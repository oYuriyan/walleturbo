const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("assert/strict");
const fs = require("fs");
(async () => {
  const fixture = JSON.parse(fs.readFileSync(0, "utf8"));
  const base = process.env.APP_URL || "http://localhost:8000";
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
      value: fixture.sid,
      url: base,
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  let csrf = fixture.csrf;
  try {
    csrf = (await (await context.request.get(base + "/api/me")).json()).csrf;
    const started = Date.now();
    await page.goto(base);
    await page.getByText("Conta conectada", { exact: true }).waitFor();
    await page.locator("#month").fill("2026-11");
    await page.locator("#month").blur();
    await page.waitForFunction(
      () =>
        document.querySelector("main").dataset.renderedMonth === "2026-11" &&
        document.querySelector("main").getAttribute("aria-busy") === "false",
    );
    const renderedMs = Date.now() - started;
    assert(
      renderedMs < 10000,
      "Resumo mobile deve carregar em até 10 segundos neste ensaio",
    );
    const expected = new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
    }).format(fixture.balance_cents / 100);
    assert.equal(await page.locator("#balance").textContent(), expected);
    await page.locator('.nav[data-view="transactions"]').click();
    assert.equal(
      await page.locator("#transaction-list .transaction").count(),
      fixture.month_count,
    );
    await page.locator("#search").fill("Registro 000022");
    assert.equal(
      await page.locator("#transaction-list .transaction").count(),
      1,
    );
    await page.locator('.nav[data-view="finance"]').click();
    assert.equal(
      await page.locator("#statement-list .transaction").count(),
      100,
    );
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    assert.deepEqual(errors, []);
    fixture.report.browser = {
      engine: "chromium",
      viewport: 390,
      rendered_ms: renderedMs,
      monthly_transactions: fixture.month_count,
      monthly_charges: 100,
    };
    fs.writeFileSync(
      "artifacts/v1-volume.json",
      JSON.stringify(fixture.report, null, 2) + "\n",
    );
    await page.screenshot({
      path: "artifacts/volume-mobile.png",
      fullPage: true,
    });
    console.log(
      "PASS: 10 mil lançamentos/2.400 compras em 24 meses, leitura/totais/exportação e busca mobile; " +
        JSON.stringify(fixture.report),
    );
  } finally {
    if (csrf) {
      const removed = await context.request.delete(base + "/api/privacy/data", {
        headers: {
          Origin: base,
          "X-CSRF-Token": csrf,
          "X-Confirm-Delete": "EXCLUIR",
        },
      });
      assert.equal(removed.status(), 200);
    }
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
