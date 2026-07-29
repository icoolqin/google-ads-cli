# Changelog

Notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- CI secret scanning for all tracked files
- Targeted diagnostics for wrong OAuth users, expired OAuth grants, and transport failures

### Changed

- OAuth login always shows Google's account picker to prevent accidental account reuse
- macOS uses the native DNS resolver for more reliable operation through VPN/TUN networks
- Setup documentation now distinguishes MCC, OAuth user, OAuth client, and target customer

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
