const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("fs"),
  assert = require("assert/strict");
(async () => {
  const seed = JSON.parse(fs.readFileSync(0, "utf8")),
    base = process.env.APP_URL || "http://localhost:8000";
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox"],
  });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    locale: "pt-BR",
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
  const csrf = (await (await context.request.get(base + "/api/me")).json())
    .csrf;
  const headers = { Origin: base, "X-CSRF-Token": csrf },
    page = await context.newPage(),
    errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    await page.goto(base);
    await page.getByText("Conta conectada", { exact: true }).waitFor();
    const guide = page.locator("#first-steps");
    await guide.waitFor();
    assert(await guide.evaluate((node) => node.open));
    await guide.screenshot({ path: "artifacts/first-steps-mobile.png" });
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    await page.locator("#start-account").click();
    await page.locator('#setup-form [name="name"]').fill("Minha conta");
    await page
      .locator("#setup-form")
      .getByRole("button", { name: "Cadastrar", exact: true })
      .click();
    await page.locator("#setup-dialog").waitFor({ state: "hidden" });
    const panel = page.locator(".account-balance");
    await panel
      .getByRole("button", { name: "Definir saldo inicial", exact: true })
      .waitFor();
    await require("./ui_helpers.cjs").navigate(page, "overview");
    await page.locator("#start-balances").click();
    assert(
      await page
        .locator("#balance-date")
        .evaluate((node) => node === document.activeElement),
    );
    await page.locator("#balance-date").fill("2026-11-30");
    await page.locator("#balance-date").dispatchEvent("change");
    await panel
      .getByRole("button", { name: "Definir saldo inicial", exact: true })
      .click();
    const opening = page.locator("#opening-form");
    await opening.locator('[name="date"]').fill("2026-11-01");
    await opening.locator('[name="amount"]').fill("1000,00");
    await opening.locator('[name="reason"]').fill("Saldo no início do mês");
    await opening
      .getByRole("button", { name: "Salvar referência", exact: true })
      .click();
    await page.locator("#opening-dialog").waitFor({ state: "hidden" });
    await panel
      .getByRole("button", { name: "Corrigir referência", exact: true })
      .waitFor();
    await require("./ui_helpers.cjs").navigate(page, "overview");
    await guide
      .getByRole("button", {
        name: "Registrar receita ou despesa",
        exact: true,
      })
      .click();
    const entry = page.locator("#entry-form");
    await entry.locator('[name="description"]').fill("Primeira despesa");
    await entry.locator('[name="amount"]').fill("25,00");
    await entry.locator('[name="date"]').fill("2026-11-02");
    await entry
      .locator('[name="account_id"]')
      .selectOption({ label: "Minha conta" });
    await entry.locator('button[type="submit"]').click();
    await page.locator("#entry-dialog").waitFor({ state: "hidden" });
    const report = await (
      await context.request.get(base + "/api/balances?as_of=2026-11-30")
    ).json();
    assert.equal(report.total_cents, 97500);
    const exported = await (
      await context.request.get(base + "/api/privacy/export")
    ).json();
    assert.equal(exported.accounts.length, 1);
    assert.equal(exported.transactions.length, 1);
    await page.reload();
    await page.getByText("Conta conectada", { exact: true }).waitFor();
    await page.waitForFunction(
      () =>
        document.querySelector("#first-steps").dataset.initialized === "true",
    );
    assert(!(await guide.evaluate((node) => node.open)));
    await context.request.delete(base + "/api/privacy/data", {
      headers: { ...headers, "X-Confirm-Delete": "EXCLUIR" },
    });
    await page.evaluate(async () => {
      await api("/api/accounts").catch(() => {});
    });
    assert(await guide.isHidden());
    await page.reload();
    await page.locator("#demo").click();
    assert(await guide.isHidden());
    assert.deepEqual(errors, []);
    console.log(
      "PASS: primeiro uso mobile cadastra conta, define referência, registra despesa e reconcilia R$ 975; guia recolhe no retorno e fica oculto na sessão encerrada/demonstração.",
    );
  } finally {
    await context.request.delete(base + "/api/privacy/data", {
      headers: { ...headers, "X-Confirm-Delete": "EXCLUIR" },
    });
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
