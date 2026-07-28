# Setup and authentication

## Contents

- Install the CLI and skill
- Gather Google Ads prerequisites
- Authorize one operator
- Configure profiles
- Verify access
- Understand access levels

## Install the CLI and skill

From the repository checkout:

```bash
./scripts/install-local.sh
gads --version
```

The installer uses an editable `uv tool` installation and links this skill into the user's
Codex skills directory. Source changes become available without publishing a package.

## Gather Google Ads prerequisites

Obtain:

1. A Google Ads manager account that owns the developer token.
2. A Google Cloud project with the Google Ads API enabled.
3. An OAuth 2.0 Desktop App client JSON downloaded from Google Cloud.
4. A Google user with access to the manager/client accounts.
5. The 10-digit client customer ID that will receive campaigns.
6. The 10-digit manager ID to use as `login_customer_id`, when operating through a manager.

New developer tokens start with test-account access. Production accounts require Explorer,
Basic, or Standard access as granted by Google. Do not interpret successful OAuth login as
production API approval.

## Authorize one operator

Keep the downloaded OAuth client file outside the repository. Run:

```bash
gads auth login \
  --client-secrets /absolute/path/to/client_secret.json \
  --login-customer-id 1111111111 \
  --customer-id 2222222222
```

Enter the developer token at the hidden prompt. The command opens Google OAuth, stores an
official `google-ads.yaml` with mode `0600`, and creates a non-secret CLI profile that only
references that credentials file.

For a browserless shell, add `--no-browser`, open the printed URL manually, and complete the
local callback.

## Configure profiles

Create or update a profile without repeating OAuth:

```bash
gads config init \
  --name production \
  --credentials /absolute/path/to/google-ads.yaml \
  --login-customer-id 1111111111 \
  --customer-id 2222222222 \
  --api-version v25
```

Use it with `--profile production` or `GADS_PROFILE=production`.

Environment-only operation is also supported when these variables are set:

```text
GOOGLE_ADS_DEVELOPER_TOKEN
GOOGLE_ADS_CLIENT_ID
GOOGLE_ADS_CLIENT_SECRET
GOOGLE_ADS_REFRESH_TOKEN
GOOGLE_ADS_LOGIN_CUSTOMER_ID   # when using a manager
GADS_CUSTOMER_ID
GADS_API_VERSION
```

Prefer a private credentials file over shell history or checked-in dotenv files.

## Verify access

Run:

```bash
gads --profile production auth test
gads --profile production accounts accessible
gads --profile production accounts hierarchy
gads --profile production accounts show
```

`accounts accessible` returns accounts to which the OAuth user has direct access; it does not
necessarily include every client beneath a manager. Use `accounts hierarchy` for linked child
accounts.

If a call fails, retain the structured `request_id` and error location. Common distinctions:

- `DEVELOPER_TOKEN_NOT_APPROVED`: the token access level cannot reach this production account.
- `USER_PERMISSION_DENIED`: the OAuth user lacks access to the selected customer or manager.
- Login-customer errors: the selected manager is not above the client account.
- OAuth `invalid_grant`: the refresh token was revoked or the OAuth client changed.

## Inspect local paths

Run `gads config path`. The result lists the profile file, default credentials location, and
audit JSONL. `gads config show` never opens or prints credential contents.
