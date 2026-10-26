# Self-Maintaining APIs

APIs that fix themselves when vendors change them — with a human in charge.

When a vendor like Stripe renames a field, code that uses the old field
breaks. This tool watches the vendor spec, finds the exact places in
your code that use the changed field, patches them on a new branch,
runs the tests, and writes a pull-request summary. A human reviews and
merges. The tool never merges to your main branch.

## Demo: a real Stripe change

The demo uses Stripe's documented Billing Meter Usage change,
API version 2025-09-30.preview:
https://docs.stripe.com/changelog/clover/2025-09-30/update-meter-usage-fields

Renames covered:
- Request: `start_time` → `starts_at`, `end_time` → `ends_at`,
  `meters.meter_id` → `meters.meter`
- Response: `data_refreshed_at` → `refreshed_at`,
  `bucket_start_time` → `starts_at`, `bucket_end_time` → `ends_at`,
  `bucket_value` → `value`, `meter_id` → `meter`

One structural change is deliberately NOT auto-patched: the `data`
response object is now nested inside `rows`. The tool flags that for
human review instead of guessing.

## Run it

```bash
bash reset_and_run.sh
```

That resets the sample repo to its original state and runs the
maintainer. You should see: 7 renames found, 16 patch sites patched,
tests passing, and a new branch with the patch — main/master untouched.

Then inspect:

```bash
cd sample_repo && git branch --show-current && git diff
cat ../output/PR.md
```

No API keys, no network calls, no pip installs are needed for the
demo. The sample client is stubbed in the tests.

## How it works

1. **Watcher / Differ** — compare the old and new vendor specs, using
   the vendor's own changelog rename mapping.
2. **Finder** — scan code by structure (Python AST) for call keywords,
   dict keys, and subscript keys that match a changed field.
3. **Fixer** — patch only those exact sites, on a new branch.
4. **Checker** — run the repo's tests before opening a PR summary.
5. **PR Maker** — write `output/PR.md` and `output/pr.diff` for human
   review. The tool never merges.

## Honest limits

- Specs are fuller extracts for this one endpoint: changelog renames
  plus unchanged request/response fields from Stripe's Meter Usage
  Analytics guide. They are still not Stripe's full OpenAPI file.
- The 2025-09-30 version is a preview version.
- The sample client is stubbed — this demo does not call live Stripe.
- This demo creates a local branch and PR summary, not a real GitHub
  pull request yet. That is Phase 1 work.
- Sample repo: `sample_repo/` is itself a small git repo, because the
  demo's branch workflow needs a git repo to branch from. The top-level
  folder is the project; `sample_repo/` is the example customer code.

## Files

- `maintainer.py` — the tool
- `specs/spec_old.json`, `specs/spec_new.json` — vendor specs
- `sample_repo/app.py`, `sample_repo/test_app.py` — example customer code
- `reset_and_run.sh` — reset and re-run the demo from a clean state
- `PHASE0_DECISIONS.md` — the decisions still needed before this
  becomes a company repo (name, roles, equity, GitHub organisation)
