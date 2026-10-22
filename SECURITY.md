# Security policy

## Reporting a vulnerability

Please **do not** open a public issue for a security problem. Report it privately
through GitHub's [security advisory](../../security/advisories/new) form, or by
email to the address on the maintainer's GitHub profile.

Include: what the issue is, how to reproduce it, and what an attacker gains.
You will get an acknowledgement within a few days. This is a single-maintainer
project, so please allow a reasonable window before disclosing publicly.

## Supported versions

Only the latest commit on `main` is supported. There are no maintained release
branches.

## What is in scope

- Prompt injection that makes the assistant answer from model memory instead of
  the retrieved context, or that leaks the system prompt.
- Retrieval poisoning: content that survives ingestion and later appears as a
  cited source for an unrelated question.
- Authentication or authorisation bypass on the admin and maintenance routes.
- Information disclosure through the trace, metrics or health endpoints.
- Secrets committed to the repository.

## What is out of scope

- Answers that are simply wrong when the retrieved context is also wrong. That
  is a retrieval-quality issue — report it as a normal bug with the query, the
  retrieved passages and what the correct answer should have been.
- Denial of service from a deliberately enormous document upload on your own
  deployment. Configure the upload limit.
- Vulnerabilities in third-party model providers or in the base images, unless
  this repository's configuration makes them exploitable by default.

## Handling of secrets

API keys are read from environment variables (`.env`, which is git-ignored).
The repository must never contain a real key:

- `.gitignore` excludes `.env` and common key files.
- The `detect-private-key` pre-commit hook blocks private keys.
- CI fails if any Python file contains HTML-escaped source, which is how
  mangled secrets have leaked into diffs before.

If you find a committed key, treat it as compromised: rotate it first, then tell
the maintainer. Rotating is what limits the damage; deleting the commit is not.
