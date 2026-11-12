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
  await require("./ui_helpers.cjs").respectRateLimits(context, page);
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
    await require("./ui_helpers.cjs").navigate(page, "planning");
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
    const added = await context.request.post(base + "/api/transactions", {
      headers,
      data: {
        date: "2026-11-02",
        description: "Receita adicional",
        amount_cents: 100,
        kind: "income",
        category: "Renda",
        reviewed: true,
      },
    });
    if (added.status() !== 201) throw Error("Receita paralela falhou");
    await page.locator("#plan-form [name=complete]").check();
    await page
      .getByRole("button", { name: "Salvar cenário", exact: true })
      .click();
    await page
      .getByText(
        "Registros alterados após a leitura. Recarregue e confira novamente.",
        { exact: true },
      )
      .waitFor();
    await require("./ui_helpers.cjs").confirmNext(page, () => page.locator("#reload-planning").click());
    await page.waitForFunction(
      () =>
        !document.querySelector("#plan-form [name=complete]").checked &&
        !document.querySelector("#plan-form [name=complete]").disabled,
    );
    await page.locator("#plan-form [name=buffer]").fill("100,00");
    await page.locator("#plan-form [name=complete]").check();
    await page
      .getByRole("button", { name: "Salvar cenário", exact: true })
      .click();
    await page
      .getByText(/Margem para a simulação de aportes: R\$\s*601,00/)
      .waitFor();
    const current = await (
      await context.request.get(base + "/api/planning/2026-11")
    ).json();
    const changed = await context.request.put(
      base + "/api/planning/2026-11/plan",
      {
        headers,
        data: {
          expected_version: current.version,
          expected_records_revision: current.records_revision,
          buffer_cents: 20000,
          records_complete: true,
        },
      },
    );
    if (changed.status() !== 200) throw Error("Alteração paralela não aceita");
    await page.locator("#plan-form [name=buffer]").fill("50,00");
    await page
      .getByRole("button", { name: "Salvar cenário", exact: true })
      .click();
    await page
      .getByText(
        "Planejamento alterado em outra sessão. Recarregue antes de salvar.",
        { exact: true },
      )
      .waitFor();
    await require("./ui_helpers.cjs").confirmNext(page, () => page.locator("#reload-planning").click());
    await page.waitForFunction(
      () =>
        document.querySelector("#plan-form [name=buffer]").value === "200,00",
    );
    if (
      (await (await context.request.get(base + "/api/planning/2026-11")).json())
        .version !==
      current.version + 1
    )
      throw Error("Conflito sobrescreveu o cenário");
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
    const erased = await context.request.delete(base + "/api/privacy/data", {
      headers: {
        Origin: base,
        "X-CSRF-Token": csrf,
        "X-Confirm-Delete": "EXCLUIR",
      },
    });
    if (erased.status() !== 200)
      throw Error("Falha ao limpar dados sintéticos");
    csrf = null;
    await require("./ui_helpers.cjs").navigate(page, "planning");
    await page.getByText("Sessão encerrada", { exact: true }).waitFor();
    if (
      (await page.locator("#capacity").textContent()) ||
      (await page.locator("#plan-form [name=income]").inputValue())
    )
      throw Error("Dados de planejamento permaneceram após encerrar a sessão");
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
