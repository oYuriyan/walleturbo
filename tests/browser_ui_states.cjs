// Estados de apresentação com respostas sintéticas; regras financeiras são testadas separadamente.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const { confirmNext } = require("./ui_helpers.cjs");
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, locale: "pt-BR", colorScheme: "light", reducedMotion: "reduce" });
  const base = process.env.APP_URL || "http://localhost:8000";
  const output = "artifacts/redesign-states";
  fs.mkdirSync(output, { recursive: true });
  let mode = "empty", hold = null, postRelease = null, posts = 0;
  const errors = [], checks = [], audits = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const reply = (data, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
    if (url.pathname === "/api/me") return reply({ csrf: "synthetic-ui-only" });
    if (url.pathname === "/api/dashboard") {
      if (mode === "loading") await new Promise((resolve) => { hold = resolve; });
      if (mode === "error") return reply({ detail: "Consulta sintética indisponível" }, 503);
      return reply({ income_cents: 0, expense_cents: mode === "credits" ? 5000 : 0, balance_cents: mode === "credits" ? -5000 : 0, cash_balance_cents: 0, card_payment_cents: 0, categories: mode === "credits" ? { Alimentação: 10000, Compras: -5000 } : {}, insights: [], transactions: [], goals: [] });
    }
    if (url.pathname === "/api/accounts") return reply(mode === "empty" ? [] : [{ id: "a", name: "Conta sintética", version: 1, archived: false }, { id: "b", name: "Sem referência", version: 1, archived: false }]);
    if (url.pathname === "/api/balances") {
      const partial = mode === "partial";
      return reply({ total_cents: partial ? null : 0, known_subtotal_cents: partial ? 10000 : 0, unknown_accounts: partial ? 1 : 0, unassigned_transactions: partial ? 1 : 0, accounts: mode === "empty" ? [] : [{ id: "a", name: "Conta sintética", balance_cents: partial ? 10000 : 0, opening_cents: 0, opening_date: "2026-11-01", version: 1 }, { id: "b", name: "Sem referência", balance_cents: partial ? null : 0, opening_cents: partial ? null : 0, opening_date: partial ? null : "2026-11-01", version: partial ? 0 : 1 }] });
    }
    if (url.pathname === "/api/transfers") return reply({ items: [], has_more: false });
    if (url.pathname === "/api/transactions" && route.request().method() === "POST") {
      posts++;
      assert.equal(route.request().postDataJSON().amount_cents, 123456);
      await new Promise((resolve) => { postRelease = resolve; });
      return reply({ detail: [{ loc: ["body", "amount_cents"], msg: "Erro sintético de valor" }] }, 422);
    }
    return reply([]);
  });
  const ready = () => page.waitForFunction(() => document.querySelector("main").getAttribute("aria-busy") === "false" && document.querySelector("main").dataset.renderedMonth);
  const audit = async (label) => {
    const result = await page.evaluate(() => axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"] } }));
    const violations = result.violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) }));
    audits.push({ label, violations });
    assert.deepEqual(violations, [], label);
  };
  try {
    await page.goto(base);
    await ready();
    await page.evaluate(fs.readFileSync(process.env.AXE_PATH || require.resolve("axe-core/axe.min.js"), "utf8"));
    assert.match(await page.locator("#overview-account-balance").textContent(), /Cadastre sua primeira conta/);
    checks.push("Sem contas não é apresentado como saldo disponível zero");
    mode = "partial";
    await page.locator("#month").dispatchEvent("change");
    await ready();
    assert.equal(await page.locator("#overview-account-balance").textContent(), "Saldo total indisponível");
    assert.match(await page.locator("#overview-balance-context").textContent(), /Subtotal conhecido: R\$\s*100,00/);
    await audit("saldo-parcial-claro");
    await page.screenshot({ path: `${output}/partial.png`, fullPage: true });
    checks.push("Cobertura parcial mantém subtotal separado de total");
    mode = "loading";
    await page.locator("#month").dispatchEvent("change");
    await page.waitForFunction(() => document.querySelector("main").getAttribute("aria-busy") === "true");
    assert(await page.locator("#loading-status").isVisible());
    assert(await page.locator("#overview").evaluate((node) => node.inert));
    await audit("carregando");
    mode = "ready";
    while (!hold) await new Promise((resolve) => setTimeout(resolve, 10));
    hold();
    await ready();
    assert.match(await page.locator("#overview-account-balance").textContent(), /R\$\s*0,00/);
    checks.push("Carregamento anuncia estado e bloqueia ações sobre conteúdo anterior; zero completo é zero");
    mode = "error";
    await page.locator("#month").dispatchEvent("change");
    await page.locator("#retry-load").waitFor();
    assert.match(await page.locator("#overview-account-balance").textContent(), /Não foi possível/);
    await audit("consulta-com-erro");
    mode = "ready";
    await page.locator("#retry-load").click();
    await ready();
    checks.push("Falha de consulta oculta valor anterior e permite recuperação");
    mode = "credits";
    await page.locator("#month").dispatchEvent("change");
    await ready();
    assert.equal(await page.locator("#categories progress").count(), 0);
    assert.match(await page.locator("#categories").textContent(), /sem percentuais/);
    await audit("categorias-com-creditos");
    checks.push("Categoria credora usa valores líquidos e evita barras/percentuais enganosos");
    await page.locator('#overview-quick-actions .button[data-action="new-entry"]').click();
    await page.locator('#entry-form [name="description"]').fill("Teste de estado ocupado");
    await page.locator('#entry-form [name="amount"]').fill("1.234,56");
    const button = page.locator('#entry-form button[type="submit"]');
    const before = await button.boundingBox();
    await button.click();
    await page.waitForFunction(() => !!document.querySelector('#entry-form[aria-busy="true"]'), null, { timeout: 5000 });
    const during = await button.boundingBox();
    assert.equal(Math.round(before.width), Math.round(during.width));
    await page.locator('#entry-form [name="description"]').press("Enter");
    assert.equal(posts, 1);
    await audit("salvamento-ocupado");
    while (!postRelease) await new Promise((resolve) => setTimeout(resolve, 10));
    postRelease();
    await page.locator("#entry-dialog .dialog-error").waitFor();
    assert.equal(await page.locator('#entry-form [name="amount"]').getAttribute("aria-invalid"), "true");
    assert.equal(await page.locator('#entry-form [name="amount"]').inputValue(), "1.234,56");
    await audit("erro-de-campo");
    await confirmNext(page, () => page.keyboard.press("Escape"));
    await page.locator("#entry-dialog").waitFor({ state: "hidden" });
    checks.push("Estado ocupado preserva largura, bloqueia envio duplicado e erro 422 mantém valor/associação ao campo");
    await page.locator("#more-navigation-button").focus();
    await page.keyboard.press("Space");
    await page.locator('.nav[data-view="goals"]').focus();
    await page.keyboard.press("Enter");
    assert.equal(await page.locator(":focus").getAttribute("id"), "page-title");
    assert.equal(await page.locator("#page-title").textContent(), "Minhas metas");
    await page.locator(".skip-link").focus();
    await page.keyboard.press("Enter");
    assert.equal(await page.locator("#page-title").textContent(), "Minhas metas");
    assert.equal(await page.locator(":focus").getAttribute("id"), "page-title");
    await page.locator("#theme-preference").selectOption("system");
    await page.emulateMedia({ colorScheme: "dark" });
    await page.waitForFunction(() => document.body.classList.contains("dark"));
    await page.emulateMedia({ colorScheme: "light" });
    await page.waitForFunction(() => !document.body.classList.contains("dark"));
    checks.push("Mais e destino operáveis por teclado; tema Sistema acompanha mudança de preferência");
    assert.deepEqual(errors, []);
    fs.writeFileSync(`${output}/results.json`, JSON.stringify({ browser: browser.version(), checks, audits, runtimeErrors: errors }, null, 2));
    console.log(`PASS: ${checks.length} grupos de estados, ${audits.length} auditorias axe sem violações; zero erros JS.`);
  } catch (error) {
    await page.screenshot({ path: `${output}/failure.png`, fullPage: true });
    fs.writeFileSync(`${output}/failure.json`, JSON.stringify({ message: error.message, posts, errors, form: await page.locator("#entry-form").evaluate((node) => ({ text: node.textContent, fields: [...node.elements].map((field) => ({ name: field.name, value: field.value, valid: field.validity.valid, disabled: field.disabled })) })) }, null, 2));
    throw error;
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
