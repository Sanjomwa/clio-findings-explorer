# Security policy

## Reporting a vulnerability

Please report it privately, not in a public issue: on this repository's **Security** tab, choose **Report a vulnerability** (GitHub private vulnerability reporting). Say what you found, where (a URL or a file), and how to reproduce it.

This is a single-maintainer project, so replies are best effort. I aim to acknowledge a report within 7 days and to tell you what I will do about it.

## Scope

- **In scope:** the live site (frontend and API on Cloud Run), the code in this repository and its GitHub Actions workflows.
- **Out of scope:** denial of service and load testing (the site runs on a small budget with a spend cap; please do not flood it), social engineering, and the third-party services it runs on (Google Cloud, Neon, GitHub).

## Supported versions

Only the current `main` branch and the deployed site.

## How the site is protected

See [docs/security.md](docs/security.md): each security layer, what it stops, the evidence, and the known gaps.
