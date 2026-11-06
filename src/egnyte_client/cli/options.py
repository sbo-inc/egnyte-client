"""
Option decorators and helpers shared by the command modules.

Egnyte's listings page in one of two styles - `--offset` and `--count` on the
v1 APIs, a 1-based `--start-index` and `--count` on the SCIM user and group
APIs - and its destructive calls all ask before acting, so those options are
declared once here rather than spelled out on each command.
"""

import json
from collections.abc import Callable
from typing import Any

import click

# =============================================================================
# FUNCTION: paging_options
# =============================================================================


def paging_options[F: Callable[..., Any]](func: F) -> F:
    """
    Add the `--offset` and `--count` options of the v1 listings.

    Returns:
        F: The decorated command.
    """
    func = click.option(
        "--count", type=int, default=None, help="How many records to return."
    )(func)
    return click.option(
        "--offset", type=int, default=None, help="How many records to skip."
    )(func)


# =============================================================================
# FUNCTION: scim_paging_options
# =============================================================================


def scim_paging_options[F: Callable[..., Any]](func: F) -> F:
    """
    Add the `--start-index` and `--count` options of the SCIM listings.

    Returns:
        F: The decorated command.
    """
    func = click.option("--count", type=int, default=None, help="Page size (max 100).")(
        func
    )
    return click.option(
        "--start-index",
        type=int,
        default=None,
        help="1-based index of the first record.",
    )(func)


# =============================================================================
# FUNCTION: yes_option
# =============================================================================


def yes_option[F: Callable[..., Any]](func: F) -> F:
    """
    Add the `-y/--yes` flag that skips a destructive command's confirmation.

    Returns:
        F: The decorated command.
    """
    return click.option(
        "-y", "--yes", is_flag=True, default=False, help="Skip confirmation."
    )(func)


# =============================================================================
# FUNCTION: confirm
# =============================================================================


def confirm(yes: bool, message: str) -> None:
    """
    Ask before a destructive call, unless `--yes` was given.

    The prompt names what is about to change, which a static confirmation
    option could not. It goes to stderr, so a command's JSON on stdout still
    pipes cleanly after an interactive answer. Declining aborts with exit
    status 1 before any request.
    """
    if not yes:
        click.confirm(message, abort=True, err=True)


# =============================================================================
# FUNCTION: parse_json
# =============================================================================


def parse_json(value: str | None) -> Any:
    """
    Decode an option whose value is a JSON document.

    Structured inputs - metadata values, a namespace's keys - have no sensible
    flat spelling on a command line, so they are passed as JSON and decoded
    here. A malformed document is a usage error rather than a traceback.

    Returns:
        Any: The decoded value, or None if the option was not given.
    """
    if value is None:
        return None
    try:
        return json.loads(value)
    except ValueError as exc:
        raise click.BadParameter(f"expected a JSON document: {exc}") from exc


# =============================================================================
# FUNCTION: exactly_one
# =============================================================================


def exactly_one(*targets: tuple[str, object]) -> None:
    """
    Require exactly one of a command's alternative inputs.

    Each target is a `(label, value)` pair, such as `("PATH", path)` or
    `("--file-id", file_id)`; a value of None counts as not given. Giving none
    or more than one is a usage error naming the alternatives.
    """
    if sum(value is not None for _, value in targets) == 1:
        return
    labels = [label for label, _ in targets]
    listed = (
        " or ".join(labels)
        if len(labels) == 2
        else ", ".join(labels[:-1]) + f", or {labels[-1]}"
    )
    raise click.UsageError(f"Give exactly one of {listed}.")
