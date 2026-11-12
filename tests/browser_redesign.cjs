const engines = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const { confirmNext, respectRateLimits } = require("./ui_helpers.cjs");

(async () => {
  const engine = process.env.BROWSER_ENGINE || "chromium";
  const authenticated = process.env.UI_AUTH === "1";
  const mode = authenticated ? "auth" : "demo";
  const base = process.env.APP_URL || "http://localhost:8000";
  const output = `artifacts/redesign-${engine}-${mode}`;
  fs.mkdirSync(output, { recursive: true });
  const browser = await engines[engine].launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: "pt-BR", timezoneId: "America/Sao_Paulo", colorScheme: "light", reducedMotion: "reduce" });
  const page = await context.newPage();
  page.setDefaultTimeout(12000);
  await respectRateLimits(context, page);
  const errors = [], audits = [], checks = [];
  page.on("pageerror", (error) => errors.push(error.message));
  let csrf;
  const ready = () => page.waitForFunction(() => document.querySelector("main").getAttribute("aria-busy") === "false");
  const nav = async (view) => {
    const link = page.locator(`.nav[data-view="${view}"]`);
    if (!(await link.isVisible())) await page.locator("#more-navigation-button").click();
    await link.click();
    if (authenticated && view === "planning") await page.waitForFunction(() => !!document.querySelector("#capacity").textContent);
    await ready();
  };
  const axe = async (label) => {
    await page.waitForFunction(() => !document.documentElement.classList.contains("theme-changing"));
    const result = await page.evaluate(async () => axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"] } }));
    const violations = result.violations.map((v) => ({ id: v.id, impact: v.impact, targets: v.nodes.map((node) => node.target) }));
    audits.push({ label, violations });
    assert.deepEqual(violations, [], label);
  };
  try {
    if (authenticated) {
      const seed = JSON.parse(fs.readFileSync(0, "utf8"));
      await context.addCookies([{ name: "walleturbo_session", value: seed.sid, url: base, httpOnly: true, sameSite: "Lax" }]);
      csrf = (await (await context.request.get(`${base}/api/me`)).json()).csrf;
      await require("./basic_journey.cjs").buildJourney(context, page, csrf);
    } else {
      await page.goto(base);
      await page.keyboard.press("Tab");
      assert.equal(await page.locator(":focus").textContent(), "Ir para o conteúdo");
      await page.keyboard.press("Enter");
      assert.equal(await page.locator(":focus").getAttribute("id"), "page-title");
      await page.locator("#demo").click();
    }
    await ready();
    await page.evaluate(fs.readFileSync(process.env.AXE_PATH || require.resolve("axe-core/axe.min.js"), "utf8"));
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
      for (const theme of ["light", "dark"]) {
        await page.locator("#theme-preference").selectOption(theme);
        for (const view of ["overview", "transactions", "finance", "planning", "goals", "privacy"]) {
          await nav(view);
          assert.equal(await page.locator(":focus").getAttribute("id"), "page-title");
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${width}/${theme}/${view} overflow`);
          await axe(`${width}/${theme}/${view}`);
          await page.screenshot({ path: `${output}/${width}-${theme}-${view}.png`, fullPage: true });
        }
        await nav("transactions");
        await page.locator('#transactions [data-action="new-entry"]').click();
        await axe(`${width}/${theme}/entry`);
        for (let index = 0; index < 16; index++) {
          await page.keyboard.press(index % 3 === 0 ? "Shift+Tab" : "Tab");
          assert(await page.evaluate(() => !!document.activeElement.closest("#entry-dialog")));
        }
        await page.locator('#entry-form [name="description"]').fill(" ");
        await page.locator('#entry-form [name="amount"]').fill("12,34");
        await page.locator('#entry-form button[type="submit"]').click();
        await page.locator("#entry-dialog .dialog-error").waitFor();
        assert.equal(await page.locator(":focus").getAttribute("class"), "dialog-error");
        assert.equal(await page.locator('#entry-form [name="amount"]').inputValue(), "12,34");
        await axe(`${width}/${theme}/entry-error`);
        await page.screenshot({ path: `${output}/${width}-${theme}-error.png`, fullPage: true });
        await page.keyboard.press("Escape");
        await page.locator("#confirm-dialog").waitFor();
        assert.equal(await page.locator(":focus").getAttribute("value"), "cancel");
        await axe(`${width}/${theme}/confirmation`);
        await page.screenshot({ path: `${output}/${width}-${theme}-confirmation.png`, fullPage: true });
        await page.locator("#confirm-dialog [value=cancel]").click();
        assert(await page.locator("#entry-dialog").isVisible());
        await confirmNext(page, () => page.keyboard.press("Escape"));
        await page.locator("#entry-dialog").waitFor({ state: "hidden" });
      }
    }
    checks.push("24 estados de página, 12 estados de formulário/erro/confirmação, Tab/Shift+Tab/Escape e cancelamento sem mutação");
    for (const [width, height] of [[320, 568], [375, 812], [768, 1024], [1024, 768], [844, 390]]) {
      await page.setViewportSize({ width, height });
      for (const view of ["overview", "transactions", "finance", "planning", "goals", "privacy"]) {
        await nav(view);
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${width}x${height}/${view}`);
      }
    }
    checks.push("Seis destinos sem overflow em 320, 375, 768, 1024 e 844x390 paisagem");
    await page.setViewportSize({ width: 1440, height: 1000 });
    await nav("transactions");
    await page.locator("#search").fill("sem correspondência sintética");
    assert.match(await page.locator("#transaction-list").textContent(), /Nenhum lançamento/);
    await page.locator("#clear-search").click();
    assert.equal(await page.locator("#search").inputValue(), "");
    await nav("overview");
    assert.match(page.url(), /#overview\?month=/);
    await nav("transactions");
    await page.goBack();
    await page.locator("#overview").waitFor();
    checks.push("Busca vazia, limpar busca e voltar pelo histórico");

    if (authenticated) {
      assert.match(await page.locator("#overview-account-balance").textContent(), /2\.965,00/);
      let posts = 0;
      page.on("request", (request) => { if (request.method() === "POST" && request.url() === `${base}/api/transactions`) posts++; });
      await page.route("**/api/dashboard?month=*", (route) => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Consulta sintética indisponível" }) }), { times: 1 });
      await page.locator('#overview-quick-actions .button[data-action="new-entry"]').click();
      await page.locator('#entry-form [name="description"]').fill("Salvo antes da falha de consulta");
      await page.locator('#entry-form [name="amount"]').fill("1.234,56");
      await page.locator('#entry-form button[type="submit"]').click();
      await page.locator("#retry-load").waitFor();
      assert.match(await page.locator("#status").textContent(), /Alteração concluída/);
      assert.equal(posts, 1);
      await page.locator("#retry-load").click();
      await ready();
      assert.equal(posts, 1);
      checks.push("POST real com 123456 centavos; falha no GET posterior e retry sem repetir POST");
      await nav("transactions");
      await page.locator("#import-button").click();
      await page.locator("#csv-file").setInputFiles({ name: "redesign.csv", mimeType: "text/csv", buffer: Buffer.from("data;descricao;valor;tipo\n2026-11-04;Importação do redesign;15,90;despesa\n") });
      await page.locator("#import-preview").getByText("Importação do redesign", { exact: true }).waitFor();
      await axe("import-csv-preview");
      await page.screenshot({ path: `${output}/import-preview.png`, fullPage: true });
      // Prévia é inspecionada sem confirmar; regressões especializadas cobrem deduplicação.
      await page.locator("#import-dialog .close").click();
      if (await page.locator("#confirm-dialog").isVisible()) await page.locator("#confirm-dialog [value=confirm]").click();
      checks.push("Importação CSV real: arquivo sintético, prévia e cancelamento");
    } else {
      assert.match(await page.locator("#overview-account-balance").textContent(), /indisponível na demonstração/);
      await nav("finance");
      await page.locator("#new-purchase").click();
      await page.locator('#purchase-form [name="description"]').fill("Compra para validar resultado negativo");
      await page.locator('#purchase-form [name="amount"]').fill("8.000,01");
      await page.locator('#purchase-form [name="installments"]').fill("1");
      await page.locator('#purchase-form button[type="submit"],#purchase-form button.button').click();
      await page.locator("#purchase-dialog").waitFor({ state: "hidden" });
      await ready();
      await nav("overview");
      assert.match(await page.locator("#balance").textContent(), /3\.755,61/);
      assert(await page.locator("#balance").evaluate((node) => node.classList.contains("negative")));
      assert.match(await page.locator("#overview-attention").textContent(), /Despesas acima das receitas/);
      checks.push("Compra agrupada pt-BR, resultado negativo e alerta da demonstração coerentes");
    }
    assert.deepEqual(errors, []);
    fs.writeFileSync(`${output}/results.json`, JSON.stringify({ engine, mode, browser: browser.version(), audits, checks, runtimeErrors: errors }, null, 2));
    console.log(`PASS: redesign ${engine}/${mode}, ${audits.length} auditorias axe, ${checks.length} grupos de verificação; zero erros JS.`);
  } catch (error) {
    await page.screenshot({ path: `${output}/failure.png`, fullPage: true }).catch(() => {});
    fs.writeFileSync(`${output}/failure.json`, JSON.stringify({ message: error.message, audits, errors }, null, 2));
    throw error;
  } finally {
    if (csrf) await context.request.delete(`${base}/api/privacy/data`, { headers: { Origin: base, "X-CSRF-Token": csrf, "X-Confirm-Delete": "EXCLUIR" } });
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
