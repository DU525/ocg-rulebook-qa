# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `## News`, a table of contents, and a *Known limitations* section in the
  README, so a reader can see the current state without reading the history.
- Repository governance files: `LICENSE` (MIT), `CONTRIBUTING.md`,
  `SECURITY.md`, `.editorconfig`, `.gitattributes`.
- CI (`.github/workflows/ci.yml`) with three jobs: source integrity, unit tests,
  and the frontend build.
- `scripts/check_escaped_source.py`, which rejects Python files containing
  HTML-escaped source. Five load-test scripts and one benchmark script had been
  committed in that state and could not be imported.
- `Makefile` wrappers for the commands CI runs.
- `tests/requirements-ci.txt` — the minimal dependency set the unit tests need.

### Fixed

- **Load-test scripts could not run.** `backend/tests/locustfile*.py` contained
  `&lt;` where `<` was intended, so every file raised a `SyntaxError`. The
  reported throughput figures therefore could not be reproduced from this
  repository; the scripts now compile, and the README describes them as
  historical local measurements.
- **`backend/scripts/download_10w_data.py` could not be parsed.** It passed
  `def=def_` as a keyword argument, but `def` is a reserved word; the template
  key is now supplied through `**{"def": def_}`.
- **`backend/app/db/test_quantized_index.py` could not be parsed.** It had been
  pasted through an HTML-escaping channel.
- **`backend/requirements.txt` was incomplete.** `aiohttp`, `beautifulsoup4`,
  `jieba`, `rank-bm25`, `redis`, `simhash`, `tenacity`, `text2vec` and
  `whoosh` are imported directly by the backend but were not declared, so a
  fresh install was not a runnable install.
- README referenced a `backend_fastapi/` directory and two documents that do
  not exist in the repository.
- The clone command in the README used a `your-username` placeholder.

### Removed

- `SHOWCASE.md`. It was not project documentation: its title was "referral
  presentation plan", it carried a "reasons to recommend to recruiters"
  section, an unfilled `[your GitHub link]` placeholder, and a note about which
  files to send to a senior schoolmate before an interview. Material whose
  purpose is to improve how the project reads in an interview does not belong
  in the repository that contains the project. The file is archived locally.
- Career framing from the documentation and from one docstring: the API protocol
  note no longer says it exists "for interview display", the screenshot guide
  no longer mentions referral showcases, and the multimodal provider docstring
  no longer calls itself an "interview bonus point".

### Changed

- README now states the backend stack that the code actually uses (Flask) and
  attributes throughput figures to the path they were measured on.

## [1.0.0] - 2026-05-23

### Added

- Multi-stage retrieval: vector search, BM25, reciprocal rank fusion, and
  Cross-Encoder reranking.
- Three-level cache: in-process LRU, Redis, and SimHash semantic cache.
- Retrieval traceability panel in the UI: the retrieved passages and the score
  from each retrieval channel are shown under every answer.
- Conversation memory sidebar: working memory and long-term facts, surfaced to
  the user.
- RAGAS-based evaluation pipeline and a Locust load-test harness.
- Docker Compose stack, Kubernetes manifests (Deployment, Service, HPA, PVC),
  and Prometheus alerting with Feishu notifications.

[Unreleased]: https://github.com/DU525/ocg-rulebook-qa/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/DU525/ocg-rulebook-qa/releases/tag/v1.0.0
