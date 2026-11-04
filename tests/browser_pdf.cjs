const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("fs");
(async () => {
  const seed = JSON.parse(fs.readFileSync(0, "utf8")),
    base = process.env.APP_URL || "http://localhost:8000";
  const browser = await chromium.launch({
    ...(process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {}),
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
  const page = await context.newPage(),
    errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let csrf;
  try {
    await page.goto(base);
    await page.getByText("Conta conectada", { exact: true }).waitFor();
    csrf = (await (await context.request.get(base + "/api/me")).json()).csrf;
    const headers = { Origin: base, "X-CSRF-Token": csrf };
    const card = await (
      await context.request.post(base + "/api/cards", {
        headers,
        data: { name: "Fatura de teste PDF", due_day: 10 },
      })
    ).json();
    await context.request.post(
      `${base}/api/cards/${card.id}/statements?month=2026-11`,
      { headers },
    );
    await page.locator("#month").fill("2026-11");
    await page.locator("#month").dispatchEvent("change");
    await page.getByRole("button", { name: "Contas e cartões" }).click();
    await page.getByRole("button", { name: "Ler PDF", exact: true }).click();
    await page
      .locator("#pdf-file")
      .setInputFiles("artifacts/fatura-sintetica.pdf");
    await page.locator(".pdf-row").first().waitFor({ timeout: 20000 });
    if ((await page.locator(".pdf-row").count()) !== 2)
      throw Error("Prévia incompleta");
    const before = await (
      await context.request.get(base + "/api/privacy/export")
    ).json();
    if (before.card_charges.length) throw Error("Prévia persistiu lançamentos");
    await page
      .locator(".pdf-row")
      .first()
      .locator("[name=description]")
      .fill("Mercado revisado");
    await page
      .locator(".pdf-row")
      .first()
      .locator("[name=amount]")
      .fill("120,00");
    await page.locator("#pdf-reviewed").check();
    await page.screenshot({
      path: "artifacts/pdf-desktop.png",
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: "artifacts/pdf-mobile.png", fullPage: true });
    if (
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      )
    )
      throw Error("Overflow mobile");
    await page
      .getByRole("button", { name: "Importar seleção revisada" })
      .click();
    await page.locator("#pdf-dialog").waitFor({ state: "hidden" });
    await page.getByText("Mercado revisado · 1/1", { exact: true }).waitFor();
    const result = await (
      await context.request.get(base + "/api/statements?month=2026-11")
    ).json();
    if (result[0].total_cents !== 9655 || result[0].pending !== 0)
      throw Error("Correção ou estorno não preservados");
    if (errors.length) throw Error(errors.join("\n"));
    console.log(
      "PASS: navegador com PDF real: prévia sem gravação, edição de descrição/valor, revisão, estorno, importação e mobile.",
    );
  } finally {
    if (csrf) {
      const clean = await context.request.delete(base + "/api/privacy/data", {
        headers: {
          Origin: base,
          "X-CSRF-Token": csrf,
          "X-Confirm-Delete": "EXCLUIR",
        },
      });
      if (clean.status() !== 200) throw Error("Limpeza sintética falhou");
    }
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
