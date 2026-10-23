# work/8116: trip-map fast-tier publishes Node JUnit results

## What changed
- `.github/workflows/ci.yml`: the fast-tier `Test` step now runs
  `node --test --test-reporter=spec --test-reporter-destination=stdout --test-reporter=junit --test-reporter-destination=fast-tier.xml tests/*.test.mjs`
  (spec keeps the readable console log; junit writes `fast-tier.xml`; no `|| true`, so a failing test still fails the step).
  A new `actions/upload-artifact@v4` step with `if: always()` uploads `fast-tier.xml` as `fast-tier-${{ github.sha }}`
  (`if-no-files-found: error`, as in aios's own ci.yml).
- `tests/fast-tier-reporting.test.mjs` (new): Node workflow contract regression. It reads ci.yml's fast-tier steps
  (no YAML dependency), checks the junit reporter goes to fast-tier.xml with a console reporter still on stdout and
  nothing swallowing the exit status, checks the upload step (after the test step, `always()`, name, path), then runs
  the workflow's own command against a deliberately failing fixture: exit non-zero, the test name on stdout, and a
  `<testcase name="fixture deliberately fails" classname=...>` with a `<failure>` child in fast-tier.xml. A green
  fixture exits 0 and still writes the xml.
- `tests/fixtures/fast-tier-failing.mjs` (new): the red fixture; not named `*.test.mjs`, so CI's glob never runs it.
- No pytest added (per the brief).

## Verified
- `node --test tests/fast-tier-reporting.test.mjs` -> 4 pass, 0 fail on Node 26.7.0 and on Node 22.23.1 (CI's major).
- The workflow's exact command over the whole suite on Node 22 -> exit 0, 7 testcases in fast-tier.xml.
- Board read-back: the fixture's real fast-tier.xml, zipped and fed to aios `board_prs._fast_tier_lines`, returns
  `test::fixture deliberately fails: fixture failure message1 !== 2`, so a red batch now names its test.
- Census: `aios.fast_tier_ci_shape.inspect_workflow` on main gives a=fail b=fail c=pass; on this branch a=fail
  b=pass c=pass. (a) is the checker's pytest-only rule (below).
- Mutation check: each of `if: success()`, dropping the junit reporter, dropping the stdout reporter, appending
  `|| true`, and renaming the artifact to `fast-tier` turns the regression test red.
- Not yet seen on GitHub: the first live run of this workflow is the PR the board opens from lane/8116. Check that
  its run lists a `fast-tier-<sha>` artifact.

## Systemic
- Immediate: trip-map's fast-tier now publishes a report, and the contract test stops it from silently regressing.
- Class: census check (a) in aios `aios/fast_tier_ci_shape.py` (`inspect_workflow`, the `junit` test) only accepts
  `pytest --junitxml=fast-tier.xml`, so every Node-tested repo flags (a) even when it writes fast-tier.xml. The fix
  belongs there: also accept a `node --test` call whose `--test-reporter=junit` is paired with
  `--test-reporter-destination=fast-tier.xml`. The operator has already routed this to the Maintainer (comment on
  run 8128), so no follow-up is filed here.

TESTS: node --test tests/fast-tier-reporting.test.mjs -> 4 passed, 0 failed
