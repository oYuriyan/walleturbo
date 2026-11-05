const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
(async () => {
  const browser = await chromium.launch({
    ...(process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {}),
    headless: true,
    args: ["--no-sandbox"],
  });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1100 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(process.env.APP_URL || "http://localhost:8000");
  await page.getByRole("button", { name: "Explorar demonstração" }).click();
  await page.screenshot({ path: "artifacts/desktop.png", fullPage: true });
  await page
    .getByRole("button", { name: "Movimentações", exact: false })
    .click();
  await page.getByRole("button", { name: "Novo lançamento" }).click();
  await page
    .locator("#entry-form [name=description]")
    .fill("<img src=x onerror=alert(1)>");
  await page.locator("#entry-form [name=amount]").fill("19,99");
  await page.getByRole("button", { name: "Salvar lançamento" }).click();
  await page.locator("#search").fill("<img");
  if (await page.locator("#transaction-list img").count())
    throw Error("HTML injection");
  if ((await page.locator("#transaction-list .transaction").count()) !== 1)
    throw Error("Lançamento não encontrado");
  await page.getByRole("button", { name: "Revisar", exact: true }).click();
  await page.locator("#entry-form [name=amount]").fill("29,99");
  await page
    .locator("#entry-form [name=reason]")
    .fill("Conferência da demonstração");
  await page.getByRole("button", { name: "Salvar lançamento" }).click();
  await page.getByRole("button", { name: "Minhas metas" }).click();
  await page.getByRole("button", { name: "Criar meta", exact: false }).click();
  await page.locator("#goal-form [name=name]").fill("Notebook");
  await page.locator("#goal-form [name=target]").fill("5000");
  await page.locator("#goal-form [name=saved]").fill("1000");
  await page.locator("#goal-form [name=deadline]").fill("2027-12-01");
  await page.getByRole("button", { name: "Salvar meta" }).click();
  if (!(await page.locator("#goal-list").textContent()).includes("Notebook"))
    throw Error("Meta ausente");
  await page.getByRole("button", { name: "Visão geral" }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "artifacts/mobile.png", fullPage: true });
  if (
    await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
  )
    throw Error("Overflow mobile");
  await page.locator('.topbar button[aria-label="Alternar tema"]').click();
  await page.waitForTimeout(200);
  await page.screenshot({ path: "artifacts/mobile-dark.png", fullPage: true });
  if (errors.length) throw Error(errors.join("\n"));
  console.log(
    "PASS: desktop, mobile 390px, tema escuro, lançamento, edição, busca, meta e XSS via textContent; zero erros JS.",
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
