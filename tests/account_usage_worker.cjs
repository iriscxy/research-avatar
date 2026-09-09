const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const esbuild = require('../deploy/cloudflare/node_modules/esbuild');
const source = fs.readFileSync(path.join(__dirname, '../deploy/cloudflare/index.ts'), 'utf8');
const compiled = esbuild.transformSync(source, { loader: 'ts', format: 'cjs' }).code;
const moduleObject = { exports: {} };
const context = { module: moduleObject, exports: moduleObject.exports, require: () => ({ Container: class {} }), Request, Response, Headers, URL, console, TextEncoder, TextDecoder, crypto: require('node:crypto').webcrypto };
vm.runInNewContext(compiled, context);
const worker = moduleObject.exports.default;
const amounts = new Map();
const db = {
  prepare(sql) { return { sql, bind(...args) { return { sql, args }; } }; },
  async batch(statements) {
    return statements.map(({ sql, args }) => {
      if (sql.startsWith('INSERT')) {
        const key = args[0] + ':' + args[1];
        amounts.set(key, Math.max(amounts.get(key) || 0, args[2]));
        return { success: true, results: [] };
      }
      return { success: true, results: [{ amount: [...amounts].filter(([key]) => key.startsWith(args[0] + ':')).reduce((n, [, value]) => n + value, 0) }] };
    });
  },
};
const env = { DEEPSEEK_API_KEY: 'synthetic-server-key', AUTH_DB: db };
const account = 'a'.repeat(64), project = 'b'.repeat(64);
const call = (body, authorized = true) => worker.fetch(new Request('https://example.invalid/internal/account-usage', {
  method: 'POST', headers: { 'Content-Type': 'application/json', ...(authorized ? { Authorization: 'Bearer synthetic-server-key' } : {}) }, body: JSON.stringify(body),
}), env);
(async () => {
  assert.equal((await call({ account, projects: [] }, false)).status, 401);
  for (const amount of [30_000_000, 30_000_000, 10_000_000]) {
    const response = await call({ account, projects: [{ id: project, amount }] });
    assert.equal(response.status, 200);
    assert.equal((await response.json()).amount, 30_000_000);
  }
  assert.equal((await (await call({ account, projects: [] })).json()).amount, 30_000_000);
  assert.equal((await (await call({ account: 'c'.repeat(64), projects: [] })).json()).amount, 0);
  assert.equal((await call({ account, projects: [{ id: project, amount: -1 }] })).status, 503);
  assert.equal((await call({ account, projects: [], padding: 'x'.repeat(70_000) })).status, 503);
  console.log('Worker usage authentication, bounds, isolation and retries passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
