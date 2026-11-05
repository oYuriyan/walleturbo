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
    viewport: { width: 1280, height: 1000 },
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
  try {
    const me = await context.request.get(base + "/api/me");
    csrf = (await me.json()).csrf;
    const headers = { Origin: base, "X-CSRF-Token": csrf };
    for (const name of ["Principal", "Reserva"]) {
      assert.equal(
        (
          await context.request.post(base + "/api/accounts", {
            headers,
            data: { name },
          })
        ).status(),
        201,
      );
    }
    await page.goto(base);
    await page.getByText("Conta conectada", { exact: true }).waitFor();
    await page.locator('[data-view="finance"]').click();
    await page.locator("#balance-date").fill("2026-11-30");
    await page.locator("#balance-date").dispatchEvent("change");
    for (const [name, amount] of [
      ["Principal", "1000,00"],
      ["Reserva", "0,00"],
    ]) {
      const panel = page
        .locator(".account-balance")
        .filter({ has: page.getByRole("heading", { name, exact: true }) });
      await panel
        .getByRole("button", { name: "Definir saldo inicial", exact: true })
        .click();
      const form = page.locator("#opening-form");
      await form.locator('[name="date"]').fill("2026-11-01");
      await form.locator('[name="amount"]').fill(amount);
      await form.locator('[name="reason"]').fill("Referência sintética");
      await form
        .getByRole("button", { name: "Salvar referência", exact: true })
        .click();
      await page.locator("#opening-dialog").waitFor({ state: "hidden" });
      await panel
        .getByRole("button", { name: "Corrigir referência", exact: true })
        .waitFor();
    }
    await page.locator("#new-transfer").click();
    const form = page.locator("#transfer-form");
    await form
      .locator('[name="source_account_id"]')
      .selectOption({ label: "Principal" });
    await form
      .locator('[name="destination_account_id"]')
      .selectOption({ label: "Reserva" });
    await form.locator('[name="date"]').fill("2026-11-03");
    await form.locator('[name="amount"]').fill("125,34");
    await form.locator('[name="description"]').fill("Reserva do mês");
    await form
      .getByRole("button", { name: "Salvar transferência", exact: true })
      .click();
    await page.locator("#transfer-dialog").waitFor({ state: "hidden" });
    await page
      .locator("#transfer-list")
      .getByRole("button", { name: "Reverter transferência", exact: true })
      .waitFor();
    const report = await (
      await context.request.get(base + "/api/balances?as_of=2026-11-30")
    ).json();
    assert.deepEqual(
      report.accounts.map((a) => a.balance_cents),
      [87466, 12534],
    );
    assert.equal(report.total_cents, 100000);
    await page.screenshot({
      path: "artifacts/balances-desktop.png",
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({
      path: "artifacts/balances-mobile.png",
      fullPage: true,
    });
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    await page
      .locator("#transfer-list")
      .getByRole("button", { name: "Reverter transferência", exact: true })
      .click();
    await page
      .locator('#reverse-transfer-form [name="date"]')
      .fill("2026-11-04");
    await page
      .getByRole("button", { name: "Confirmar reversão", exact: true })
      .click();
    await page.locator("#reverse-transfer-dialog").waitFor({ state: "hidden" });
    await page.getByText("Revertida em 04/11/2026", { exact: true }).waitFor();
    assert.deepEqual(
      (
        await (
          await context.request.get(base + "/api/balances?as_of=2026-11-30")
        ).json()
      ).accounts.map((a) => a.balance_cents),
      [100000, 0],
    );
    // Expirar sessão enquanto um formulário contém dados deve apagar valores e lista.
    await page
      .locator(".account-balance")
      .first()
      .getByRole("button", { name: "Corrigir referência", exact: true })
      .click();
    assert.equal(
      (
        await context.request.delete(base + "/api/privacy/data", {
          headers: { ...headers, "X-Confirm-Delete": "EXCLUIR" },
        })
      ).status(),
      200,
    );
    csrf = null;
    await page
      .getByRole("button", { name: "Salvar referência", exact: true })
      .click();
    // Preencher motivo para que validação HTML permita a requisição que verifica sessão.
    if (await page.locator("#opening-dialog").isVisible()) {
      await page
        .locator('#opening-form [name="reason"]')
        .fill("Sessão encerrada");
      await page
        .getByRole("button", { name: "Salvar referência", exact: true })
        .click();
    }
    await page.locator("#opening-dialog").waitFor({ state: "hidden" });
    assert.equal(
      await page.locator('#opening-form [name="amount"]').inputValue(),
      "",
    );
    assert.equal(await page.locator("#balance-list").textContent(), "");
    console.log(
      "PASS: referências, transferência, conservação/reversão de saldos, desktop/mobile e limpeza ao encerrar sessão.",
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
    await context.close();
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
