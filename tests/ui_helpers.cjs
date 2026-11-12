// Ações compartilhadas dos testes para os componentes nativos do redesign.
async function confirmNext(page, trigger) {
  await trigger();
  await page.locator("#confirm-dialog").waitFor();
  await page.locator("#confirm-dialog [value=confirm]").click();
  await page.locator("#confirm-dialog").waitFor({ state: "hidden" });
}
async function clickRowAction(row, name) {
  const menu = row.locator(".row-menu");
  if (!(await menu.evaluate((node) => node.open))) await menu.locator("summary").click();
  await row.getByRole("button", { name, exact: true }).click();
}
async function navigate(page, view) {
  const link = page.locator(`.nav[data-view="${view}"]`);
  if (!(await link.isVisible())) await page.locator("#more-navigation-button").click();
  await link.click();
}
async function respectRateLimits(context, page) {
  if (process.env.UI_RATE_RETRY !== "1") return;
  page.setDefaultTimeout(90000);
  const retry = async (request) => {
    let response;
    for (let attempt = 0; attempt < 3; attempt++) {
      response = await request();
      if (response.status() !== 429) return response;
      const seconds = Number(response.headers()["retry-after"]);
      if (!(seconds > 0 && seconds <= 60)) return response;
      console.log(`Cota de teste respeitada; aguardando Retry-After de ${seconds}s.`);
      await new Promise((resolve) => setTimeout(resolve, seconds * 1000 + 100));
    }
    return response;
  };
  for (const method of ["get", "post", "put", "delete", "patch", "fetch"]) {
    const original = context.request[method].bind(context.request);
    context.request[method] = (...args) => retry(() => original(...args));
  }
  await context.route("**/api/**", async (route) => {
    const response = await retry(() => route.fetch());
    await route.fulfill({ response });
  });
}
module.exports = { confirmNext, clickRowAction, navigate, respectRateLimits };
