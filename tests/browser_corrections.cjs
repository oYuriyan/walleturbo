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
    const card = await (
      await context.request.post(base + "/api/cards", {
        headers,
        data: { name: "Cartão sintético", due_day: 10 },
      })
    ).json();
    const body = {
      request_id: randomUUID(),
      card_id: card.id,
      first_month: "2026-11",
      date: "2026-10-28",
      description: "Notebook sintético",
      amount_cents: 10001,
      installments: 3,
      kind: "expense",
      category: "Compras",
      reviewed: true,
    };
    assert.equal(
      (
        await context.request.post(base + "/api/card-purchases", {
          headers,
          data: body,
        })
      ).status(),
      201,
    );
    await page.goto(base);
    await page.getByText("Conta conectada", { exact: true }).waitFor();
    await page.locator('[data-view="finance"]').click();
    await page
      .getByRole("button", { name: "Corrigir compra", exact: true })
      .click();
    const form = page.locator("#correction-form"),
      dialog = page.locator("#correction-dialog");
    await form.locator('[name="amount"]').fill("200,03");
    await form.locator('[name="installments"]').fill("2");
    await form.locator('[name="first_month"]').fill("2026-12");
    await form.locator('[name="reason"]').fill("Conferido no comprovante");
    await form
      .getByRole("button", { name: "Conferir alterações", exact: true })
      .click();
    await page.locator("#confirm-correction").waitFor({ state: "visible" });
    await page
      .getByText("2026-12: R$ 33,34 → R$ 100,02", { exact: true })
      .waitFor();
    await page.screenshot({
      path: "artifacts/corrections-mobile.png",
      fullPage: true,
    });
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    const refreshed = page.waitForResponse(
      (r) => r.url().includes("/api/transfers?") && r.status() === 200,
    );
    await page.locator("#confirm-correction").click();
    await dialog.waitFor({ state: "hidden" });
    await refreshed;
    const path = base + "/api/card-operations/" + body.request_id;
    let data = await (await context.request.get(path)).json();
    assert.deepEqual(
      data.charges.map((c) => c.amount_cents),
      [10002, 10001],
    );
    assert.equal(
      (
        await (
          await context.request.post(base + "/api/card-purchases", {
            headers,
            data: body,
          })
        ).json()
      ).length,
      2,
    );
    const next = page.waitForResponse(
      (r) => r.url().includes("/api/transfers?") && r.status() === 200,
    );
    await page.locator("#month").fill("2026-12");
    await page.locator("#month").dispatchEvent("change");
    await next;
    await page
      .getByRole("button", { name: "Corrigir compra", exact: true })
      .click();
    await form.locator('[name="reason"]').fill("Outra conferência");
    await form
      .getByRole("button", { name: "Conferir alterações", exact: true })
      .click();
    await page
      .getByText("2026-12: R$ 100,02 → R$ 100,02", { exact: true })
      .waitFor();
    const other = {
      ...body,
      request_id: randomUUID(),
      expected_revision: data.revision,
      amount_cents: 31000,
      installments: 2,
      first_month: "2026-12",
      description: "Outra sessão",
      reason: "Atualização concorrente",
    };
    assert.equal(
      (await context.request.put(path, { headers, data: other })).status(),
      200,
    );
    await page.locator("#confirm-correction").click();
    await dialog
      .getByText(
        "Compra alterada em outra sessão. Recarregue e confira a prévia novamente.",
        { exact: true },
      )
      .waitFor();
    await page.locator("#reload-correction").click();
    await page.waitForFunction(
      () =>
        document.querySelector('#correction-form [name="description"]')
          .value === "Outra sessão",
    );
    const cancelled = {
      ...body,
      request_id: randomUUID(),
      installments: 1,
      first_month: "2028-04",
    };
    assert.equal(
      (
        await context.request.post(base + "/api/card-purchases", {
          headers,
          data: cancelled,
        })
      ).status(),
      201,
    );
    const cancelledRevision = (
      await (
        await context.request.get(
          base + "/api/card-operations/" + cancelled.request_id,
        )
      ).json()
    ).revision;
    assert.equal(
      (
        await context.request.delete(
          base +
            "/api/card-operations/" +
            cancelled.request_id +
            "?expected_revision=" +
            cancelledRevision,
          { headers },
        )
      ).status(),
      204,
    );
    assert.equal(
      (
        await context.request.post(base + "/api/card-purchases", {
          headers,
          data: cancelled,
        })
      ).status(),
      409,
    );
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
      .getByRole("button", { name: "Conferir alterações", exact: true })
      .click();
    await dialog.waitFor({ state: "hidden" });
    assert.equal(await form.locator('[name="description"]').inputValue(), "");
    assert.equal(await form.locator('[name="operation_id"]').inputValue(), "");
    console.log(
      "PASS: correção integral mobile, prévia, centavos, conflito/recarga, reenvio cancelado e limpeza após sessão encerrada.",
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
