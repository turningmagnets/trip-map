import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const html = fs.readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const sources = fs.readFileSync(new URL('../SOURCES.md', import.meta.url), 'utf8');

test('map attribution credits Trailforks for its trail data', () => {
  const calls = [...html.matchAll(/addAttribution\(\s*(['"`])([\s\S]*?)\1\s*\)/g)].map(m => m[2]);
  assert.ok(calls.length > 0, 'no addAttribution call in index.html');
  const credit = calls.find(text => /Trail data (©|&copy;)[\s\S]*Trailforks/.test(text));
  assert.ok(credit, `no "Trail data © Trailforks" in attribution calls: ${JSON.stringify(calls)}`);
  assert.match(credit, /href=["']https:\/\/www\.trailforks\.com\/["']/, 'Trailforks credit is not linked');
  assert.match(credit, /MTB Project/, 'MTB Project credit was dropped');
});

test('Esri tile credit is unchanged', () => {
  assert.ok(html.includes("attribution: 'Tiles &copy; Esri — Esri, HERE, Garmin, FAO, NOAA, USGS'"));
});

test('SOURCES.md carries the Trailforks credit line in the MTB trails section', () => {
  const section = sources.split(/^## MTB trails$/m)[1]?.split(/^## /m)[0];
  assert.ok(section, 'no "## MTB trails" section');
  assert.match(section, /Trail data © Trailforks \(https:\/\/www\.trailforks\.com\/\)/);
});
