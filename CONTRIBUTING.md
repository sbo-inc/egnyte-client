# Contributing

How to work on this repository. The [README](README.md) covers using the package.

## Setup

The repository uses [uv](https://docs.astral.sh/uv/) and a Makefile; `make help` lists every target.

```bash
make install   # sync the locked environment
make check     # ruff and mypy
make format    # apply formatting and lint fixes
make test      # unit tests (offline)
make coverage  # unit tests with coverage (80% minimum)
make build     # build the sdist and wheel
```

`make lock`, `make upgrade`, and `make outdated` manage the locked dependencies.

## Layout

- `src/egnyte_client/operations/` describes each API call as an `Operation`: method, path, query, body, and response parser. Nothing there performs I/O.
- `src/egnyte_client/client.py` and `async_client.py` put operations on the wire. They must stay method-for-method identical; `tests/test_async_client.py` checks the signatures and docstrings.
- `src/egnyte_client/transport.py` holds what both clients share: configuration, token refresh, the rate-limit retry, and error mapping.
- `src/egnyte_client/schemas/` holds the Pydantic models, shaped after live responses rather than the documentation where the two disagree.
- `src/egnyte_client/cli/` is the `egnyte-client` command.

## Tests

The tests run offline against `httpx.MockTransport`, with fixture bodies shaped after live Egnyte responses. They never call a live domain, so nothing spends the domain's API quota. Never commit tokens, API keys, or secrets.

## Releasing

Bump `version` in `pyproject.toml`, run `uv lock`, and add the release to `CHANGELOG.md`. Pushing a `v*` tag that matches the version builds the package, creates the GitHub release, and publishes to PyPI through trusted publishing.
