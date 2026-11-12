// Composição e navegação do dashboard com respostas sintéticas, sem mutações reais.
const engines = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("node:fs");
const assert = require("node:assert/strict");
(async () => {
  const engine = process.env.BROWSER_ENGINE || "chromium";
  const browser = await engines[engine].launch({ headless: true });
  const page = await browser.newPage({ locale: "pt-BR", reducedMotion: "reduce" });
  const base = process.env.APP_URL || "http://localhost:8000";
  let cardCount = 3, posts = 0, withBills = true;
  const errors = [], audits = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const cards = ["Principal", "Reserva", "Viagem"].map((name, i) => ({ id: `card-${i}`, name, due_day: 10 + i, version: 1 }));
  await page.route("**/api/**", (route) => {
    const url = new URL(route.request().url());
    if (route.request().method() !== "GET") posts++;
    const month = url.searchParams.get("month") || new Date().toISOString().slice(0, 7);
    const bills = cards.slice(0, 2).map((card, i) => ({ id: `bill-${i}`, card_id: card.id, month, due_date: `${month}-${10 + i}`, status: i ? "open" : "closed", total_cents: 20000, paid_cents: i ? 0 : 5000, remaining_cents: i ? 20000 : 15000, pending: 0, charges: [], payments: [] }));
    const data = url.pathname === "/api/me" ? { csrf: "synthetic-dashboard-only" }
      : url.pathname === "/api/cards" ? cards.slice(0, cardCount)
      : url.pathname === "/api/statements" ? cardCount && withBills ? bills.slice(0, cardCount) : []
      : url.pathname === "/api/accounts" ? [{ id: "account", name: "Conta", version: 1 }]
      : url.pathname === "/api/balances" ? { total_cents: 296500, known_subtotal_cents: 296500, unknown_accounts: 0, unassigned_transactions: 0, accounts: [{ id: "account", name: "Conta", balance_cents: 296500, opening_date: "2026-11-01", opening_cents: 296500, version: 1 }] }
      : url.pathname === "/api/transfers" ? { items: [], has_more: false }
      : { income_cents: 650000, expense_cents: 225560, balance_cents: 424440, cash_balance_cents: 424440, card_payment_cents: 0, categories: { Moradia: 180000, Alimentação: 45560 }, insights: [], transactions: [], goals: [] };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data) });
  });
  try {
    await page.goto(base);
    await page.waitForFunction(() => document.querySelector("main").dataset.renderedMonth && document.querySelector("main").getAttribute("aria-busy") === "false");
    await page.evaluate(fs.readFileSync(process.env.AXE_PATH || require.resolve("axe-core/axe.min.js"), "utf8"));
    assert.equal(await page.locator("#overview-cards .credit-access").count(), 1);
    assert.equal(await page.locator(".card-choice").count(), 2);
    assert.match(await page.locator("#overview-card-count").textContent(), /2 de 3/);
    assert.match(await page.locator("#overview-cards .credit-remaining").textContent(), /R\$\s*150,00/);
    assert.match(await page.locator("#overview-account-balance").textContent(), /2\.965,00/);
    for (const width of [320, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      for (const theme of ["light", "dark"]) {
        await page.locator("#theme-preference").selectOption(theme);
        await page.waitForFunction(() => !document.documentElement.classList.contains("theme-changing"));
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${width}/${theme}: overflow`);
        assert(await page.locator("#overview-new-card,.card-choice").evaluateAll((nodes) => nodes.every((node) => node.getBoundingClientRect().height >= 48)));
        assert(await page.locator(".card-facts > div:nth-child(2) dd").evaluate((node) => getComputedStyle(node).whiteSpace === "nowrap" && node.scrollWidth <= node.clientWidth + 1));
        if (width < 768) {
          assert(await page.locator(".dashboard-metrics .metric > strong").evaluateAll((nodes) => nodes.every((node) => getComputedStyle(node).whiteSpace === "nowrap" && node.scrollWidth <= node.clientWidth + 1)));
        }
        const result = await page.evaluate(() => axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"] } }));
        const violations = result.violations.map((v) => ({ id: v.id, targets: v.nodes.map((node) => node.target) }));
        audits.push({ width, theme, violations });
        assert.deepEqual(violations, [], `${width}/${theme}`);
        if ([390, 1440].includes(width)) {
          await page.screenshot({ path: `artifacts/dashboard-auth-${engine}-${width}-${theme}.png`, fullPage: true });
          await page.locator(".overview-card-panel").screenshot({ path: `artifacts/card-reference-${engine}-${width}-${theme}.png` });
        }
      }
    }
    await page.locator("#overview-cards .credit-access").first().focus();
    await page.keyboard.press("Enter");
    assert.equal(await page.locator(":focus").getAttribute("id"), "statement-bill-0");
    assert.equal(posts, 0, "Consultar cartão não deve criar fatura ou pagamento");
    await page.locator('.nav[data-view="overview"]').click();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator(".card-choice").nth(1).focus();
    await page.keyboard.press("Enter");
    assert.equal(await page.locator(".card-choice").nth(1).getAttribute("aria-pressed"), "true");
    assert.match(await page.locator(".card-facts").textContent(), /Em revisão/);
    assert.equal(await page.locator(".card-facts .credit-remaining").count(), 0);
    assert.equal(await page.locator(":focus").getAttribute("class"), "card-choice");
    await page.locator("#overview-cards .credit-access").focus();
    await page.keyboard.press("Enter");
    assert.equal(await page.locator(":focus").getAttribute("id"), "statement-bill-1");
    assert.equal(posts, 0);
    await page.locator('.nav[data-view="overview"]').click();
    await page.locator(".cash-details > summary").click();
    assert(await page.locator("#cash-result").isVisible());
    await page.locator(".balance-help > summary").click();
    assert.match(await page.locator(".balance-help").textContent(), /sem consulta bancária/);
    await page.locator(".overview-secondary > summary").click();
    assert(await page.locator("#goal-preview").isVisible());
    cardCount = 0;
    await page.locator("#month").dispatchEvent("change");
    await page.waitForFunction(() => document.querySelector("main").getAttribute("aria-busy") === "false");
    assert.match(await page.locator("#overview-cards").textContent(), /Cadastrar cartão/);
    cardCount = 1;
    withBills = false;
    await page.locator("#month").dispatchEvent("change");
    await page.waitForFunction(() => document.querySelector("main").getAttribute("aria-busy") === "false");
    assert.match(await page.locator("#overview-cards").textContent(), /Sem fatura/);
    await page.locator("#overview-cards .credit-access").click();
    assert(await page.locator(":focus").evaluate((node) => node.dataset.entityId === "card-0"));
    assert.equal(posts, 0, "Cartão sem fatura deve abrir o cadastro existente sem criar registros");
    await page.locator('.nav[data-view="overview"]').click();
    await page.locator("#overview-new-card").click();
    await page.locator("#setup-dialog").waitFor();
    assert.equal(await page.locator("#setup-title").textContent(), "Cadastrar cartão");
    assert.equal(posts, 0, "Adicionar cartão deve abrir o formulário, sem cadastro automático");
    await page.keyboard.press("Escape");
    assert.deepEqual(errors, []);
    fs.writeFileSync(`artifacts/dashboard-${engine}-results.json`, JSON.stringify({ audits, runtimeErrors: errors, posts }, null, 2));
    console.log(`PASS: dashboard ${engine}, 10 auditorias axe, 5 larguras/dois temas, centavos inteiros, cartão por teclado sem POST, detalhes acessíveis e vazio.`);
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
