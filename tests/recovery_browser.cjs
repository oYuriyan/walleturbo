// Credenciais e checkpoint chegam do roteiro OIDC e permanecem em memória.
const assert = require("assert/strict");
const { spawn } = require("child_process");
const { createInterface } = require("readline");
const { request } = require("./basic_journey.cjs");
const base = "http://localhost:8000";

// A API exporta coleções sem contrato de ordenação SQL. Preservar todas as linhas.
function orderedExport(data) {
  const orderedKeys = (value) => {
    if (Array.isArray(value)) return value.map(orderedKeys);
    if (value && typeof value === "object")
      return Object.fromEntries(
        Object.keys(value)
          .sort()
          .map((key) => [key, orderedKeys(value[key])]),
      );
    return value;
  };
  return Object.fromEntries(
    Object.entries(data).map(([name, rows]) => [
      name,
      rows
        .map(orderedKeys)
        .sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))),
    ]),
  );
}

async function verifyRecovery(
  browser,
  fixture,
  secret,
  totp,
  checkpoint,
  oldCookie,
) {
  const child = spawn(
    "python",
    ["-m", "tests.integration_backup", "--identity", "--promote"],
    {
      stdio: ["pipe", "pipe", "pipe"],
    },
  );
  child.stdin.on("error", () => {}); // O código de saída abaixo valida a falha do filho.
  let readyResolve, readyReject;
  const ready = new Promise((resolve, reject) => {
    readyResolve = resolve;
    readyReject = reject;
  });
  const lines = createInterface({ input: child.stdout });
  lines.on("line", (line) => {
    if (line === "RECOVERY_READY") readyResolve();
    else if (line.startsWith("PASS:") || line.startsWith("RECOVERY:"))
      console.log(line);
  });
  // Não encaminhar stderr de ferramentas administrativas para artefatos/logs.
  child.stderr.resume();
  const exited = new Promise((resolve, reject) => {
    child.once("error", (error) => {
      readyReject(error);
      resolve(-1);
    });
    child.once("exit", (code) => {
      readyReject(Error("Ensaio de recuperação terminou antes da conferência"));
      resolve(code);
    });
  });
  let stage = "inicialização do destino";
  try {
    await ready;
    stage = "recusa do cookie anterior";
    const stale = await browser.newContext();
    try {
      await stale.addCookies([{ ...oldCookie, url: undefined }]);
      assert.equal((await stale.request.get(base + "/api/me")).status(), 401);
      console.log("RECOVERY: cookie anterior recusado pelo destino.");
    } finally {
      await stale.close();
    }
    const context = await browser.newContext();
    try {
      stage = "senha e OTP recuperado";
      const page = await context.newPage();
      await page.goto(base + "/auth/login");
      await page.locator("#username").fill(fixture.username);
      await page.locator("#password").fill(fixture.password);
      await page.locator("#kc-login").click();
      // Credencial OTP recuperada: precisa pedir o código, sem novo cadastro.
      await page.locator("#otp").waitFor();
      assert.equal((await context.request.get(base + "/api/me")).status(), 401);
      console.log("RECOVERY: senha aceita; destino exige OTP já cadastrado.");
      // O último código pode estar registrado como usado no snapshot.
      await new Promise((resolve) =>
        setTimeout(resolve, 30000 - (Date.now() % 30000) + 1000),
      );
      await page.locator("#otp").fill(totp(secret));
      await page.locator("#kc-login").click();
      await page.waitForURL(base + "/");
      stage = "exportação recuperada";
      const csrf = (await request(context, "", "/api/me")).csrf;
      assert.deepEqual(
        orderedExport(await request(context, csrf, "/api/privacy/export")),
        orderedExport(checkpoint.exported),
      );
      stage = "resultado e despesa recuperados";
      await page.locator("#month").fill("2026-11");
      await page.locator("#month").blur();
      await page.waitForFunction(() =>
        /1\.935,00/.test(document.querySelector("#balance").textContent),
      );
      assert.match(await page.locator("#expense").textContent(), /65,00/);
      console.log(
        "PASS: nova sessão no ambiente recuperado exige OTP existente, recusa cookie antigo e preserva exportação e resultado R$ 1.935.",
      );
    } finally {
      await context.close();
    }
    child.stdin.end("VERIFIED\n");
    stage = "reativação da origem";
    assert.equal(
      await exited,
      0,
      "O ensaio precisa limpar o destino e reativar a origem",
    );
  } catch (error) {
    console.error(`FAIL: recuperação, etapa ${stage}: ${error.name}`);
    throw error;
  } finally {
    if (!child.stdin.writableEnded) child.stdin.end();
    await exited;
    lines.close();
  }
}
module.exports = { verifyRecovery };
