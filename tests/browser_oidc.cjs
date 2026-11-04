// A fixture chega por stdin; não gravar senha, QR, segredo TOTP ou tokens em artefatos.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const { createHmac } = require('crypto');
const fs = require('fs');
const assert = require('assert/strict');
const base = 'http://localhost:8000';
function totp(secret) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const c of secret.toUpperCase().replace(/[\s=]/g, '')) {
    assert(alphabet.includes(c));
    bits += alphabet.indexOf(c).toString(2).padStart(5, '0');
  }
  const key = Buffer.from((bits.match(/.{8}/g) || []).map(b => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const hash = createHmac('sha1', key).update(counter).digest();
  const offset = hash[hash.length - 1] & 15;
  return ((hash.readUInt32BE(offset) & 0x7fffffff) % 1000000).toString().padStart(6, '0');
}
(async () => {
  const fixture = JSON.parse(fs.readFileSync(0, 'utf8'));
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    assert.equal((await context.request.get(base + '/api/me')).status(), 401);
    await page.goto(base + '/auth/login');
    assert.equal(new URL(page.url()).hostname, 'auth.walleturbo.localhost');
    assert.equal(new URL(page.url()).searchParams.get('code_challenge_method'), 'S256');
    const before = (await context.cookies(base)).find(c => c.name === 'walleturbo_session');
    assert(before);
    await page.locator('#username').fill(fixture.username);
    await page.locator('#password').fill(fixture.password);
    await page.locator('#kc-login').click();
    await page.locator('#totpSecret').waitFor({state: 'attached'});
    assert.equal((await context.request.get(base + '/api/me')).status(), 401);
    const secret = await page.locator('#totpSecret').inputValue();
    const valid = totp(secret);
    await page.locator('#totp').fill(valid === '000000' ? '111111' : '000000');
    await page.locator('#userLabel').fill('CI sintético');
    await page.locator('input[type=submit]').last().click();
    await page.locator('#input-error-otp-code').waitFor();
    assert.equal((await context.request.get(base + '/api/me')).status(), 401);
    await page.locator('#totp').fill(totp(secret));
    await page.locator('input[type=submit]').last().click();
    await page.waitForURL(base + '/');
    const me = await context.request.get(base + '/api/me');
    assert.equal(me.status(), 200);
    const {csrf} = await me.json();
    const after = (await context.cookies(base)).find(c => c.name === 'walleturbo_session');
    assert(after && after.value !== before.value);
    assert(after.httpOnly && after.sameSite === 'Lax');
    // A sessão pré-login é revogada ao completar a troca OIDC.
    const stolen = await browser.newContext();
    await stolen.addCookies([{...before, url: undefined}]);
    assert.equal((await stolen.request.get(base + '/api/me')).status(), 401);
    await stolen.close();
    assert.equal((await context.request.post(base + '/api/logout', {
      headers: {Origin: base, 'X-CSRF-Token': csrf}
    })).status(), 200);
    assert.equal((await context.request.get(base + '/api/me')).status(), 401);
    // Uma tentativa com state incorreto precisa ser rejeitada sem autenticar.
    await page.goto(base + '/auth/login');
    const invalid = await context.request.get(base + '/auth/callback?state=invalid&code=invalid', {maxRedirects: 0});
    assert.equal(invalid.status(), 400);
    assert.equal((await context.request.get(base + '/api/me')).status(), 401);
    console.log('PASS: Keycloak real, PKCE, cadastro TOTP, recusa de código incorreto/ausente, ID token assinado, rotação, logout e state inválido.');
  } finally {
    await context.close();
    await browser.close();
  }
})().catch(() => { console.error('FAIL: fluxo OIDC real; conferir etapa sem expor credenciais.'); process.exitCode = 1; });
