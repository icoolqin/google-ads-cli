# Contributing

Thanks for helping improve Google Ads CLI. Contributions that make account operations safer,
clearer, or easier to test are especially welcome.

## Before opening an issue

- Search existing issues first.
- Do not include developer tokens, OAuth credentials, customer data, request payloads,
  screenshots with account identifiers, or unredacted Google Ads request IDs.
- Use the private process in [SECURITY.md](SECURITY.md) for vulnerabilities.
- For a bug, include the CLI version, Python version, operating system, exact sanitized
  command, expected result, and full sanitized error.

## Development setup

Requirements are Python 3.11+ and
[`uv`](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/your-user/google-ads-cli.git
cd google-ads-cli
uv sync --dev
uv run gads --version
```

Create a branch from `main` and keep each pull request focused on one change.

## Checks

Run all checks before opening a pull request:

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=google_ads_cli --cov-fail-under=55
uv build
```

Tests must not require real Google credentials or mutate an account. Use the installed local
protobuf schema and mocks for unit tests. If a change genuinely needs live integration
testing, document the manual test separately and use a Google Ads test account.

Validate changes to the bundled Codex skill:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" \
  skills/google-ads
```

If that system validator is unavailable, CI still checks the skill's required structure and
the rest of the project.

## Design rules

- Preserve plan mode as the default for every mutation.
- Keep `--validate-only` and `--execute` mutually exclusive.
- Create new campaigns paused unless a reviewed design explicitly requires otherwise.
- Use typed commands for specialized API methods; use generic manifests only for
  `GoogleAdsService.Mutate` resources.
- Never log secrets, binary assets, or full mutation payloads.
- Preserve structured Google Ads error details and `request_id` values after sanitization.
- Add tests for new commands, protobuf compilation, validation, and failure behavior.
- Keep examples advertiser-neutral and use fake account/resource identifiers.
- Use Google Ads API version names explicitly where behavior depends on the schema.

## Pull requests

A pull request should:

1. Explain the problem and the chosen behavior.
2. Describe safety or compatibility implications.
3. Include tests and documentation for user-visible changes.
4. Pass CI without credentials.
5. Update [CHANGELOG.md](CHANGELOG.md) for a user-visible change.

By contributing, you agree that your contribution is licensed under the
[Apache License 2.0](LICENSE).
