---
name: google-ads
description: Safely inspect, report on, and manage Google Ads accounts with the gads CLI, including account discovery, GAQL queries, campaign and budget changes, App Campaign creation, creative asset uploads, conversion checks, and generic GoogleAdsService mutations. Use whenever Codex needs to check Google Ads performance, create or change campaigns, pause or enable delivery, upload assets, inspect conversion tracking, or perform Google Ads API CRUD for an advertiser.
---

# Google Ads

Operate Google Ads through the `gads` CLI. Keep reads scriptable and make every write
reviewable, validated, and auditable.

## Resolve the tool

Prefer the installed executable:

```bash
GADS_BIN="$(command -v gads)"
"$GADS_BIN" --version
```

If it is not installed, install it from a repository checkout:

```bash
./scripts/install-local.sh
gads --version
```

Do not confuse the Google Ads client customer ID with the manager/login customer ID.
Pass IDs without hyphens. Use root options before the subcommand:

```bash
"$GADS_BIN" --profile default --customer-id 1234567890 --format json campaigns list
```

## Follow the operating workflow

1. Run `gads auth test` before the first account operation in a session.
2. Read the account, currency, conversion actions, current campaigns, budgets, and assets
   before proposing a material change.
3. Run a write command without `--execute` to produce a local plan. This step needs no API
   credentials and performs protobuf schema validation.
4. Run the same command with `--validate-only` to ask Google Ads to validate it without
   applying it.
5. Run with `--execute` only when the user's request authorizes the exact change. Do not add
   a second approval requirement when the user already clearly requested the write.
6. Re-query the mutated resources and report their resource names, status, budget, and any
   policy or primary-status issues.

Treat `--execute` as the only live-write switch. Never use it while exploring syntax.

## Apply safety rules

- Create campaigns as `PAUSED`; inspect the complete structure before enabling them.
- Prefer `PAUSED` over `remove`. Campaign removal is not the same as a reversible pause.
- Treat uploaded assets as immutable. Google Ads does not let the API update or remove most
  assets; stop them serving by changing their associations or ads.
- Read `customer.currency_code` before interpreting any budget, CPA, ROAS, or cost micros.
- Preserve atomic behavior (`partial_failure: false`) for dependent campaign setup unless
  partial success is explicitly wanted and individually handled.
- Keep credentials outside the repository. Never print or commit developer tokens, OAuth
  secrets, refresh tokens, private keys, or image bytes.
- Capture Google Ads `request_id` from failures. The CLI records executed and validate-only
  mutation summaries in its local audit JSONL.
- Use a test account for integration tests when available. Do not manufacture production
  data merely to test the tool.

## Select the task path

- For authentication, developer-token access, installation, or profile setup, read
  [setup.md](references/setup.md).
- For account reads, reports, campaigns, budgets, assets, App Campaigns, generic mutation
  manifests, and troubleshooting, read [operations.md](references/operations.md).

## Use machine-readable output

Prefer `--format json` for bounded reads and plans, `--format jsonl` for large row sets, and
`--format csv` for handoff to spreadsheet analysis. Use `--limit` during exploration.

Use raw GAQL when a preset is insufficient:

```bash
"$GADS_BIN" --format json query run \
  "SELECT campaign.id, campaign.name, campaign.status FROM campaign"
```

Discover field validity instead of guessing:

```bash
"$GADS_BIN" --format json fields describe campaign.app_campaign_setting.app_id
"$GADS_BIN" --format json fields search 'metrics.%' --limit 50
```

## Use the escape hatch

Use `gads mutate apply plan.yaml` for GoogleAdsService mutation resources not covered by a
dedicated command. First run `gads mutate schema`, then author a versioned YAML plan. Always
plan, validate, and only then execute. If the needed method is not represented by
`GoogleAdsService.Mutate` (for example, a specialized service action), extend the CLI and its
tests instead of sending an opaque one-off request.
