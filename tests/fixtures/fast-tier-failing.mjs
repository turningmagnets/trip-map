// Deliberately red fixture for tests/fast-tier-reporting.test.mjs. Not named *.test.mjs, so CI's glob never runs it.
import test from 'node:test';
import assert from 'node:assert/strict';

test('fixture passes', () => {});

test('fixture deliberately fails', () => {
  assert.equal(1, 2, 'fixture failure message');
});
