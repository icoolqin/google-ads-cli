# Operations

## Contents

- Read account state
- Query and report
- Manage campaigns and budgets
- Create App Campaigns
- Manage creative assets
- Inspect conversions and targeting constants
- Use generic mutation manifests
- Diagnose failures

## Read account state

Use reads before writes:

```bash
gads --format json accounts show
gads --format json campaigns list
gads --format json budgets list
gads --format json adgroups list
gads --format json ads list
gads --format json assets list
gads --format json conversions list
```

Narrow ad groups or ads with `--campaign-id`; include removed resources only when auditing
history.

## Query and report

List and run curated reports:

```bash
gads reports list
gads --format json reports run campaigns --date-range LAST_30_DAYS
gads --format csv reports run daily --date-range 2026-07-01:2026-07-28
gads --format json reports run conversion-actions --date-range LAST_30_DAYS
```

Available date names include `TODAY`, `YESTERDAY`, `LAST_7_DAYS`, `LAST_14_DAYS`,
`LAST_30_DAYS`, `THIS_MONTH`, and `LAST_MONTH`.

Run arbitrary GAQL:

```bash
gads query validate --file /absolute/path/report.gaql
gads --format jsonl query run --file /absolute/path/report.gaql --limit 1000
```

Remember that adding a segment splits metrics into one row per segment/resource tuple. Do not
sum already segmented and unsegmented reports together.

## Manage campaigns and budgets

Inspect first, then plan/validate/execute:

```bash
gads campaigns get 123456789

gads campaigns set-status 123456789 PAUSED
gads campaigns set-status 123456789 PAUSED --validate-only
gads campaigns set-status 123456789 PAUSED --execute

gads budgets set-amount 987654321 50
gads budgets set-amount 987654321 50 --validate-only
gads budgets set-amount 987654321 50 --execute
```

Budget amounts use the customer account currency and are converted to micros exactly.

Remove only on an explicit removal request:

```bash
gads campaigns remove 123456789
gads campaigns remove 123456789 --validate-only
gads campaigns remove 123456789 --execute
```

Prefer pausing for ordinary shutdowns.

## Create App Campaigns

Create an atomic install campaign plan:

```bash
gads --format json campaigns create-app \
  --name "Example App · US · Install" \
  --app-id 000000000 \
  --app-store APPLE_APP_STORE \
  --daily-budget 50 \
  --goal installs \
  --target-cpa 2.50 \
  --headline "Create Something New" \
  --headline "Your Ideas, Made Simple" \
  --description "Turn an idea into something worth sharing." \
  --description "Create, refine, and share in just a few steps." \
  --location 2840 \
  --language 1000
```

The plan creates a non-shared budget, a `PAUSED` multi-channel App Campaign, language/location
criteria, an enabled ad group, and an enabled App Ad in one `GoogleAdsService.Mutate` call with
temporary resource IDs. Add uploaded image or YouTube assets using repeated `--image-asset` or
`--video-asset`.

Supported goals:

- `installs` with `--target-cpa`
- `installs-and-actions` with `--target-cpa` and conversion actions
- `in-app-actions` with `--target-cpa` and conversion actions
- `roas` with `--target-roas` and conversion actions
- v25 no-target variants: `installs-no-target`, `in-app-actions-no-target`,
  `value-no-target`

Pass conversion action IDs or full resource names with repeated `--conversion-action`.

Always validate against the real account before executing:

```bash
# Same arguments as the plan:
gads campaigns create-app ... --validate-only
gads campaigns create-app ... --execute
```

After creation, query Campaign, criteria, Ad Group, Ad, budget, policy approval, and primary
status reasons. Enable the Campaign only after all are ready.

## Manage creative assets

Upload images:

```bash
gads assets upload-image /absolute/path/creative.png --name "US Before After 1"
gads assets upload-image /absolute/path/creative.png --name "US Before After 1" --validate-only
gads assets upload-image /absolute/path/creative.png --name "US Before After 1" --execute
```

The CLI verifies JPEG/PNG/GIF content and dimensions locally. Binary data is hashed and
redacted from plan output.

Create a YouTube video asset:

```bash
gads assets create-youtube VIDEO_ID --name "US Demo 15s"
```

Pass the YouTube video ID, not a full URL. Assets are immutable after upload.

## Inspect conversions and targeting constants

Before choosing an in-app action or value goal:

```bash
gads --format json conversions list
```

Use the returned conversion resource name. Verify that it is the intended app event, primary
for the goal, active, and receiving recent data.

Resolve locations and languages instead of guessing IDs:

```bash
gads --format json geo suggest "United States" --country-code US
gads --format json geo languages
```

## Use generic mutation manifests

Print the schema example:

```bash
gads --format json mutate schema
```

Manifest structure:

```yaml
label: pause-one-campaign
customer_id: "1234567890"
api_version: v25
partial_failure: false
response_content_type: RESOURCE_NAME_ONLY
operations:
  - resource: campaign
    action: update
    data:
      resourceName: customers/1234567890/campaigns/111
      status: PAUSED
    update_mask:
      - status
```

Run:

```bash
gads mutate apply plan.yaml
gads mutate apply plan.yaml --validate-only
gads mutate apply plan.yaml --execute
```

Use protobuf JSON field names and enum labels. A resource maps to the corresponding field in
`MutateOperation`, such as `campaign_budget`, `campaign_criterion`, `ad_group_ad`, or `asset`.
For updates, provide `update_mask` explicitly when clearing default-valued fields or changing
nested oneofs.

## Diagnose failures

Use this sequence:

1. Preserve `request_id`, error code, message, trigger, and field path.
2. Run `gads fields describe FIELD` for mutability/selectability details.
3. Re-run the exact request with `--validate-only` after correction.
4. Inspect `gads audit list` for the operation count and plan hash.
5. Check the account in the Google Ads UI for billing, policy, identity verification, app
   linkage, and product limitations not exposed as mutable API fields.
