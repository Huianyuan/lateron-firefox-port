const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
(async () => {
  for (const name of ['library.js', 'sidepanel.js']) {
    const source = fs.readFileSync(path.join(__dirname, '..', name), 'utf8');
    const start = source.indexOf('async function saveCovers(next) {');
    const end = source.indexOf('\n}', start) + 2;
    let fail = true, stored = { a: 'old' }, message;
    const context = vm.createContext({ covers: stored, COVERS_KEY: 'covers', tr: key => key,
      showToast: text => { message = text; }, status: {},
      chrome: { storage: { local: { set: async patch => { if (fail) throw Error('write failure'); stored = patch.covers; } } } }
    });
    vm.runInContext(source.slice(start, end), context);
    assert.strictEqual(await context.saveCovers({ a: 'new' }), false);
    assert.strictEqual(context.covers.a, 'old');
    assert.strictEqual(stored.a, 'old');
    assert.strictEqual(message || context.status.textContent, 'operationFailed');
    fail = false;
    assert.strictEqual(await context.saveCovers({ a: 'new' }), true);
    assert.strictEqual(context.covers.a, 'new');
    assert.strictEqual(stored.a, 'new');
  }
  console.log('PASS 两个界面封面写入失败保留原数据并提示，重试成功后才更新内存');
})().catch(error => { console.error(error); process.exitCode = 1; });
