# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in OpenDemocracy AI, please report it responsibly.

**Do NOT open a public issue for security vulnerabilities.**

Instead, please email **[security@opendemocracy.ai]** (placeholder — update when established) with:

1. A description of the vulnerability
2. Steps to reproduce
3. Potential impact
4. Suggested fix (if any)

We will acknowledge receipt within 48 hours and aim to provide a fix or mitigation plan within 7 days for critical issues.

## Supported Versions

| Version | Supported |
|---|---|
| Latest on `main` | Yes |
| Previous releases | Best effort |

## Security Priorities

Given that OpenDemocracy AI handles democratic participation data, security is foundational:

1. **Privacy preservation**: Individual responses must never be recoverable from outputs.
2. **Input integrity**: Sybil attacks and manipulation must be detectable and resistible.
3. **System availability**: The platform must resist denial-of-service attacks.
4. **Data integrity**: Results must be tamper-proof and auditable.
5. **Supply chain security**: Dependencies are reviewed and pinned.

## Security Practices

- Dependencies are regularly audited for known vulnerabilities.
- All inputs are validated and sanitized.
- Authentication and authorization follow the principle of least privilege.
- Sensitive configuration uses environment variables, never committed to the repository.
- CI runs security linting on every pull request.

## Disclosure Policy

We follow coordinated disclosure:
- Reporter notifies us privately.
- We confirm and assess the vulnerability.
- We develop and test a fix.
- We release the fix and publicly disclose the vulnerability with credit to the reporter (unless they prefer anonymity).

## Bug Bounty

We do not currently have a formal bug bounty program. We will publicly credit all security researchers who responsibly report valid vulnerabilities (with their permission).
