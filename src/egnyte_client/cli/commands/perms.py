from typing import Any, override

import click

from egnyte_client.cli.context import ClientContext
from egnyte_client.cli.group import CommonClickGroup
from egnyte_client.cli.options import confirm, yes_option
from egnyte_client.cli.output import render
from egnyte_client.schemas.permission import PermissionLevel

# The values of `PermissionLevel`, in ascending order of access.
PERMISSION_LEVELS: tuple[PermissionLevel, ...] = (
    "Viewer Only",
    "Viewer",
    "Editor",
    "Full",
    "Owner",
)

# =============================================================================
# CLASS: _GrantType
# =============================================================================


class _GrantType(click.ParamType):
    """
    A `NAME=LEVEL` grant, converted to a `(name, level)` pair.

    The level is matched case-insensitively and returned in Egnyte's spelling.
    It is split at the last `=`, as no level contains one, so a group name
    with an `=` in it still parses.
    """

    name = "NAME=LEVEL"

    @override
    def convert(
        self, value: Any, param: click.Parameter | None, ctx: click.Context | None
    ) -> tuple[str, PermissionLevel]:
        if isinstance(value, tuple):
            return value  # already converted (a default, or a re-parse)

        name, sep, raw_level = str(value).rpartition("=")
        name, raw_level = name.strip(), raw_level.strip()
        if not sep or not name or not raw_level:
            self.fail(f"expected NAME=LEVEL, got {value!r}.", param, ctx)

        if raw_level.lower() == "none":
            self.fail(
                "use --remove-user or --remove-group to remove a permission.",
                param,
                ctx,
            )

        for level in PERMISSION_LEVELS:
            if level.lower() == raw_level.lower():
                return name, level

        choices = ", ".join(repr(level) for level in PERMISSION_LEVELS)
        self.fail(f"{raw_level!r} is not a level; use one of {choices}.", param, ctx)


GRANT = _GrantType()

# =============================================================================
# FUNCTION: _changes
# =============================================================================


def _changes(
    kind: str,
    grants: tuple[tuple[str, PermissionLevel], ...],
    removals: tuple[str, ...],
) -> dict[str, PermissionLevel | None] | None:
    """
    Merge the grants and removals for users or for groups into one delta.

    Naming a user or group twice is refused rather than letting the last
    option win silently, as the two could disagree.

    Returns:
        dict[str, PermissionLevel | None] | None: Name to level, None to
            remove, or None when nothing was named.
    """
    changes: dict[str, PermissionLevel | None] = {}
    for name, level in [*grants, *((name, None) for name in removals)]:
        if name in changes:
            raise click.UsageError(f"The {kind} {name!r} is named more than once.")
        changes[name] = level
    return changes or None


# =============================================================================
# FUNCTION: _describe
# =============================================================================


def _describe(
    kind: str, changes: dict[str, PermissionLevel | None] | None
) -> list[str]:
    """
    Spell out a delta for the confirmation prompt.

    Returns:
        list[str]: One phrase per change, such as `user jdoe -> Full`.
    """
    return [
        f"{kind} {name} -> {level or 'removed'}"
        for name, level in (changes or {}).items()
    ]


@click.group(name="perms", cls=CommonClickGroup)
def group() -> None:
    """
    Inspect and change folder permissions.

    Egnyte refuses top-level folders such as `/Shared`; a PATH needs at least
    two segments.
    """


@group.command(name="get")
@click.argument("path")
@click.pass_obj
def get(ctx: ClientContext, path: str) -> None:
    """
    Show the user and group permissions set on a folder.
    """
    render(ctx.client.get_folder_permissions(path))


@group.command(name="effective")
@click.argument("path")
@click.option(
    "--user",
    "username",
    default=None,
    help="Username to check. Defaults to the caller.",
)
@click.pass_obj
def effective(ctx: ClientContext, path: str, username: str | None) -> None:
    """
    Show a user's effective permission on a folder.

    Prints one level, after groups and inheritance: None, Nav, Viewer Only,
    Viewer, Editor, Full, or Owner.
    """
    render(ctx.client.get_effective_permission(path, username=username))


@group.command(name="set")
@click.argument("path")
@click.option(
    "--user",
    "user_grants",
    type=GRANT,
    multiple=True,
    help=(
        "Grant a user a level, as NAME=LEVEL (repeatable). LEVEL is one of "
        + ", ".join(PERMISSION_LEVELS)
        + "."
    ),
)
@click.option(
    "--group",
    "group_grants",
    type=GRANT,
    multiple=True,
    help="Grant a group a level, as NAME=LEVEL (repeatable).",
)
@click.option(
    "--remove-user",
    "user_removals",
    multiple=True,
    metavar="NAME",
    help="Remove a user's permission (repeatable).",
)
@click.option(
    "--remove-group",
    "group_removals",
    multiple=True,
    metavar="NAME",
    help="Remove a group's permission (repeatable).",
)
@click.option(
    "--inherit/--no-inherit",
    default=None,
    help="Start or stop inheriting permissions from the parent folder.",
)
@click.option(
    "--keep-parent",
    is_flag=True,
    default=False,
    help="With --no-inherit, copy the inherited permissions onto the folder first.",
)
@yes_option
@click.pass_obj
def set_(
    ctx: ClientContext,
    path: str,
    user_grants: tuple[tuple[str, PermissionLevel], ...],
    group_grants: tuple[tuple[str, PermissionLevel], ...],
    user_removals: tuple[str, ...],
    group_removals: tuple[str, ...],
    inherit: bool | None,
    keep_parent: bool,
    yes: bool,
) -> None:
    """
    Grant, change, or remove user and group permissions on a folder.

    Only the users and groups named change; everyone else keeps their
    permission. Quote a level with a space: `--user "jdoe=Viewer Only"`.
    Needs Owner on the folder or admin rights.
    """
    if keep_parent and inherit is not False:
        raise click.UsageError("--keep-parent applies only with --no-inherit.")

    users = _changes("user", user_grants, user_removals)
    groups = _changes("group", group_grants, group_removals)
    if users is None and groups is None and inherit is None:
        raise click.UsageError(
            "Nothing to change; give --user, --group, --remove-user, "
            "--remove-group, or --inherit/--no-inherit."
        )

    summary = _describe("user", users) + _describe("group", groups)
    if inherit is not None:
        if inherit:
            summary.append("inherit from parent")
        elif keep_parent:
            summary.append("stop inheriting (keep parent permissions)")
        else:
            summary.append("stop inheriting")
    confirm(yes, f"Change permissions on {path}: {', '.join(summary)}?")

    ctx.client.set_folder_permissions(
        path,
        user_permissions=users,
        group_permissions=groups,
        inherits_permissions=inherit,
        keep_parent_permissions=True if keep_parent else None,
    )
    click.echo(f"Updated permissions on {path}", err=True)
