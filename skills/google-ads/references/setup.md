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

“Manager account” means an MCC account type, not an administrator role on a client account.
The API Center only appears in a non-test manager account. New applications may receive
Explorer access automatically; otherwise they start with test-account access. Production
accounts require Explorer, Basic, or Standard access as granted by Google. Do not interpret
successful OAuth login as production API approval.

Keep four identities separate during diagnosis:

1. Developer-token owner: the MCC whose API Center issued the token.
2. OAuth client: the Desktop app in the Google Cloud project.
3. OAuth Google user: the human user whose refresh token is stored.
4. Login and target customers: the manager request header and the account being queried.

If the OAuth app is in Testing, add the intended OAuth Google user under **Google Auth
Platform > Audience > Test users** and save before authorizing. MCC access does not make the
user an OAuth test user. Testing-mode authorization for the Ads scope expires after seven
days, including its refresh token.

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
references that credentials file. The account picker is always displayed. Choose a Google
user that can directly access the manager passed as `--login-customer-id`; do not merely
choose the browser's currently signed-in user.

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
gads --profile production accounts hierarchy --manager-id 1111111111
gads --profile production accounts show
```

`accounts accessible` returns accounts to which the OAuth user has direct access; it does not
necessarily include every client beneath a manager. Use `accounts hierarchy` for linked child
accounts and seed it with the manager ID. If the configured login manager is absent from
`accounts accessible`, `auth test` stops early with a targeted wrong-OAuth-user diagnosis.

If a call fails, retain the structured `request_id` and error location. Common distinctions:

- `DEVELOPER_TOKEN_NOT_APPROVED`: the token access level cannot reach this production account.
- `USER_PERMISSION_DENIED`: the OAuth user lacks access to the selected customer or manager.
- Login-customer errors: the selected manager is not above the client account.
- OAuth `invalid_grant`: the refresh token was revoked or the OAuth client changed.
- OAuth `403 access_denied` while the app is Testing: add the user to OAuth test users.
- `ServiceUnavailable`, DNS, or no route to host: check VPN/proxy/IPv6. On custom networks,
  try `GRPC_DNS_RESOLVER=native gads auth test`; macOS uses the native resolver automatically.

## Inspect local paths

Run `gads config path`. The result lists the profile file, default credentials location, and
audit JSONL. `gads config show` never opens or prints credential contents.
