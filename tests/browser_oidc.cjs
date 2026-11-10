// A fixture chega por stdin; não gravar senha, QR, segredo TOTP ou tokens em artefatos.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const { createHmac } = require("crypto");
const fs = require("fs");
const assert = require("assert/strict");
const { buildJourney, request } = require("./basic_journey.cjs");
const base = "http://localhost:8000";
function totp(secret, now = Date.now()) {
  // O campo oculto do Keycloak contém o segredo bruto; a tela/QR usa Base32.
  const key = Buffer.from(secret, "utf8");
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(now / 30000)));
  const hash = createHmac("sha1", key).update(counter).digest();
  const offset = hash[hash.length - 1] & 15;
  return ((hash.readUInt32BE(offset) & 0x7fffffff) % 1000000)
    .toString()
    .padStart(6, "0");
}
assert.equal(totp("12345678901234567890", 59000), "287082");
(async () => {
  const fixture = JSON.parse(fs.readFileSync(0, "utf8"));
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox"],
  });
  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    assert.equal((await context.request.get(base + "/api/me")).status(), 401);
    const start = await page.goto(base + "/auth/login");
    const errorCode = new URL(page.url()).searchParams.get("error");
    console.log(
      "OIDC: resposta inicial",
      start.status(),
      "host",
      new URL(page.url()).hostname,
      "erro",
      /^[a-z_]+$/.test(errorCode || "") ? errorCode : "nenhum",
    );
    assert.equal(new URL(page.url()).hostname, "auth.walleturbo.localhost");
    assert.equal(
      new URL(page.url()).searchParams.get("code_challenge_method"),
      "S256",
    );
    const before = (await context.cookies(base)).find(
      (c) => c.name === "walleturbo_session",
    );
    assert(before);
    await page.locator("#username").fill(fixture.username);
    await page.locator("#password").fill(fixture.password);
    await page.locator("#kc-login").click();
    await page.locator("#totpSecret").waitFor({ state: "attached" });
    assert.equal((await context.request.get(base + "/api/me")).status(), 401);
    const secret = await page.locator("#totpSecret").inputValue();
    const valid = totp(secret);
    await page.locator("#totp").fill(valid === "000000" ? "111111" : "000000");
    await page.locator("#userLabel").fill("CI sintético");
    await page.locator("#saveTOTPBtn").click();
    await page.locator("#input-error-otp-code").waitFor();
    assert.equal((await context.request.get(base + "/api/me")).status(), 401);
    await page.locator("#totp").fill(totp(secret));
    await page.locator("#saveTOTPBtn").click();
    await page.waitForURL(base + "/");
    const me = await context.request.get(base + "/api/me");
    assert.equal(me.status(), 200);
    const { csrf } = await me.json();
    const firstLoginStep = Math.floor(Date.now() / 30000);
    const after = (await context.cookies(base)).find(
      (c) => c.name === "walleturbo_session",
    );
    assert(after && after.value !== before.value);
    assert(after.httpOnly && after.sameSite === "Lax");
    // A sessão pré-login é revogada ao completar a troca OIDC.
    const stolen = await browser.newContext();
    await stolen.addCookies([{ ...before, url: undefined }]);
    assert.equal((await stolen.request.get(base + "/api/me")).status(), 401);
    await stolen.close();
    const checkpoint = await buildJourney(context, page, csrf);
    // Outro login real precisa permanecer isolado, inclusive ao tentar escrever.
    const otherContext = await browser.newContext();
    try {
      const otherPage = await otherContext.newPage();
      await otherPage.goto(base + "/auth/login");
      await otherPage.locator("#username").fill(fixture.other.username);
      await otherPage.locator("#password").fill(fixture.other.password);
      await otherPage.locator("#kc-login").click();
      await otherPage.locator("#totpSecret").waitFor({ state: "attached" });
      const otherSecret = await otherPage.locator("#totpSecret").inputValue();
      await otherPage.locator("#totp").fill(totp(otherSecret));
      await otherPage.locator("#userLabel").fill("CI isolado");
      await otherPage.locator("#saveTOTPBtn").click();
      await otherPage.waitForURL(base + "/");
      const otherCsrf = (await request(otherContext, "", "/api/me")).csrf;
      assert.equal(
        (await request(otherContext, otherCsrf, "/api/accounts")).length,
        0,
      );
      await request(
        otherContext,
        otherCsrf,
        "/api/transactions/" + checkpoint.entryId,
        "GET",
        undefined,
        404,
      );
      await request(
        otherContext,
        otherCsrf,
        "/api/statements/" + checkpoint.billId,
        "GET",
        undefined,
        404,
      );
      await request(
        otherContext,
        otherCsrf,
        "/api/transactions",
        "POST",
        {
          request_id: require("crypto").randomUUID(),
          account_id: checkpoint.accountId,
          date: "2026-11-10",
          description: "Tentativa de vínculo cruzado",
          amount_cents: 1,
          kind: "expense",
        },
        404,
      );
      assert.deepEqual(
        await request(context, csrf, "/api/privacy/export"),
        checkpoint.exported,
      );
    } finally {
      await otherContext.close();
    }
    assert.equal(
      (
        await context.request.post(base + "/api/logout", {
          headers: { Origin: base, "X-CSRF-Token": csrf },
        })
      ).status(),
      200,
    );
    assert.equal((await context.request.get(base + "/api/me")).status(), 401);
    await page.evaluate(async () => {
      await api("/api/accounts").catch(() => {});
    });
    assert.match(await page.locator("#expense").textContent(), /0,00/);
    assert(await page.locator("#first-steps").isHidden());
    // Nova sessão da mesma identidade deve recuperar os mesmos registros.
    await page.goto(base + "/auth/login");
    await page.locator("#username").fill(fixture.username);
    await page.locator("#password").fill(fixture.password);
    await page.locator("#kc-login").click();
    // O mesmo código não pode ser reutilizado na janela da primeira autenticação.
    if (Math.floor(Date.now() / 30000) <= firstLoginStep)
      await new Promise((resolve) =>
        setTimeout(resolve, 30000 - (Date.now() % 30000) + 1000),
      );
    await page.locator("#otp").fill(totp(secret));
    await page.locator("#kc-login").click();
    await page.waitForURL(base + "/");
    const currentCsrf = (await request(context, "", "/api/me")).csrf;
    assert.deepEqual(
      await request(context, currentCsrf, "/api/privacy/export"),
      checkpoint.exported,
    );
    await context.request.post(base + "/api/logout", {
      headers: { Origin: base, "X-CSRF-Token": currentCsrf },
    });
    assert.equal((await context.request.get(base + "/api/me")).status(), 401);
    console.log(
      "PASS: jornada básica com login/TOTP real, duas contas, saldos, correção/reenvio CSV, transferência, parcelas/estorno/pagamento, planejamento/exportação, isolamento com segundo login real e persistência após nova sessão.",
    );
    // Uma tentativa com state incorreto precisa ser rejeitada sem autenticar.
    await page.goto(base + "/auth/login");
    const invalid = await context.request.get(
      base + "/auth/callback?state=invalid&code=invalid",
      { maxRedirects: 0 },
    );
    assert.equal(invalid.status(), 400);
    assert.equal((await context.request.get(base + "/api/me")).status(), 401);
    console.log(
      "PASS: Keycloak real, PKCE, cadastro TOTP, recusa de código incorreto/ausente, ID token assinado, rotação, logout e state inválido.",
    );
  } finally {
    await context.close();
    await browser.close();
  }
})().catch((error) => {
  const location = (error.stack || "")
    .split("\n")
    .find(
      (line) =>
        line.includes("browser_oidc.cjs:") ||
        line.includes("basic_journey.cjs:"),
    );
  console.error(
    "FAIL: fluxo OIDC real:",
    error.name,
    location?.trim() || "sem localização",
  );
  process.exitCode = 1;
});
