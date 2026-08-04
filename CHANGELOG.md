# Changelog

Notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `scripts/check_identifiers.py` blocks real account identifiers from entering this public
  repository, plus a `pre-commit` config that runs it before every commit. `detect-secrets`
  recognizes credentials, not business identifiers — a real customer ID, account balance, or
  live ad headline is invisible to it. The check pairs a gitignored `.private-values`
  denylist with an `.identifier-allowlist.txt` allowlist, so identifiers nobody thought to
  list are caught too.

## [0.2.0] - 2026-08-04

### Added

- `gads ads assets AD_ID` reads an App Ad's real asset list from `app_ad.*`, with slot
  fill and per-orientation coverage. `ad_group_ad_asset_view` retains historical
  associations and can report more assets than the ad actually carries, so it is not
  used as the source of truth.
- `gads ads set-assets AD_ID` edits App Ad assets in place. App Ad asset fields are
  whole-field replacements, so the command reads current assets first and applies an
  `--add-*`/`--remove-*` delta on top; per-ad-group caps, duplicates, removing an absent
  asset, and stripping every visual asset are all rejected before the API is called.
- `gads billing show` reports account funding, remaining balance, and spend runway.
  `account_budget` returns the net spendable amount, so `--tax-rate` prints a
  gross-equivalent column that reconciles with the web UI's "Available funds".
- `gads changes list` surfaces `change_event` history (who changed what, when), supplying
  the bounded date window and `LIMIT` the resource requires.
- Report presets `assets` (per-asset performance labels), `network` (Search / YouTube /
  Display / Discover split), and `daily-campaign`.

### Changed

- CI secret scanning for all tracked files
- Targeted diagnostics for wrong OAuth users, expired OAuth grants, and transport failures
- OAuth login always shows Google's account picker to prevent accidental account reuse
- macOS uses the native DNS resolver for more reliable operation through VPN/TUN networks
- Setup documentation now distinguishes MCC, OAuth user, OAuth client, and target customer

### Notes

- Promotional account credits, SKAdNetwork reports, and Google's own per-orientation Ad
  Strength breakdown for App ads are not exposed by the Google Ads API and remain
  web-UI-only. `asset_group.asset_coverage` is Performance Max only.

## [0.1.0] - 2026-07-28

### Added

- Safe plan, validate-only, and execute modes for Google Ads mutations
- OAuth login, profiles, account hierarchy discovery, GAQL, field discovery, and reports
- Campaign and budget operations
- Atomic App Campaign creation with image and YouTube asset support
- Generic versioned GoogleAdsService mutation manifests
- Sanitized local mutation audit records
- Bundled Codex skill
- English and Simplified Chinese documentation
