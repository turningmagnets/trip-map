# work/8723 — credit Trailforks for its trail data

## Changed
- `index.html`: the trail attribution now reads `Trails: MTB Project · Trail data © Trailforks`, with `Trailforks` linked to https://www.trailforks.com/ (opens in a new tab). The Esri tile credit and the rest of the page are unchanged.
- `SOURCES.md`, "MTB trails" section: the first line is now `Trail data © Trailforks (https://www.trailforks.com/), used under its terms for personal, non-commercial use, with share-alike credit.` A new paragraph says plainly that the ★3.8–3.99 trails the 2018 MTB Project archive and the cached Trailforks pages cannot supply are missing, and that this is the gap counted under "Known gaps". No counts or data files changed.
- `tests/trailforks-credit.test.mjs` (new, node:test): checks that an `addAttribution(...)` call holds `Trail data ©`/`&copy;` followed by `Trailforks`, linked, with MTB Project kept; that the Esri tile credit is unchanged; and that the MTB trails section of SOURCES.md has the credit line.

## Checked
- On main's index.html and SOURCES.md (copies in .aios-runs/main), the new test fails 2 of 3: both credit tests fail and the Esri test passes.
- On this branch the acceptance exits 0, with 6/6 tests passing.
- Not checked in a browser. Leaflet renders attribution strings as HTML, so the link shows in the control.

## Root cause
- This time: the credit was a requirement only on work/4398's branch. That branch was retired, main was rebuilt from other commits, and no test or check kept the requirement alive. The new test now fails if the credit is removed from either file.
- Next time: an operator requirement attached to a branch disappears with the branch unless it becomes a test or acceptance on main. Where the fix belongs: when a branch is retired, the Conductor or operator should move every open instruction on its card (here 6810) to a live card. I have not changed this; it is outside this workspace.

Vault: filed note 1006163 (trip-map Trailforks credit now on lane/8723).

TESTS: test -f tests/site.test.mjs && test -f tests/trailforks-credit.test.mjs && grep -q 'Trail data .* Trailforks' SOURCES.md && node --test tests/site.test.mjs tests/trailforks-credit.test.mjs -> pass (6/6, exit 0)
