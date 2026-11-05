const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("fs"),
  assert = require("assert/strict"),
  { randomUUID } = require("crypto");
const base = "http://localhost:8000";
(async () => {
  const seed = JSON.parse(fs.readFileSync(0, "utf8"));
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox"],
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
  const page = await context.newPage();
  let headers;
  try {
    headers = {
      Origin: base,
      "X-CSRF-Token": (
        await (await context.request.get(base + "/api/me")).json()
      ).csrf,
    };
    const accounts = [];
    for (const [name, amount] of [
      ["Principal", 10000],
      ["Reserva", 20000],
    ]) {
      const a = await (
        await context.request.post(base + "/api/accounts", {
          headers,
          data: { name },
        })
      ).json();
      accounts.push(a);
      assert.equal(
        (
          await context.request.put(base + `/api/accounts/${a.id}/opening`, {
            headers,
            data: {
              request_id: randomUUID(),
              date: "2026-11-01",
              expected_version: 0,
              amount_cents: amount,
              reason: "Saldo sintético",
            },
          })
        ).status(),
        200,
      );
    }
    const card = await (
      await context.request.post(base + "/api/cards", {
        headers,
        data: { name: "Cartão sintético", due_day: 10 },
      })
    ).json();
    assert.equal(
      (
        await context.request.post(base + "/api/card-purchases", {
          headers,
          data: {
            request_id: randomUUID(),
            card_id: card.id,
            first_month: "2026-11",
            date: "2026-10-28",
            description: "Compra sintética",
            amount_cents: 15000,
            installments: 1,
            category: "Compras",
            reviewed: true,
          },
        })
      ).status(),
      201,
    );
    const statement = (
      await (
        await context.request.get(base + "/api/statements?month=2026-11")
      ).json()
    )[0];
    assert.equal(
      (
        await context.request.post(
          base + `/api/statements/${statement.id}/close`,
          { headers, data: { expected_cents: 15000 } },
        )
      ).status(),
      200,
    );
    let payment;
    for (const amount of [6000, 3000]) {
      const response = await context.request.post(
        base + `/api/statements/${statement.id}/payments`,
        {
          headers,
          data: {
            request_id: randomUUID(),
            account_id: accounts[0].id,
            date: "2026-11-03",
            amount_cents: amount,
          },
        },
      );
      assert.equal(response.status(), 201);
      if (amount === 6000) payment = await response.json();
    }
    await page.goto(base);
    await page.getByText("Conta conectada", { exact: true }).waitFor();
    await page.locator('[data-view="finance"]').click();
    const form = page.locator("#payment-correction-form"),
      dialog = page.locator("#payment-correction-dialog");
    await page
      .locator(".payment-row")
      .filter({ hasText: /60,00/ })
      .getByRole("button", { name: "Corrigir pagamento", exact: true })
      .click();
    await form
      .locator('[name="account_id"]')
      .selectOption({ label: "Reserva" });
    await form.locator('[name="date"]').fill("2026-12-02");
    await form.locator('[name="amount"]').fill("40,00");
    await form.locator('[name="as_of"]').fill("2026-12-31");
    await form.locator('[name="reason"]').fill("Conferido no comprovante");
    await form
      .getByRole("button", { name: "Conferir pagamento", exact: true })
      .click();
    await page
      .getByText("Principal: R$ 10,00 → R$ 70,00.", { exact: true })
      .waitFor();
    await page
      .getByText("Reserva: R$ 200,00 → R$ 160,00.", { exact: true })
      .waitFor();
    await page.locator("#confirm-payment-correction").scrollIntoViewIfNeeded();
    await dialog.screenshot({
      path: "artifacts/payment-corrections-mobile-preview.png",
    });
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    const refreshed = page.waitForResponse(
      (r) => r.url().includes("/api/transfers?") && r.status() === 200,
    );
    await page.locator("#confirm-payment-correction").click();
    await dialog.waitFor({ state: "hidden" });
    await refreshed;
    const path = base + "/api/statement-payments/" + payment.id;
    let data = (await (await context.request.get(path)).json()).payment;
    assert.equal(data.version, 2);
    assert.equal(data.account_id, accounts[1].id);
    assert.equal(data.amount_cents, 4000);
    const row = page.locator(".payment-row").filter({ hasText: /40,00/ });
    await row
      .getByRole("button", { name: "Corrigir pagamento", exact: true })
      .click();
    await form.locator('[name="reason"]').fill("Revisão local");
    await form
      .getByRole("button", { name: "Conferir pagamento", exact: true })
      .click();
    await page
      .getByText("Prévia do registro corrigido", { exact: true })
      .waitFor();
    assert.equal(
      (
        await context.request.put(path, {
          headers,
          data: {
            request_id: randomUUID(),
            account_id: accounts[1].id,
            date: "2026-12-02",
            amount_cents: 4500,
            expected_version: 2,
            as_of: "2026-12-31",
            reason: "Outra sessão",
          },
        })
      ).status(),
      200,
    );
    await page.locator("#confirm-payment-correction").click();
    await dialog
      .getByText(
        "Pagamento alterado em outra sessão. Recarregue e confira a prévia novamente.",
        { exact: true },
      )
      .waitFor();
    await page.locator("#reload-payment-correction").click();
    await page.waitForFunction(
      () =>
        document.querySelector('#payment-correction-form [name="amount"]')
          .value === "45,00",
    );
    await dialog.getByRole("button", { name: "Fechar", exact: true }).click();
    page.once("dialog", (d) => d.accept());
    await row
      .getByRole("button", { name: "Estornar registro", exact: true })
      .click();
    await page
      .getByText(
        "Pagamento alterado em outra sessão. Atualize antes de remover.",
        { exact: true },
      )
      .waitFor();
    await row
      .getByRole("button", { name: "Corrigir pagamento", exact: true })
      .click();
    await form.locator('[name="reason"]').fill("Sessão encerrada");
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
      .getByRole("button", { name: "Conferir pagamento", exact: true })
      .click();
    await dialog.waitFor({ state: "hidden" });
    assert.equal(await form.locator('[name="payment_id"]').inputValue(), "");
    assert.equal(await form.locator('[name="reason"]').inputValue(), "");
    assert.equal(await form.locator('[name="account_id"] option').count(), 0);
    console.log(
      "PASS: correção de pagamento mobile com prévia de saldos, confirmação, conflito/recarga, exclusão obsoleta e limpeza após sessão encerrada.",
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
