// Workflow contract: the fast-tier job writes Node JUnit to fast-tier.xml and always uploads it as
// fast-tier-${{ github.sha }}, the artifact the board reads to name a red batch's failing tests (work/8116).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const workflow = fs.readFileSync(path.join(root, '.github/workflows/ci.yml'), 'utf8');
const fixture = path.join(root, 'tests/fixtures/fast-tier-failing.mjs');

// Block-YAML steps of jobs.fast-tier: top-level scalar keys, plus the `with:` mapping. No YAML dependency.
function fastTierSteps(text) {
  const lines = text.split('\n');
  const start = lines.findIndex(line => /^ {2}fast-tier:\s*(#.*)?$/.test(line));
  assert.ok(start >= 0, 'ci.yml has no jobs.fast-tier');
  const steps = [];
  let inSteps = false, stepIndent = null, step = null, inWith = false;
  for (const line of lines.slice(start + 1)) {
    if (!line.trim() || line.trim().startsWith('#')) continue;
    const indent = line.length - line.trimStart().length;
    if (indent <= 2) break;
    if (line.trim() === 'steps:') { inSteps = true; continue; }
    if (!inSteps) continue;
    let body = line.trim();
    if (body.startsWith('- ') && (stepIndent === null || indent === stepIndent)) {
      stepIndent = indent;
      steps.push(step = {with: {}});
      inWith = false;
      body = body.slice(2);
    } else if (indent <= stepIndent + 2) {
      inWith = false;
    }
    const pair = body.match(/^([\w-]+):\s*(.*)$/);
    if (!step || !pair) continue;
    const [, key, raw] = pair;
    const value = raw.replace(/^(['"])(.*)\1$/, '$2');
    if (key === 'with' && !value) inWith = true;
    else if (inWith && indent > stepIndent + 2) step.with[key] = value;
    else step[key] = value;
  }
  return steps;
}

const steps = fastTierSteps(workflow);
const testStep = steps.find(step => /^node --test\b/.test(step.run || ''));

function runFastTier(files, cwd) {
  // The workflow's own command, with its test glob replaced by `files`. NODE_TEST_CONTEXT is dropped so the
  // child runs as a top-level node --test, as on CI, rather than as a subtest reporting into this run.
  const argv = testStep.run.trim().split(/\s+/).slice(1).filter(arg => arg !== 'tests/*.test.mjs');
  const env = {...process.env};
  delete env.NODE_TEST_CONTEXT;
  return spawnSync(process.execPath, [...argv, ...files], {cwd, env, encoding: 'utf8', timeout: 60_000});
}

test('fast-tier test step writes JUnit to fast-tier.xml and keeps a console reporter', () => {
  assert.ok(testStep, 'fast-tier has no node --test step');
  const argv = testStep.run.trim().split(/\s+/);
  assert.ok(argv.includes('tests/*.test.mjs'), testStep.run);
  const reporters = argv.filter(arg => arg.startsWith('--test-reporter=')).map(arg => arg.split('=')[1]);
  const destinations = argv.filter(arg => arg.startsWith('--test-reporter-destination='))
    .map(arg => arg.split('=')[1]);
  assert.equal(reporters.length, destinations.length, 'each --test-reporter needs its own destination');
  assert.equal(destinations[reporters.indexOf('junit')], 'fast-tier.xml', testStep.run);
  assert.ok(reporters.some((reporter, i) => reporter !== 'junit' && destinations[i] === 'stdout'),
    'a human-readable reporter must still write to stdout');
  assert.ok(!/[|;&]|\|\||continue-on-error/.test(testStep.run) && !testStep['continue-on-error'],
    'the test step must keep node --test exit status');
});

test('fast-tier always uploads fast-tier.xml as fast-tier-${{ github.sha }}', () => {
  const testIndex = steps.indexOf(testStep);
  const upload = steps.findIndex(step => (step.uses || '').startsWith('actions/upload-artifact@')
    && step.with.name === 'fast-tier-${{ github.sha }}');
  assert.ok(upload > testIndex, 'no fast-tier-${{ github.sha }} upload after the test step');
  const step = steps[upload];
  assert.equal(step.if.replace(/^\$\{\{\s*(.*?)\s*\}\}$/, '$1').replace(/\s+/g, ''), 'always()');
  assert.equal(step.with.path, 'fast-tier.xml');
  assert.equal(step.with['if-no-files-found'], 'error');
});

test('a deliberately failing test fails the command and is named in fast-tier.xml', () => {
  const cwd = fs.mkdtempSync(path.join(os.tmpdir(), 'fast-tier-'));
  try {
    const result = runFastTier([fixture], cwd);
    assert.equal(result.error, undefined);
    assert.notEqual(result.status, 0, 'a failing test must fail the step');
    assert.match(result.stdout, /fixture deliberately fails/, 'console output lost');
    const xml = fs.readFileSync(path.join(cwd, 'fast-tier.xml'), 'utf8');
    // board_prs._fast_tier_lines needs a testcase with classname, name and a <failure> child.
    const failed = [...xml.matchAll(/<testcase\b([^>]*?)(?:\/>|>([\s\S]*?)<\/testcase>)/g)]
      .filter(([, , body]) => /<failure\b/.test(body || ''));
    assert.equal(failed.length, 1, xml);
    assert.match(failed[0][1], /\bname="fixture deliberately fails"/);
    assert.match(failed[0][1], /\bclassname="[^"]+"/);
    assert.match(failed[0][2], /message="[^"]*fixture failure message/);
    assert.match(xml, /<testcase\b[^>]*\bname="fixture passes"[^>]*\/>/);
  } finally {
    fs.rmSync(cwd, {recursive: true, force: true});
  }
});

test('a green run exits 0 and still writes fast-tier.xml', () => {
  const cwd = fs.mkdtempSync(path.join(os.tmpdir(), 'fast-tier-'));
  const green = path.join(cwd, 'green.mjs');
  fs.writeFileSync(green, "import test from 'node:test';\ntest('green fixture', () => {});\n");
  try {
    const result = runFastTier([green], cwd);
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.match(fs.readFileSync(path.join(cwd, 'fast-tier.xml'), 'utf8'), /name="green fixture"/);
  } finally {
    fs.rmSync(cwd, {recursive: true, force: true});
  }
});
