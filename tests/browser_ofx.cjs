const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("fs"),
  assert = require("assert/strict");
(async () => {
  const seed = JSON.parse(fs.readFileSync(0, "utf8")),
    base = process.env.APP_URL || "http://localhost:8000";
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox"],
    ...(process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {}),
  });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    locale: "pt-BR",
    timezoneId: "America/Sao_Paulo",
  });
  await context.addCookies([
    {
      name: "walleturbo_session",
      value: seed.sid,
      url: base,
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
  const headers = {
    Origin: base,
    "X-CSRF-Token": (await (await context.request.get(base + "/api/me")).json())
      .csrf,
  };
  const page = await context.newPage(),
    errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await require("./ui_helpers.cjs").respectRateLimits(context, page);
  const source = fs
    .readFileSync("tests/fixtures/ofx/bank-102.ofx", "utf8")
    .replace("ENCODING:UTF-8", "ENCODING:USASCII")
    .replace("CHARSET:NONE", "CHARSET:1252");
  const file = (text) => ({
    name: "extrato-sintetico.ofx",
    mimeType: "application/x-ofx",
    buffer: Buffer.from(text, "latin1"),
  });
  try {
    const a = (
      await (
        await context.request.post(base + "/api/accounts", {
          headers,
          data: { name: "Conta OFX A" },
        })
      ).json()
    ).id;
    const b = (
      await (
        await context.request.post(base + "/api/accounts", {
          headers,
          data: { name: "Conta OFX B" },
        })
      ).json()
    ).id;
    const manual = await (
      await context.request.post(base + "/api/transactions", {
        headers,
        data: {
          account_id: a,
          date: "2026-11-03",
          description: "Mercado manual",
          amount_cents: 1234,
          kind: "expense",
          category: "Outros",
        },
      })
    ).json();
    await page.goto(base);
    await page.getByText("Conta conectada", { exact: true }).waitFor();
    await page.locator("#month").fill("2026-11");
    await page.locator("#month").dispatchEvent("change");
    await require("./ui_helpers.cjs").navigate(page, "transactions");
    const open = async () => {
      await page.locator("#import-button").click();
      await page.locator("#import-format").selectOption("ofx");
      await page.locator("#import-account").selectOption(a);
    };
    await open();
    await page.locator("#csv-file").setInputFiles(file(source));
    await page.locator('#import-preview select[data-link-index="0"]').waitFor();
    await page
      .locator("#import-preview")
      .getByText(/Conta do arquivo ••••1234/)
      .waitFor();
    assert.equal(
      (await page.locator("#import-preview").textContent()).includes(
        "00001234",
      ),
      false,
    );
    await page.locator("#import-account").selectOption(b);
    await page.waitForFunction(
      () =>
        document.querySelector("#import-preview").dataset.base ===
          "/api/import/ofx" &&
        !!document.querySelector('input[data-source-index="0"]') &&
        !document.querySelector("select[data-link-index]"),
    );
    assert(await page.locator("#confirm-import").isDisabled());
    await page.locator("#import-account").selectOption(a);
    await page
      .locator('#import-preview select[data-link-index="0"]')
      .selectOption(manual.id);
    await page.locator('input[data-source-index="1"]').uncheck();
    await page.locator('input[data-source-index="2"]').uncheck();
    await page.locator("#import-acknowledgement").check();
    let response = page.waitForResponse(
      (r) => r.url().endsWith("/api/import/ofx/confirm") && r.status() === 200,
    );
    await page.locator("#confirm-import").click();
    assert.equal((await (await response).json()).linked, 1);
    await page.locator("#import-dialog").waitFor({ state: "hidden" });
    await open();
    await page.locator("#csv-file").setInputFiles(file(source));
    await page
      .locator('input[data-release-reason="0"]')
      .fill("Destino conferido novamente");
    response = page.waitForResponse(
      (r) => r.url().endsWith("/api/import/ofx/unlink") && r.status() === 200,
    );
    await require("./ui_helpers.cjs").confirmNext(page, async () => {
      await page.locator('button[data-release-index="0"]').click();
    });
    assert.equal((await (await response).json()).released, 1);
    await page
      .locator('input[data-release-reason="0"]')
      .waitFor({ state: "detached" });
    await page
      .locator('#import-preview select[data-link-index="0"]')
      .selectOption(manual.id);
    await page.locator("#import-acknowledgement").check();
    await page.locator("#confirm-import").scrollIntoViewIfNeeded();
    await page
      .locator("#import-dialog")
      .screenshot({ path: "artifacts/ofx-mobile.png" });
    response = page.waitForResponse(
      (r) => r.url().endsWith("/api/import/ofx/confirm") && r.status() === 200,
    );
    await page.locator("#confirm-import").click();
    const result = await (await response).json();
    assert.equal(result.created, 2);
    assert.equal(result.linked, 1);
    await page.locator("#import-dialog").waitFor({ state: "hidden" });
    const replay = await context.request.post(
      base + "/api/import/ofx/confirm",
      {
        headers,
        data: {
          account_id: a,
          content: fs.readFileSync("tests/fixtures/ofx/bank-220.ofx", "utf8"),
          reviewed: true,
        },
      },
    );
    assert.equal(replay.status(), 200);
    assert.equal((await replay.json()).created, 0);
    await open();
    await page
      .locator("#csv-file")
      .setInputFiles(file(source.replace("2500.00", "2600.00")));
    await page
      .locator("#import-preview")
      .getByText(/Identificador de origem já recebido/)
      .waitFor();
    await page.locator("#import-acknowledgement").check();
    assert(await page.locator("#confirm-import").isDisabled());
    await page.locator('input[data-source-index="1"]').uncheck();
    assert(await page.locator("#confirm-import").isEnabled());
    await page.locator("#import-dialog .close").click();
    await page.waitForFunction(
      () => document.querySelector("#import-preview").textContent === "",
    );
    assert.equal(await page.locator("#import-preview").textContent(), "");
    const exported = await (
      await context.request.get(base + "/api/privacy/export")
    ).json();
    assert.equal(exported.transactions.length, 3);
    assert.equal(
      exported.transactions.filter((e) => e.kind === "expense").length,
      2,
    );
    assert.equal(
      exported.transactions.find((e) => e.kind === "income").amount_cents,
      250000,
    );
    assert.deepEqual(errors, []);
    console.log(
      "PASS: OFX mobile Windows-1252, conta/contexto, seleção, vínculo/desfazimento, FITIDs entre formatos e bloqueio de origem divergente sem alteração financeira.",
    );
  } finally {
    assert.equal(
      (
        await context.request.delete(base + "/api/privacy/data", {
          headers: { ...headers, "X-Confirm-Delete": "EXCLUIR" },
        })
      ).status(),
      200,
    );
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
