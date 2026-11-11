const engines = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("assert/strict");
(async () => {
  const engine = process.env.BROWSER_ENGINE || "chromium";
  const browser = await engines[engine].launch({
    headless: true,
    args: engine === "chromium" ? ["--no-sandbox"] : [],
    ...(engine === "chromium" && process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {}),
  });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
    locale: "pt-BR",
  });
  const authenticated = process.env.UI_AUTH === "1";
  const base = process.env.APP_URL || "http://localhost:8000";
  const context = page.context();
  let headers;
  if (authenticated) {
    const seed = JSON.parse(require("fs").readFileSync(0, "utf8"));
    await context.addCookies([
      {
        name: "walleturbo_session",
        value: seed.sid,
        url: base,
        httpOnly: true,
        sameSite: "Lax",
      },
    ]);
    headers = {
      Origin: base,
      "X-CSRF-Token": (
        await (await context.request.get(base + "/api/me")).json()
      ).csrf,
    };
  }
  let quota;
  page.on("response", (response) => {
    if (response.status() === 429)
      quota = {
        at: Date.now(),
        retry: Number(response.headers()["retry-after"]),
      };
  });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    await page.goto(base);
    await page.keyboard.press("Tab");
    assert.equal(
      await page.locator(":focus").textContent(),
      "Ir para o conteúdo",
    );
    await page.keyboard.press("Enter");
    assert.equal(await page.locator(":focus").getAttribute("id"), "page-title");
    if (authenticated)
      await require("./basic_journey.cjs").buildJourney(
        context,
        page,
        headers["X-CSRF-Token"],
      );
    else
      await page
        .getByRole("button", { name: "Explorar demonstração", exact: false })
        .click();
    await page.evaluate(
      require("fs").readFileSync(
        process.env.AXE_PATH || require.resolve("axe-core/axe.min.js"),
        "utf8",
      ),
    );
    const setMonth = async (value, waitForRender = true) => {
      for (let attempt = 0; attempt < 2; attempt++) {
        const completed = page.waitForResponse(
          (response) =>
            response.url() === `${base}/api/dashboard?month=${value}`,
        );
        if (attempt) await page.locator("#month").dispatchEvent("change");
        else {
          await page.locator("#month").fill(value);
          await page.locator("#month").blur();
        }
        const response = await completed;
        if (response.status() !== 429) {
          assert.equal(response.status(), 200);
          if (!waitForRender) return;
          await page.waitForFunction(
            () =>
              document.querySelector("main").getAttribute("aria-busy") ===
              "false",
          );
          const status = await page.locator("#status").textContent();
          if (!status) return;
          assert.match(status, /Limite de requisições/);
        }
        if (attempt) assert.fail("Cota ainda indisponível após a espera");
        assert(quota && quota.retry > 0 && quota.retry <= 60);
        const remaining = Math.max(
          0,
          quota.at + quota.retry * 1000 - Date.now(),
        );
        await new Promise((resolve) => setTimeout(resolve, remaining + 1000));
      }
    };
    const views = [
      "overview",
      "transactions",
      "finance",
      "planning",
      "goals",
      "privacy",
    ];
    const audit = async (label) => {
      await page.waitForFunction(
        () =>
          document.querySelector("main").getAttribute("aria-busy") === "false",
      );
      const result = await page.evaluate(async () =>
        axe.run(document, {
          runOnly: {
            type: "tag",
            values: ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"],
          },
        }),
      );
      assert.deepEqual(
        result.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          targets: v.nodes.map((n) => n.target),
        })),
        [],
        label,
      );
    };
    if (authenticated) {
      // Falhar ao consultar outro mês não pode liberar ações sobre dados antigos.
      await page.route(
        "**/api/dashboard?month=2026-12",
        (route) =>
          route.fulfill({
            status: 503,
            contentType: "application/json",
            body: JSON.stringify({
              detail: "Consulta temporariamente indisponível",
            }),
          }),
        { times: 1 },
      );
      await page.locator("#month").fill("2026-12");
      await page.locator("#month").blur();
      await page.locator("#retry-load").waitFor();
      assert(await page.locator("#finance").evaluate((node) => node.inert));
      assert(await page.locator("#privacy").evaluate((node) => !node.inert));
      assert.match(
        await page.locator("#status").textContent(),
        /temporariamente indisponível/,
      );
      await audit("falha de carregamento");
      await page.locator("#retry-load").click();
      await page.waitForFunction(
        () =>
          document.querySelector("main").getAttribute("aria-busy") ===
            "false" && !document.querySelector("#finance").inert,
      );
      assert(await page.locator("#retry-load").isHidden());
      await setMonth("2026-11");
      let release, fetched;
      const held = new Promise((resolve) => (release = resolve)),
        received = new Promise((resolve) => (fetched = resolve));
      await page.route("**/api/statements?month=2026-12", async (route) => {
        const response = await route.fetch();
        assert.equal(response.status(), 200);
        fetched();
        await held;
        await route.fulfill({ response });
      });
      try {
        await setMonth("2026-12", false);
        await received;
        assert.equal(
          await page.locator("main").getAttribute("aria-busy"),
          "true",
        );
        await setMonth("2026-11");
        await page.waitForFunction(
          () =>
            document.querySelector("main").getAttribute("aria-busy") ===
            "false",
        );
        const completed = page.waitForResponse((response) =>
          response.url().endsWith("/api/statements?month=2026-12"),
        );
        release();
        await completed;
        await page.unroute("**/api/statements?month=2026-12");
        await page.waitForLoadState("networkidle");
        assert.equal(
          await page.locator("main").getAttribute("data-rendered-month"),
          "2026-11",
        );
        assert(
          await page.evaluate(() =>
            financeStatements.every((row) => row.month === "2026-11"),
          ),
        );
        assert.match(await page.locator("#balance").textContent(), /1\.935,00/);
      } finally {
        release();
      }
    }
    for (const dark of [false, true]) {
      if (dark) await page.locator("#theme").click();
      for (const view of views) {
        await page.locator(`.nav[data-view="${view}"]`).click();
        assert.equal(
          await page.locator(":focus").getAttribute("id"),
          "page-title",
        );
        assert.equal(
          await page.locator('.nav[aria-current="page"]').count(),
          1,
        );
        if (authenticated && view === "planning")
          await page.waitForFunction(
            () => document.querySelector("#capacity").textContent.length > 0,
          );
        await audit(`${engine} ${view} ${dark ? "escuro" : "claro"}`);
      }
    }
    if (authenticated) {
      await page.locator('.nav[data-view="finance"]').click();
      await setMonth("2026-12");
      const menu = page.locator("#statement-list .row-menu").first();
      await menu.locator("summary").focus();
      await page.keyboard.press("Enter");
      assert(await menu.evaluate((node) => node.open));
      await menu
        .getByRole("button", { name: "Corrigir compra", exact: true })
        .waitFor();
      await audit("ações secundárias da compra");
      await page.locator("#history-panel > summary").click();
      await page.locator("#refresh-history").click();
      await page.locator("#history-list details").first().waitFor();
      await audit("histórico consultado");
      await page.locator("#history-panel > summary").click();
    }
    await page.locator("#theme").click();
    await page.locator('.nav[data-view="transactions"]').click();
    await page
      .getByRole("button", { name: "Novo lançamento", exact: false })
      .click();
    const dialog = page.getByRole("dialog", {
      name: "Novo lançamento",
      exact: true,
    });
    await dialog.waitFor();
    assert.equal(
      await page.locator(":focus").getAttribute("name"),
      "description",
    );
    await audit("diálogo de lançamento");
    for (let i = 0; i < 18; i++) {
      await page.keyboard.press("Tab");
      assert(
        await page.evaluate(
          () => !!document.activeElement.closest("dialog[open]"),
        ),
      );
    }
    await page.keyboard.press("Escape");
    await dialog.waitFor({ state: "hidden" });
    assert(
      await page
        .locator(":focus")
        .evaluate((node) => node.matches('[data-action="new-entry"]')),
    );
    for (const width of [320, 390, 768]) {
      await page.setViewportSize({ width, height: 844 });
      for (const view of views) {
        const link = page.locator(`.nav[data-view="${view}"]`);
        await link.click();
        const bounds = await link.boundingBox();
        assert(
          bounds.x >= 0 && bounds.x + bounds.width <= width + 1,
          `navegação ${width}`,
        );
        assert(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
          `${view} ${width}`,
        );
      }
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.locator('.nav[data-view="overview"]').click();
    if (authenticated) {
      await setMonth("2026-11");
      await page.waitForFunction(() =>
        /1\.935,00/.test(document.querySelector("#balance").textContent),
      );
    }
    await page.screenshot({
      path: `artifacts/ui-${engine}-desktop.png`,
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({
      path: `artifacts/ui-${engine}-mobile.png`,
      fullPage: true,
    });
    await page.locator('.topbar button[aria-label="Alternar tema"]').click();
    await audit("mobile escuro");
    await page.screenshot({
      path: `artifacts/ui-${engine}-dark.png`,
      fullPage: true,
    });
    assert.deepEqual(errors, []);
    console.log(
      `PASS: UI ${engine}, seis áreas claro/escuro sem violações axe WCAG A/AA nos estados testados, navegação 320/390/768px, foco/Tab/Escape e diálogos nomeados.`,
    );
  } finally {
    if (authenticated)
      await context.request.delete(base + "/api/privacy/data", {
        headers: { ...headers, "X-Confirm-Delete": "EXCLUIR" },
      });
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
