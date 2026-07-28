# Security Policy

Google Ads CLI can execute changes that affect real advertising spend. Treat its configuration
and execution environment as production-sensitive.

## Supported versions

| Version | Security updates |
| --- | --- |
| `0.1.x` | Supported |
| Older versions | Not supported |

Until the first stable release, security fixes may include breaking changes when necessary to
protect credentials or prevent unsafe account mutations.

## Report a vulnerability privately

Do not open a public issue for a suspected vulnerability.

After this repository is published on GitHub, use **Security → Report a vulnerability** to
open a private security advisory. If private reporting is unavailable, contact the maintainer
through the private contact method listed on the repository owner's GitHub profile.

Include:

- affected version or commit;
- impact and attack scenario;
- minimal reproduction using fake account IDs and redacted data;
- suggested mitigation, if known.

Never send a real developer token, OAuth client secret, refresh token, service-account key,
credentials file, or unredacted customer data. Revoke and rotate any secret that was exposed.

## Operational safety

- Review the printed plan before using `--validate-only` or `--execute`.
- Use a Google Ads test account for integration testing.
- Apply least-privilege Google account and filesystem permissions.
- Keep OAuth and service-account files outside the repository.
- Protect the machine and user account that hold the refresh token.
- Confirm the target customer ID, manager hierarchy, currency, budget, bid, status, and
  conversion setup before executing a mutation.
- Inspect the resource after every write.
- Back up the local audit log according to your own retention policy; it is not a substitute
  for Google Ads change history.

## Scope

Reports about this project's code, installer, credential handling, audit handling, protobuf
compilation, or mutation safeguards are in scope. Vulnerabilities in Google Ads, Google's
official client library, OAuth infrastructure, or third-party dependencies should also be
reported to the relevant upstream project.
