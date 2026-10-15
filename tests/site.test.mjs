import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const html = fs.readFileSync(new URL('../index.html', import.meta.url), 'utf8');

test('all inline application scripts parse and local scripts exist', () => {
  let inline = 0;
  for (const match of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)) {
    const src = match[1].match(/\bsrc=["']([^"']+)["']/i)?.[1];
    if (src && !/^(https?:)?\/\//.test(src)) {
      const path = new URL('../' + src, import.meta.url);
      assert.ok(fs.existsSync(path), src);
      new vm.Script(fs.readFileSync(path, 'utf8'), {filename: src});
    } else if (!src && !/type=["']application\//.test(match[1]) && match[2].trim()) {
      new vm.Script(match[2]);
      inline++;
    }
  }
  assert.ok(inline > 0, 'no application scripts checked');
});

for (const [file, global, field] of [['rooms.js', 'POKER_ROOMS', 'rooms'], ['trails.js', 'MTB_TRAILS', 'trails']]) {
  test(`${file} loads with usable coordinates and unique identities`, () => {
    const context = vm.createContext({window: {}});
    new vm.Script(fs.readFileSync(new URL('../data/' + file, import.meta.url), 'utf8')).runInContext(context);
    const rows = context.window[global][field];
    assert.ok(Array.isArray(rows) && rows.length > 0);
    const identities = new Set();
    for (const row of rows) {
      assert.ok(typeof row.name === 'string' && row.name.trim());
      assert.ok(Number.isFinite(row.lat) && Math.abs(row.lat) <= 90, JSON.stringify(row));
      assert.ok(Number.isFinite(row.lon) && Math.abs(row.lon) <= 180, JSON.stringify(row));
      assert.ok(row.id && !identities.has(row.id), `duplicate/missing id ${row.id}`);
      identities.add(row.id);
    }
  });
}
