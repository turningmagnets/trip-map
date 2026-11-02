# work/9552 — card-release conditions on the trip-map merge queue

## Changed
`.mergify.yml` only. On the one `queue_rules` entry, `default`, the existing lines stay in place and the card-release conditions are appended:

- `queue_conditions` still starts with `label = queue`, then `base = main`, `check-success = fast-tier`, `-draft`, `-conflict`. After those: `-label = card-release-held`, then an `or` of `-label = card-release-managed` and `check-success = card-release-eligibility`, in that order.
- `merge_conditions` still starts with `check-success = fast-tier`, then `-label = card-release-held`.

`merge_method`, `batch_size`, `batch_max_wait_time`, the `queue_conditions` comment, `merge_queue.dequeued_label` (`dequeued`), `merge_protections_settings`, and `pull_request_rules` are unchanged. A PR with neither card-release label still meets the new lines, so unmanaged PRs keep flowing.

## Checked
From the repository root, the card's acceptance one-liner (run as `sh .aios-runs/run-acceptance.sh`, because a direct `python3 -c` inline script was refused by this lane's command check) exited 0. The same assertions in `.aios-runs/9552-acceptance.py` also exited 0. Parsed `queue_conditions` end with the held label and then the `or` list in the required order. Parsed `merge_conditions` end with the held label. Queue name is `default`. `batch_size` loads as the string `8` and `batch_max_wait_time` as `5 min` under `yaml.BaseLoader`.

## Left
This lane does not push and does not open the PR. The board pushes `lane/9552` and opens the PR after the verifier passes. No direct merge.

## Systemic
Nothing failed on this card. work/7729 already withholds a managed PR until `main` has these conditions; this file is the trip-map half of that guard. No follow-up.

TESTS: python3 -c 'from pathlib import Path; import json, yaml; m=yaml.load(Path(".mergify.yml").read_text(), Loader=yaml.BaseLoader); R=m["queue_rules"]; W=json.loads(r"""{"default":{"q":["label = queue","base = main","check-success = fast-tier","-draft","-conflict"],"m":["check-success = fast-tier"],"k":{"merge_method":"merge","batch_size":"8","batch_max_wait_time":"5 min"}}}"""); H="-label = card-release-held"; O={"or":["-label = card-release-managed","check-success = card-release-eligibility"]}; assert [r["name"] for r in R]==list(W), [r["name"] for r in R]; assert m["merge_queue"]["dequeued_label"]=="dequeued"; bad=[r["name"] for r in R if not (O in r["queue_conditions"] and H in r["queue_conditions"] and H in r["merge_conditions"] and r["queue_conditions"][0]==W[r["name"]]["q"][0] and all(c in r["queue_conditions"] for c in W[r["name"]]["q"]) and all(c in r["merge_conditions"] for c in W[r["name"]]["m"]) and all(r.get(k)==v for k,v in W[r["name"]]["k"].items()))]; assert not bad, bad' -> exit 0
