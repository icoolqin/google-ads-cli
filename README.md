# Google Ads CLI

[English](README.md) · [简体中文](README.zh-CN.md)

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![Google Ads API v25](https://img.shields.io/badge/Google%20Ads%20API-v25-4285F4)
![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)

`gads` is a safe, scriptable, agent-friendly command-line interface for the Google Ads API.
It combines Google's official Python client with practical commands for account discovery,
GAQL reporting, campaign operations, App Campaign creation, asset uploads, and generic
mutations.

The repository also includes a Codex skill, so an AI agent can use the same guarded workflow
instead of improvising direct API calls.

> [!IMPORTANT]
> This is an independent open-source project. It is not affiliated with or endorsed by
> Google. Google Ads is a trademark of Google LLC.

## Why the write workflow is different

Every mutating command has three explicit modes:

| Mode | Flag | What happens |
| --- | --- | --- |
| Plan | none | Builds and validates the protobuf request locally, then prints it. No credentials or network request are needed. |
| Validate | `--validate-only` | Sends the request to Google Ads for validation without applying it. |
| Execute | `--execute` | Applies the mutation and records a sanitized summary in the local audit log. |

Plan mode is the default. A pasted command cannot spend money merely because it parsed.
New App Campaigns are always created in `PAUSED` status, leaving activation as a separate,
reviewable action.

## What it can do

- Complete a single-user OAuth flow and create a private `google-ads.yaml`
- Manage multiple non-secret profiles
- Discover directly accessible accounts and recursive manager hierarchies
- Run and validate arbitrary GAQL; discover valid Google Ads fields
- Output tables, JSON, JSONL, or CSV
- Run curated account, campaign, ad group, ad, daily, and conversion reports
- Inspect campaigns, budgets, ad groups, ads, assets, and conversion actions
- Pause, enable, or remove campaigns and update daily budgets
- Create an atomic App Campaign with budget, criteria, ad group, app ad, and assets
- Upload image assets and create YouTube assets
- Resolve geographic and language constants
- Apply versioned `GoogleAdsService.Mutate` YAML manifests
- Keep a non-secret JSONL audit trail with deterministic plan hashes

## Before you start

You need:

1. Python 3.11 or newer.
2. [`uv`](https://docs.astral.sh/uv/getting-started/installation/).
3. A Google Ads manager account with a developer token.
4. A Google Cloud project with the Google Ads API enabled.
5. An OAuth 2.0 **Desktop app** client JSON.
6. A Google user that can access the target Ads account.

Google assigns every developer token an access level:

| Access level | Accounts | Daily operations |
| --- | --- | ---: |
| Test | Test accounts | 15,000 |
| Explorer | Test and production | 2,880 production; 15,000 test |
| Basic | Test and production | 15,000 |
| Standard | Test and production | Unlimited for most services |

See Google's current [developer-token guide](https://developers.google.com/google-ads/api/docs/api-policy/developer-token)
and [access-level table](https://developers.google.com/google-ads/api/docs/api-policy/access-levels)
before relying on these limits.

## Install in five minutes

### 1. Install `uv`

On macOS with Homebrew:

```bash
brew install uv
```

For Linux, Windows, or other installation methods, use the
[official uv instructions](https://docs.astral.sh/uv/getting-started/installation/).

### 2. Download this repository

Clone or download the repository, then enter its root directory:

```bash
cd google-ads-cli
```

### 3. Install the CLI and Codex skill

```bash
./scripts/install-local.sh
gads --version
```

The installer creates an editable isolated `uv` tool and links `skills/google-ads` into your
Codex skills directory. To install only the CLI:

```bash
uv tool install .
```

For repository development without a global command:

```bash
uv sync --dev
uv run gads --help
```

## Set up Google access

### 1. Get a developer token

Sign in to a Google Ads **manager account**, open its
[API Center](https://ads.google.com/aw/apicenter), and apply for a developer token. A token
with test access can be used while building the setup; production accounts require an
appropriate production access level.

### 2. Create an OAuth Desktop app

In Google Cloud:

1. Create or select a project.
2. Enable the **Google Ads API**.
3. Configure the OAuth consent screen.
4. Create an OAuth client with application type **Desktop app**.
5. Download the client JSON and keep it outside this repository.

Google's [OAuth guide](https://developers.google.com/google-ads/api/docs/oauth/overview)
describes the current console flow.

### 3. Authenticate

Run:

```bash
gads auth login \
  --client-secrets /absolute/path/to/client_secret.json \
  --login-customer-id 1111111111 \
  --customer-id 2222222222
```

The developer token is requested through a hidden prompt. The command opens Google's OAuth
page, writes a credentials YAML with file mode `0600`, and creates a non-secret CLI profile.

- `customer_id` is the client account whose campaigns and data you manage.
- `login_customer_id` is the manager account used to reach that client. Omit it when you
  access the client directly.
- Hyphenated IDs are accepted and normalized to 10 digits.

For a shell that cannot open a browser, add `--no-browser`, open the printed URL on a browser
that can reach the same local callback, and complete the flow.

### 4. Verify the connection

```bash
gads auth test
gads accounts accessible
gads accounts hierarchy
gads accounts show
```

`accounts accessible` lists direct access only. Use `accounts hierarchy` to find clients
beneath a manager.

## Your first read

Global options go **before** the command group:

```bash
gads --profile default --customer-id 2222222222 --format json campaigns list
```

Useful reads:

```bash
gads --format json accounts show
gads --format json budgets list
gads --format json adgroups list
gads --format json ads list
gads --format json assets list
gads --format json conversions list
```

Curated reports:

```bash
gads reports list
gads --format json reports run campaigns --date-range LAST_30_DAYS
gads --format csv reports run daily --date-range 2026-07-01:2026-07-28
```

Raw GAQL:

```bash
gads query validate --file examples/app-campaign-performance.gaql
gads --format jsonl query run \
  --file examples/app-campaign-performance.gaql \
  --limit 1000
```

Discover field names instead of guessing:

```bash
gads --format json fields describe campaign.app_campaign_setting.app_id
gads --format json fields search 'metrics.%' --limit 50
```

## Your first safe write

Use the same command through plan, validation, execution, and verification:

```bash
# 1. Local plan; no account is changed
gads campaigns set-status 123456789 PAUSED

# 2. Google validates it; no account is changed
gads campaigns set-status 123456789 PAUSED --validate-only

# 3. Apply it
gads campaigns set-status 123456789 PAUSED --execute

# 4. Read it back
gads campaigns get 123456789
```

`--execute` and `--validate-only` cannot be combined. Prefer `PAUSED` for normal shutdowns;
removal is a distinct and generally irreversible Google Ads lifecycle action.

Update a budget using the account's currency:

```bash
gads budgets set-amount 987654321 50
gads budgets set-amount 987654321 50 --validate-only
gads budgets set-amount 987654321 50 --execute
```

Always run `gads accounts show` first and confirm the account currency.

## Create an App Campaign

This generic iOS example creates a local plan only:

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

Replace the example App Store ID, copy, targeting, budget, and bid with real reviewed values.
For Android, use the package name as `--app-id` and pass
`--app-store GOOGLE_APP_STORE`.

The plan creates a non-shared budget, a paused multi-channel campaign, location/language
criteria, an enabled ad group, and an enabled App Ad in one atomic request. Repeat the command
with `--validate-only`, inspect the result, then use `--execute`.

Before enabling spend, verify billing, conversion tracking, account currency, policy status,
targeting, assets, and the app-store record. For in-app action or value bidding, inspect the
real conversion resources first:

```bash
gads --format json conversions list
```

## Upload creative assets

Image uploads are checked locally for supported content and dimensions:

```bash
gads assets upload-image /absolute/path/creative.png --name "US Creative 1"
gads assets upload-image /absolute/path/creative.png \
  --name "US Creative 1" \
  --validate-only
gads assets upload-image /absolute/path/creative.png \
  --name "US Creative 1" \
  --execute
```

Image bytes are redacted from plans and represented by a SHA-256 digest.

Create a YouTube asset:

```bash
gads assets create-youtube VIDEO_ID --name "US Demo 15s"
```

Google Ads assets are generally immutable. Stop one from serving by changing the ad or
association that uses it.

## Use generic mutation manifests

Dedicated commands cover common operations. The versioned manifest escape hatch covers
resources available through `GoogleAdsService.Mutate`:

```bash
gads --format json mutate schema
gads mutate apply examples/pause-campaign.yaml
gads mutate apply examples/pause-campaign.yaml --validate-only
gads mutate apply examples/pause-campaign.yaml --execute
```

Manifest example:

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

Use protobuf JSON field names, string enum labels, and explicit update masks. Use temporary
negative resource IDs when later operations depend on resources created earlier in the same
atomic request.

## Profiles and environment variables

Add another profile without repeating OAuth:

```bash
gads config init \
  --name production \
  --credentials /absolute/path/to/google-ads.yaml \
  --login-customer-id 1111111111 \
  --customer-id 2222222222 \
  --api-version v25
```

Select it with `--profile production` or `GADS_PROFILE=production`.

Environment-only authentication supports:

```text
GOOGLE_ADS_DEVELOPER_TOKEN
GOOGLE_ADS_CLIENT_ID
GOOGLE_ADS_CLIENT_SECRET
GOOGLE_ADS_REFRESH_TOKEN
GOOGLE_ADS_LOGIN_CUSTOMER_ID
GOOGLE_ADS_JSON_KEY_FILE_PATH
GOOGLE_ADS_USE_APPLICATION_DEFAULT_CREDENTIALS
GADS_CUSTOMER_ID
GADS_API_VERSION
```

Use only the credential group for your chosen auth method. Prefer a private credentials file
over shell history or a checked-in dotenv file.

Inspect local paths without revealing secret contents:

```bash
gads config path
gads config show
gads audit list
```

## Use with Codex

`./scripts/install-local.sh` links the bundled `google-ads` skill into the Codex skills
directory. A request such as:

```text
Use $google-ads to report campaign performance for the last 30 days.
```

causes Codex to follow the same read → plan → validate → execute → verify workflow. The skill
does not bypass `--execute`, Google authentication, developer-token access, or account
permissions.

## Troubleshooting

| Symptom | Likely cause and next check |
| --- | --- |
| `DEVELOPER_TOKEN_NOT_APPROVED` | The token cannot access that production account. Check its API Center access level. |
| `USER_PERMISSION_DENIED` | The OAuth user cannot access the selected client or manager. |
| Login-customer error | `login_customer_id` is not a manager above the client, or the IDs were reversed. |
| OAuth `invalid_grant` | The refresh token was revoked, the OAuth client changed, or the consent grant expired. Run `gads auth login` again. |
| “Missing customer ID” | Pass `--customer-id` before the command or store it in the selected profile. |
| A global option is rejected | Put `--profile`, `--customer-id`, `--api-version`, and `--format` before the command group. |
| Plan works but validation fails | Read the structured Google Ads error and `request_id`; then inspect the referenced field with `gads fields describe`. |

Do not paste credentials into an issue. See [SECURITY.md](SECURITY.md) for private reporting.

## Data and security model

- Secrets, OAuth files, keys, dotenv files, caches, and build output are ignored by Git.
- Credentials and profiles are written with mode `0600` where the operating system supports
  POSIX permissions.
- The CLI never prints credential contents.
- Audit records store customer ID, API version, mode, outcome, operation count, plan hash,
  request ID, and sanitized errors—not tokens or full mutation payloads.
- Mutations do not add blanket retries because Google Ads mutates do not provide a universal
  idempotency key.
- Unit tests require no Google credentials and never contact or mutate a Google Ads account.

Review [SECURITY.md](SECURITY.md) before using the CLI in production. You remain responsible
for account permissions, policy compliance, spend, and every command executed with
`--execute`.

## API compatibility

Version `0.1.0` defaults to Google Ads API `v25` through official Python client `31.x`. Run
`gads --version` to see every API schema available in the installed environment. Google Ads
versions have fixed sunset dates, so keep the CLI and lock file current.

## Development

```bash
uv sync --dev
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=google_ads_cli --cov-fail-under=55
uv build
```

Tests use only local protobuf schemas and fixtures. Live `--validate-only` or `--execute`
checks require your own account and are intentionally excluded from CI.

The main code is in `src/google_ads_cli/`; CLI tests are in `tests/`; reusable examples are in
`examples/`; and the Codex skill is in `skills/google-ads/`.

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and
[CHANGELOG.md](CHANGELOG.md) before opening a contribution.

## License

Licensed under the [Apache License 2.0](LICENSE).
