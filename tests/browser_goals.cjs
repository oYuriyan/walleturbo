const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("fs"),
  assert = require("assert/strict");
const base = "http://localhost:8000";
(async () => {
  const seed = JSON.parse(fs.readFileSync(0, "utf8"));
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox"],
  });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
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
  let headers;
  try {
    const csrf = (await (await context.request.get(base + "/api/me")).json())
      .csrf;
    headers = { Origin: base, "X-CSRF-Token": csrf };
    await page.goto(base);
    await page.getByText("Conta conectada", { exact: true }).waitFor();
    await page.locator('[data-view="goals"]').click();
    await page.locator('#goals [data-action="new-goal"]').click();
    const form = page.locator("#goal-form"),
      dialog = page.locator("#goal-dialog");
    await form.locator('[name="name"]').fill("Reserva sintética");
    await form.locator('[name="target"]').fill("1000,00");
    await form.locator('[name="saved"]').fill("50,00");
    await form.locator('[name="deadline"]').fill("2027-12-01");
    // O refresh termina com a lista de transferências; escutar antes do envio.
    const saveAndRefresh = async () => {
      const refreshed = page.waitForResponse(
        (r) => r.url().includes("/api/transfers?") && r.status() === 200,
      );
      await form
        .getByRole("button", { name: "Salvar meta", exact: true })
        .click();
      await dialog.waitFor({ state: "hidden" });
      await refreshed;
    };
    await saveAndRefresh();
    const manage = async () =>
      page
        .locator("#goal-list")
        .getByRole("button", { name: "Gerenciar meta", exact: true })
        .click();
    await manage();
    const row = (
      await (await context.request.get(base + "/api/privacy/export")).json()
    ).goals[0];
    const path = base + "/api/goals/" + row.id;
    const { id, version, ...body } = row;
    assert.equal(
      (
        await context.request.put(path, {
          headers,
          data: { ...body, name: "Outra sessão", expected_version: version },
        })
      ).status(),
      200,
    );
    await form.locator('[name="name"]').fill("Edição obsoleta");
    await form
      .getByRole("button", { name: "Salvar meta", exact: true })
      .click();
    await dialog
      .getByText(
        "Cadastro alterado em outra sessão. Atualize antes de salvar.",
        { exact: true },
      )
      .waitFor();
    await page.locator("#reload-goal").click();
    await page.waitForFunction(
      () =>
        document.querySelector('#goal-form [name="name"]').value ===
        "Outra sessão",
    );
    await form.locator('[name="archived"]').check();
    await saveAndRefresh();
    await page
      .locator("#goal-list")
      .getByText("Meta arquivada · fora da simulação", { exact: true })
      .waitFor();
    assert.equal(
      (await (await context.request.get(base + "/api/planning/2026-11")).json())
        .goals.length,
      0,
    );
    await manage();
    page.once("dialog", (d) => d.accept());
    await page.locator("#delete-goal").click();
    await dialog
      .getByText(
        "Meta possui reserva informada. Mantenha arquivada ou revise a reserva antes de excluir.",
        { exact: true },
      )
      .waitFor();
    await page.screenshot({
      path: "artifacts/goals-mobile.png",
      fullPage: true,
    });
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    await form.locator('[name="archived"]').uncheck();
    await saveAndRefresh();
    assert.equal(
      (await (await context.request.get(base + "/api/planning/2026-11")).json())
        .goals.length,
      1,
    );
    await manage();
    await form.locator('[name="archived"]').check();
    await form.locator('[name="saved"]').fill("0,00");
    await saveAndRefresh();
    await manage();
    page.once("dialog", (d) => d.accept());
    await page.locator("#delete-goal").click();
    await dialog.waitFor({ state: "hidden" });
    await page
      .locator("#goal-list")
      .getByText("Crie uma meta para começar a planejar.", { exact: true })
      .waitFor();
    await page.locator('[data-view="finance"]').click();
    const unsafe = "<img src=x onerror=alert(1)>";
    assert.equal(
      (
        await context.request.post(base + "/api/transactions", {
          headers,
          data: {
            date: "2026-11-03",
            description: unsafe,
            amount_cents: 1234,
            kind: "expense",
            category: "Outros",
            reviewed: true,
          },
        })
      ).status(),
      201,
    );
    await page.locator("#refresh-history").click();
    await page
      .locator("#history-list")
      .getByText(unsafe, { exact: false })
      .first()
      .waitFor();
    assert.equal(await page.locator("#history-list img").count(), 0);
    await page
      .locator("#history-list details")
      .first()
      .locator("summary")
      .click();
    await page
      .locator("#history-list")
      .getByText("R$ 12,34", { exact: true })
      .waitFor();
    await page.screenshot({
      path: "artifacts/history-mobile.png",
      fullPage: true,
    });
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    await page.locator('[data-view="goals"]').click();
    await page.locator('#goals [data-action="new-goal"]').click();
    await form.locator('[name="name"]').fill("Não deve persistir na tela");
    await form.locator('[name="target"]').fill("10,00");
    await form.locator('[name="deadline"]').fill("2027-01-01");
    let release, received;
    const held = new Promise((resolve) => (release = resolve));
    const ready = new Promise((resolve) => (received = resolve));
    await page.route("**/api/dashboard?*", async (route) => {
      const response = await route.fetch();
      received();
      await held;
      await route.fulfill({ response });
    });
    const delayed = page.evaluate(() => refresh());
    await ready;
    assert.equal(
      (
        await context.request.delete(base + "/api/privacy/data", {
          headers: { ...headers, "X-Confirm-Delete": "EXCLUIR" },
        })
      ).status(),
      200,
    );
    headers = null;
    await form
      .getByRole("button", { name: "Salvar meta", exact: true })
      .click();
    await dialog.waitFor({ state: "hidden" });
    release();
    await delayed;
    assert.equal(
      await page.locator("#transaction-list .transaction").count(),
      0,
    );
    assert.equal(await page.locator("#goal-list [data-goal-id]").count(), 0);
    assert.equal(await form.locator('[name="name"]').inputValue(), "");
    assert.equal(await form.locator('[name="id"]').inputValue(), "");
    assert.equal(await page.locator("#history-list").textContent(), "");
    console.log(
      "PASS: metas no navegador: criação, conflito/recarga, arquivamento/reativação, exclusão protegida, planejamento, histórico sem injeção HTML e limpeza de sessão.",
    );
  } finally {
    if (headers)
      await context.request.delete(base + "/api/privacy/data", {
        headers: { ...headers, "X-Confirm-Delete": "EXCLUIR" },
      });
    await context.close();
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
