# Contributing

Thanks for taking a look. This is a single-maintainer project, so the process
is deliberately light — but the checks below are the ones that matter.

## What this repository is optimised for

A retrieval-augmented question-answering system whose answers must be
*traceable*. Two properties are non-negotiable and any change is reviewed
against them:

1. **Every claim in an answer is attributable to a retrieved passage.** If a
   change makes it easier for the model to answer from memory, it is a
   regression even if the answer reads better.
2. **Retrieval quality is measured, not asserted.** A change that claims to
   improve retrieval must come with a number produced by the evaluation
   harness, not an impression.

## Getting set up

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in your own API key

# frontend
cd frontend
npm ci
```

Optional dependencies (OCR providers, LoRA fine-tuning) are listed in
`backend/requirements-optional.txt`. The application degrades gracefully when
they are absent.

## Running the tests

There are two suites, and they are split on purpose.

**Unit tests — what CI runs.** No model downloads, no vector index, finished in
seconds:

```bash
pip install -r tests/requirements-ci.txt
PYTHONPATH=backend python -m pytest tests -v
```

**Full suite — run before touching retrieval or generation.** Needs the whole
stack (`faiss`, `torch`, `sentence-transformers`) and a built index:

```bash
cd backend && python -m pytest tests -v
```

If you add a test that needs the full stack, put it in `backend/tests/`. If it
can run with plain `pytest`, put it in `tests/` so CI picks it up.

## Source integrity

CI fails if any Python file does not parse, or if a file contains HTML-escaped
source (`-&gt;`, `&lt;`, `&amp;`). Both have happened: files pasted through a
web form arrive escaped and then fail with a `SyntaxError` hundreds of lines
away from the real cause. Run the same check locally with:

```bash
make integrity
```

## Linting

`ruff` is configured in `pyproject.toml` with a deliberately narrow rule set
(`E9`, `F63`, `F7`, `F82`) — the rules that catch defects rather than the rules
that enforce a style. The broader style rules are **not** enforced yet; the
existing codebase would not pass them and a mass reformat would bury the
history. Narrow the debt, do not pretend it is gone.

`pre-commit install` wires the hooks up. They run on changed files only.

## Commit messages

Conventional Commits, because the log is read by humans:

```
feat: add RRF fusion weight as a query-class parameter
fix: restore BM25 exact-match ranking for card names
docs: correct the backend stack description in the README
test: cover the hard-evidence constraint injection
chore: bump ruff to 0.5.7
```

One logical change per commit. If a commit needs "and" to describe it, split it.

## Pull requests

Before opening one, check:

- [ ] `make integrity` passes
- [ ] `make test` passes
- [ ] New behaviour has a test that fails without the change
- [ ] No `.env`, API keys, vector indexes, model weights or datasets are staged
- [ ] If retrieval or generation changed, the evaluation numbers are in the PR
      description: which config, which corpus, which metric, and the delta
- [ ] The README is still true (stack, structure, commands)
- [ ] Numbers are reproducible from the repository, or explicitly labelled as
      historical local measurements

## What not to commit

| Never committed | Why |
|---|---|
| `.env`, API keys, tokens | secrets; `.gitignore` and the pre-commit `detect-private-key` hook block the common cases |
| `data/`, `vector_db/`, `*.faiss`, `*.pkl` | large, regenerable, and they make a clone useless |
| model weights (`*.bin`, `*.safetensors`, `*.pt`) | dozens of GB; reference the model id in config instead |
| `node_modules/`, `frontend/dist/` | build output |
| load-test result dumps (`*.csv`, `*.html` from Locust) | large; summarise the numbers in the docs instead |

## Reporting a security issue

See [SECURITY.md](SECURITY.md) — please do not open a public issue for a
vulnerability.

## Code of conduct

Be direct about the code and generous about the person. Disagreement about a
design is welcome; dismissal of a contributor is not.
