const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("fs");
(async () => {
  const seed = JSON.parse(fs.readFileSync(0, "utf8")),
    base = process.env.APP_URL || "http://localhost:8000";
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox"],
  });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 1000 },
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
  const page = await context.newPage();
  let csrf;
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  try {
    await page.goto(base);
    await page.getByText("Conta conectada", { exact: true }).waitFor();
    csrf = (await (await context.request.get(base + "/api/me")).json()).csrf;
    const headers = { Origin: base, "X-CSRF-Token": csrf };
    for (const entry of [
      {
        kind: "income",
        amount_cents: 100000,
        category: "Renda",
        description: "Receita",
      },
      {
        kind: "expense",
        amount_cents: 30000,
        category: "Compras",
        description: "Compra",
      },
    ]) {
      const r = await context.request.post(base + "/api/transactions", {
        headers,
        data: { ...entry, date: "2026-11-01", reviewed: true },
      });
      if (r.status() !== 201) throw Error("Falha ao preparar registros");
    }
    await page.locator("#month").fill("2026-11");
    await page.locator("#month").dispatchEvent("change");
    await page
      .getByRole("button", { name: "Planejamento", exact: true })
      .click();
    await page
      .getByText("Sugestão de aporte indisponível até conferir os dados", {
        exact: true,
      })
      .waitFor();
    await page.locator("#budget-form [name=category]").selectOption("Compras");
    await page.locator("#budget-form [name=amount]").fill("250,00");
    await page
      .getByRole("button", { name: "Salvar limite", exact: true })
      .click();
    await page.getByText(/Excedido em R\$\s*50,00/).waitFor();
    await page.locator("#plan-form [name=buffer]").fill("100,00");
    await page.locator("#plan-form [name=complete]").check();
    await page
      .getByRole("button", { name: "Salvar cenário", exact: true })
      .click();
    await page
      .getByText(/Margem para a simulação de aportes: R\$\s*600,00/)
      .waitFor();
    await page.screenshot({
      path: "artifacts/planning-desktop.png",
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({
      path: "artifacts/planning-mobile.png",
      fullPage: true,
    });
    if (
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      )
    )
      throw Error("Overflow mobile");
    if (errors.length) throw Error(errors.join("\n"));
    console.log(
      "PASS: orçamento excedido, cenário confirmado e capacidade conservadora no navegador desktop/mobile.",
    );
  } finally {
    if (csrf)
      await context.request.delete(base + "/api/privacy/data", {
        headers: {
          Origin: base,
          "X-CSRF-Token": csrf,
          "X-Confirm-Delete": "EXCLUIR",
        },
      });
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
