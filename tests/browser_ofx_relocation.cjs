const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("fs"),
  assert = require("assert/strict"),
  { randomUUID } = require("crypto");
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
  const content = fs.readFileSync("tests/fixtures/ofx/card-102.ofx", "utf8");
  const imported = { content, reviewed: true, excluded_indices: [1, 2] };
  const post = (url, data) =>
    context.request.post(base + url, { headers, data });
  try {
    const card = await (
      await post("/api/cards", { name: "Competência OFX", due_day: 10 })
    ).json();
    const bills = [];
    for (const month of ["2026-11", "2026-12"])
      bills.push(
        await (
          await post(`/api/cards/${card.id}/statements?month=${month}`)
        ).json(),
      );
    const path = (bill) => `/api/statements/${bill.id}/import/ofx`;
    assert.equal(
      (await post(path(bills[0]) + "/confirm", imported)).status(),
      200,
    );
    const initial = (
      await (await context.request.get(base + "/api/privacy/export")).json()
    ).card_charges[0];
    await page.goto(base);
    await page.getByText("Conta conectada", { exact: true }).waitFor();
    await page.locator("#month").fill("2026-11");
    await page.locator("#month").dispatchEvent("change");
    await require("./ui_helpers.cjs").navigate(page, "finance");
    const open = async () => {
      await page
        .locator("#statement-list")
        .getByRole("button", { name: "Importar CSV / OFX", exact: true })
        .click();
      await page.locator("#import-format").selectOption("ofx");
      await page
        .locator("#csv-file")
        .setInputFiles({
          name: "competencia.ofx",
          mimeType: "application/x-ofx",
          buffer: Buffer.from(content),
        });
      await page.locator('details[data-relocation-index="0"]').waitFor();
      await page.locator('details[data-relocation-index="0"] summary').click();
      return page.locator('details[data-relocation-index="0"]');
    };
    let controls = await open();
    const simulate = () =>
      controls.getByRole("button", { name: "Simular mudança", exact: true });
    const confirmMove = () =>
      controls.getByRole("button", {
        name: "Confirmar mudança de competência",
        exact: true,
      });
    await controls
      .getByLabel("Fatura de destino", { exact: true })
      .selectOption(bills[1].id);
    await controls
      .getByLabel("Motivo da mudança de competência", { exact: true })
      .fill("Competência conferida");
    await simulate().click();
    await controls.getByText(/Fatura 2026-12: total/).waitFor();
    assert(await confirmMove().isDisabled());
    await controls.getByRole("checkbox").check();
    assert(await confirmMove().isEnabled());
    await controls
      .getByLabel("Motivo da mudança de competência", { exact: true })
      .fill("Competência revisada no documento");
    assert(await confirmMove().isDisabled());
    assert(!(await controls.getByRole("checkbox").isChecked()));
    await simulate().click();
    await controls.getByText(/Fatura 2026-12: total/).waitFor();
    await controls.getByRole("checkbox").check();
    await confirmMove().scrollIntoViewIfNeeded();
    await page
      .locator("#import-dialog")
      .screenshot({ path: "artifacts/ofx-relocation-mobile.png" });
    const moved = page.waitForResponse(
      (r) => r.url().endsWith("/import/ofx/relocate") && r.status() === 200,
    );
    await confirmMove().click();
    assert.equal((await (await moved).json()).moved, 1);
    await page.locator("#import-dialog").waitFor({ state: "hidden" });
    let exported = await (
      await context.request.get(base + "/api/privacy/export")
    ).json();
    assert.equal(exported.card_charges.length, 1);
    assert.equal(exported.card_charges[0].id, initial.id);
    assert.equal(exported.card_charges[0].operation_id, initial.operation_id);
    assert.equal(exported.card_charges[0].statement_id, bills[1].id);
    assert.equal(exported.import_marks[0].container_id, bills[1].id);
    assert.equal(
      exported.statement_payments.length + exported.transactions.length,
      0,
    );
    assert.equal(
      (await post(path(bills[0]) + "/confirm", imported)).status(),
      409,
    );
    assert.equal(
      (await (await post(path(bills[1]) + "/confirm", imported)).json())
        .created,
      0,
    );
    const history = await (
      await context.request.get(base + "/api/history?entity=import_relocation")
    ).json();
    assert.equal(
      history.items[0].after.reason,
      "Competência revisada no documento",
    );
    const loaded = page.waitForResponse(
      (r) =>
        r.url().includes("/api/statements?month=2026-12") && r.status() === 200,
    );
    await page.locator("#month").fill("2026-12");
    await page.locator("#month").dispatchEvent("change");
    await loaded;
    controls = await open();
    await controls
      .getByLabel("Motivo da mudança de competência", { exact: true })
      .fill("Nova simulação não confirmada");
    let release, fetched;
    const held = new Promise((resolve) => (release = resolve)),
      received = new Promise((resolve) => (fetched = resolve));
    await page.route("**/import/ofx/relocate/preview", async (route) => {
      const response = await route.fetch();
      assert.equal(response.status(), 200);
      fetched();
      await held;
      await route.fulfill({ response });
    });
    await simulate().click();
    await received;
    await require("./ui_helpers.cjs").confirmNext(page, () => page.locator("#import-dialog .close").click());
    const finished = page.waitForResponse((r) =>
      r.url().endsWith("/import/ofx/relocate/preview"),
    );
    release();
    await finished;
    await page.waitForFunction(
      () => document.querySelector("#import-preview").textContent === "",
    );
    assert(!(await page.locator("#import-dialog").isVisible()));
    exported = await (
      await context.request.get(base + "/api/privacy/export")
    ).json();
    assert.equal(exported.card_charges.length, 1);
    assert.equal(exported.card_charges[0].statement_id, bills[1].id);
    assert.deepEqual(errors, []);
    console.log(
      "PASS: realocação OFX mobile simula duas faturas, invalida revisão ao editar, preserva ID/origem/histórico, impede duplicação no reenvio e descarta resposta após fechar.",
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
