import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import click
from pydantic import BaseModel

type Renderable = (
    BaseModel | Sequence[BaseModel] | Mapping[str, object] | str | int | bool | None
)

# =============================================================================
# FUNCTION: render
# =============================================================================


def render(value: Renderable, *, exclude: set[str] | None = None) -> None:
    """
    Print a command's result to stdout.

    Models, lists of models, and mappings are printed as indented JSON, so the
    output pipes into `jq` unchanged. A bare string or number is echoed as-is,
    and a bool as `true`/`false`, so they can be captured in a shell variable.
    `exclude` drops the named top-level fields from model output (e.g. to
    redact a secret). `None` prints nothing.
    """
    if value is None:
        return
    if isinstance(value, bool):
        click.echo("true" if value else "false")
        return
    if isinstance(value, str | int):
        click.echo(value)
        return
    payload: object
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude=exclude)
    elif isinstance(value, Mapping):
        payload = dict(value)
    else:
        payload = [item.model_dump(mode="json", exclude=exclude) for item in value]
    click.echo(json.dumps(payload, indent=2, default=str))


# =============================================================================
# FUNCTION: write_bytes
# =============================================================================


def write_bytes(content: bytes, output: str) -> None:
    """
    Write downloaded content to a file, or to stdout when `output` is `-`.

    Stdout is written through the binary buffer rather than `click.echo`, so a
    PDF or a zip survives being redirected. A note of what was written goes to
    stderr, out of the way of the content.
    """
    if output == "-":
        sys.stdout.buffer.write(content)
        sys.stdout.buffer.flush()
        return
    Path(output).write_bytes(content)
    click.echo(f"Wrote {len(content)} bytes to {output}", err=True)
