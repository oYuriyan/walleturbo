// Roteiro financeiro para uma sessão autenticada; valores exclusivamente sintéticos.
const assert = require("assert/strict");
const { randomUUID } = require("crypto");
const base = process.env.APP_URL || "http://localhost:8000";
async function request(
  context,
  csrf,
  path,
  method = "GET",
  data,
  expectedStatus,
) {
  const options = {
    method,
    headers: { Origin: base, "X-CSRF-Token": csrf },
    ...(data === undefined ? {} : { data }),
  };
  let response = await context.request.fetch(base + path, options);
  if (response.status() === 429) {
    const delay = Number(response.headers()["retry-after"]);
    assert(delay > 0 && delay <= 60);
    await new Promise((resolve) => setTimeout(resolve, (delay + 1) * 1000));
    response = await context.request.fetch(base + path, options);
  }
  if (expectedStatus !== undefined)
    assert.equal(response.status(), expectedStatus, `Etapa ${method} ${path}`);
  else
    assert(response.ok(), `Etapa ${method} ${path}: HTTP ${response.status()}`);
  return response.status() === 204 ? null : response.json();
}
async function buildJourney(context, page, csrf) {
  const call = (path, method, data) =>
    request(context, csrf, path, method, data);
  const accounts = [];
  for (const name of ["Principal integrada", "Reserva integrada"])
    accounts.push(await call("/api/accounts", "POST", { name }));
  for (const [index, amount_cents] of [100000, 0].entries())
    await call(`/api/accounts/${accounts[index].id}/opening`, "PUT", {
      request_id: randomUUID(),
      expected_version: 0,
      date: "2026-11-01",
      amount_cents,
      reason: "Referência da jornada sintética",
    });
  await call("/api/transactions", "POST", {
    request_id: randomUUID(),
    account_id: accounts[0].id,
    date: "2026-11-02",
    description: "Receita integrada",
    amount_cents: 200000,
    kind: "income",
    category: "Renda",
    reviewed: true,
  });
  const csv = {
    content:
      "data;descricao;valor;tipo\n2026-11-03;Mercado integrado;20,00;despesa\n",
    account_id: accounts[0].id,
  };
  assert.equal((await call("/api/import/confirm", "POST", csv)).created, 1);
  let exported = await call("/api/privacy/export");
  const expense = exported.transactions.find((row) => row.kind === "expense");
  await call("/api/transactions/" + expense.id, "PUT", {
    request_id: randomUUID(),
    expected_version: expense.version,
    account_id: accounts[0].id,
    date: expense.date,
    description: "Mercado conferido",
    amount_cents: 2500,
    kind: "expense",
    category: "Alimentação",
    reviewed: true,
    reason: "Valor conferido no comprovante",
  });
  assert.equal((await call("/api/import/confirm", "POST", csv)).duplicates, 1);
  const transfer = {
    request_id: randomUUID(),
    source_account_id: accounts[0].id,
    destination_account_id: accounts[1].id,
    date: "2026-11-04",
    amount_cents: 10000,
    description: "Reserva própria",
  };
  await call("/api/transfers", "POST", transfer);
  await call("/api/transfers", "POST", transfer);
  const card = await call("/api/cards", "POST", {
    name: "Cartão integrado",
    due_day: 10,
  });
  const purchase = {
    request_id: randomUUID(),
    card_id: card.id,
    first_month: "2026-11",
    date: "2026-11-05",
    description: "Compra integrada",
    amount_cents: 10000,
    installments: 2,
    kind: "expense",
    category: "Compras",
    reviewed: true,
  };
  const rows = await call("/api/card-purchases", "POST", purchase);
  assert.deepEqual(
    (await call("/api/card-purchases", "POST", purchase)).map((row) => row.id),
    rows.map((row) => row.id),
  );
  await call("/api/card-purchases", "POST", {
    ...purchase,
    request_id: randomUUID(),
    description: "Estorno integrado",
    amount_cents: 1000,
    installments: 1,
    kind: "refund",
  });
  const bill = await call("/api/statements/" + rows[0].statement_id);
  assert.equal(bill.total_cents, 4000);
  await call(`/api/statements/${bill.id}/close`, "POST", {
    expected_cents: 4000,
    expected_revision: bill.revision,
  });
  const payment = {
    request_id: randomUUID(),
    account_id: accounts[0].id,
    amount_cents: 1000,
    date: "2026-11-10",
  };
  await call(`/api/statements/${bill.id}/payments`, "POST", payment);
  await call(`/api/statements/${bill.id}/payments`, "POST", payment);
  assert.equal(
    (await call("/api/statements/" + bill.id)).remaining_cents,
    3000,
  );
  await call("/api/goals", "POST", {
    name: "Reserva integrada",
    target_cents: 100000,
    saved_cents: 10000,
    deadline: "2027-12-31",
  });
  await call("/api/planning/2026-11/budget", "PUT", {
    expected_version: 0,
    category: "Alimentação",
    amount_cents: 3000,
  });
  let plan = await call("/api/planning/2026-11");
  await call("/api/planning/2026-11/plan", "PUT", {
    expected_version: plan.version,
    expected_records_revision: plan.records_revision,
    records_complete: true,
    buffer_cents: 10000,
  });
  plan = await call("/api/planning/2026-11");
  assert.equal(plan.capacity_cents, 183500);
  assert.equal(
    plan.budgets.find((row) => row.category === "Alimentação").remaining_cents,
    500,
  );
  const balances = await call("/api/balances?as_of=2026-11-30");
  assert.equal(balances.total_cents, 296500);
  assert.equal(
    balances.accounts.find((row) => row.id === accounts[0].id).balance_cents,
    286500,
  );
  assert.equal(
    balances.accounts.find((row) => row.id === accounts[1].id).balance_cents,
    10000,
  );
  const report = await call("/api/dashboard?month=2026-11");
  assert.equal(report.balance_cents, 193500);
  assert.equal(report.cash_balance_cents, 196500);
  assert.equal(report.expense_cents, 6500);
  assert.equal(
    (await call("/api/dashboard?month=2026-12")).expense_cents,
    5000,
  );
  exported = await call("/api/privacy/export");
  assert.equal(exported.accounts.length, 2);
  assert.equal(exported.goals.length, 1);
  assert.equal(exported.transactions.length, 2);
  assert.equal(exported.card_charges.length, 3);
  assert.equal(exported.statement_payments.length, 1);
  assert.equal(exported.transfers.length, 1);
  let throttled = false,
    retryAfter = 60;
  const observe = (response) => {
    if (
      response.url().startsWith(base + "/api/") &&
      response.status() === 429
    ) {
      throttled = true;
      retryAfter = Number(response.headers()["retry-after"]);
    }
  };
  page.on("response", observe);
  try {
    const show = async () => {
      await page.goto(base);
      await page
        .getByText("Conta conectada", { exact: true })
        .waitFor({ timeout: 8000 });
      await page.locator("#month").fill("2026-11");
      await page.locator("#month").blur();
      await page.waitForFunction(
        () => /1\.935,00/.test(document.querySelector("#balance").textContent),
        null,
        { timeout: 8000 },
      );
    };
    try {
      await show();
    } catch (error) {
      if (!throttled) throw error;
      assert(retryAfter > 0 && retryAfter <= 60);
      await new Promise((resolve) =>
        setTimeout(resolve, (retryAfter + 1) * 1000),
      );
      await show();
    }
    assert.match(await page.locator("#expense").textContent(), /65,00/);
    assert.match(await page.locator("#cash-result").textContent(), /1\.965,00/);
  } finally {
    page.off("response", observe);
  }
  return {
    exported,
    accountId: accounts[0].id,
    entryId: expense.id,
    billId: bill.id,
  };
}
module.exports = { buildJourney, request };
