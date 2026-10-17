# Security

## Scope

This repository contains a demonstration tool and synthetic data. It does not contain employer data, customer data, credentials, or personal information.

## Reporting

If you find a security issue, please open a private security advisory on GitHub rather than a public issue.

## Design choices

- No third-party dependencies.
- The optional local model is called on `127.0.0.1` only.
- No secrets are committed. `.env` files, keys, and internal-only artifacts are ignored.
- Secret scanning and push protection are enabled on the GitHub repository.
- Dependabot alerts are enabled.

## What this is not

This is a portfolio demonstration, not a production system. Do not run it against confidential data without adding authentication, access control, and an audit trail.

## Account hygiene

The repository owner should have two-factor authentication enabled on GitHub. This is the single highest-value protection for the account and the code.
