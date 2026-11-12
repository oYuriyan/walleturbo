const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("fs");
(async () => {
  const seed = JSON.parse(fs.readFileSync(0, "utf8"));
  const base = process.env.APP_URL || "http://localhost:8000";
  const browser = await chromium.launch({
    ...(process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {}),
    headless: true,
    args: ["--no-sandbox"],
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1100 },
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
  const page = await context.newPage(),
    errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await require("./ui_helpers.cjs").respectRateLimits(context, page);
  let csrf;
  try {
    await page.goto(base);
    await page.getByText("Conta conectada", { exact: true }).waitFor();
    csrf = (await (await context.request.get(base + "/api/me")).json()).csrf;
    await page.locator("#month").fill("2026-11");
    await page.locator("#month").dispatchEvent("change");
    await require("./ui_helpers.cjs").navigate(page, "finance");
    await page.locator("#new-account").click();
    await page.locator("#setup-form [name=name]").fill("Conta de teste");
    await page
      .locator("#setup-form button[type=submit], #setup-form .button.full")
      .click();
    await page.locator("#setup-dialog").waitFor({ state: "hidden" });
    await page
      .locator("#balance-list")
      .getByRole("heading", { name: "Conta de teste", exact: true })
      .waitFor();
    await page.locator("#new-card").click();
    await page.locator("#setup-form [name=name]").fill("Cartão de teste");
    await page.locator("#setup-form [name=due_day]").fill("31");
    await page.locator("#setup-form .button.full").click();
    await page.locator("#setup-dialog").waitFor({ state: "hidden" });
    await page
      .locator("#card-list")
      .getByText("Cartão de teste", { exact: true })
      .waitFor();
    await page.locator("#new-purchase").click();
    await page
      .locator("#purchase-form [name=description]")
      .fill("Compra parcelada");
    await page.locator("#purchase-form [name=amount]").fill("100,01");
    await page.locator("#purchase-form [name=installments]").fill("3");
    await page.locator("#purchase-form [name=date]").fill("2026-10-28");
    await page.locator("#purchase-form [name=first_month]").fill("2026-11");
    await page.locator("#purchase-form .button.full").click();
    await page.locator("#purchase-dialog").waitFor({ state: "hidden" });
    await page.getByText("Compra parcelada · 1/3", { exact: true }).waitFor();
    if (
      !(await page.locator("#statement-list").textContent()).includes("33,34")
    )
      throw Error("Parcela incorreta");
    await page
      .getByRole("button", { name: "Conferir total", exact: true })
      .click();
    await page.locator("#reconcile-form [name=amount]").fill("33,33");
    await page.locator("#reconcile-form .button.full").click();
    await page.locator("#reconcile-dialog .dialog-error").waitFor();
    const before = (
      await (
        await context.request.get(base + "/api/statements?month=2026-11")
      ).json()
    )[0];
    const charge = before.charges[0];
    const reviewed = await context.request.put(
      base + "/api/card-charges/" + charge.id + "/review",
      {
        headers: { Origin: base, "X-CSRF-Token": csrf },
        data: {
          expected_version: charge.version,
          category: "Outros",
          reviewed: true,
        },
      },
    );
    if (reviewed.status() !== 200) throw Error("Revisão paralela falhou");
    await page.locator("#reconcile-form [name=amount]").fill("33,34");
    await page.locator("#reconcile-form .button.full").click();
    await page
      .locator("#reconcile-dialog")
      .getByText(
        "Fatura alterada em outra sessão. Atualize os dados e confira novamente.",
        { exact: true },
      )
      .waitFor();
    await page.locator("#reload-reconcile").click();
    await page.waitForFunction(
      () =>
        document.querySelector("#reconcile-form [name=amount]").value === "",
    );
    await page.locator("#reconcile-form [name=amount]").fill("33,34");
    await page.locator("#reconcile-form .button.full").click();
    await page.locator("#reconcile-dialog").waitFor({ state: "hidden" });
    await page
      .getByRole("button", { name: "Registrar pagamento", exact: true })
      .click();
    await page.locator("#payment-form [name=date]").fill("2026-11-10");
    await page.locator("#payment-form [name=amount]").fill("20,00");
    await page.locator("#payment-form .button.full").click();
    await page.locator("#payment-dialog").waitFor({ state: "hidden" });
    await page.getByRole("button", { name: "Estornar registro" }).waitFor();
    if (
      !(await page.locator("#statement-list").textContent()).includes("13,34")
    )
      throw Error("Restante incorreto");
    await page.screenshot({
      path: "artifacts/cards-desktop.png",
      fullPage: true,
    });
    await require("./ui_helpers.cjs").navigate(page, "overview");
    if (!(await page.locator("#expense").textContent()).includes("33,34"))
      throw Error("Pagamento duplicou despesa");
    if (!(await page.locator("#cash-result").textContent()).includes("20,00"))
      throw Error("Caixa incorreto");
    await page.locator("#month").fill("2026-12");
    await page.locator("#month").dispatchEvent("change");
    await require("./ui_helpers.cjs").navigate(page, "finance");
    await page.getByText("Compra parcelada · 2/3", { exact: true }).waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator("#theme-preference").selectOption("dark");
    await page.waitForTimeout(200);
    await page.screenshot({
      path: "artifacts/cards-mobile-dark.png",
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
      "PASS: navegador autenticado com API real: conta, cartão, parcelas, divergência, conferência, pagamento parcial, caixa, mês seguinte e mobile escuro.",
    );
  } finally {
    if (csrf) {
      const result = await context.request.delete(base + "/api/privacy/data", {
        headers: {
          Origin: base,
          "X-CSRF-Token": csrf,
          "X-Confirm-Delete": "EXCLUIR",
        },
      });
      if (result.status() !== 200)
        throw Error("Falha na limpeza dos dados sintéticos");
    }
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
