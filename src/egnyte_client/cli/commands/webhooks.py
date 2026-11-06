from collections.abc import Callable
from typing import Any

import click

from egnyte_client.cli.context import ClientContext
from egnyte_client.cli.group import CommonClickGroup
from egnyte_client.cli.options import confirm, yes_option
from egnyte_client.cli.output import render

EVENT_TYPES = click.Choice(
    [
        "fs:*",
        "fs:add_file",
        "fs:add_folder",
        "fs:upload_link",
        "fs:copy_file",
        "fs:copy_folder",
        "fs:delete_file",
        "fs:delete_folder",
        "fs:delete_from_trash",
        "fs:move_file",
        "fs:move_folder",
        "fs:restore_from_trash",
        "fs:lock_file",
        "fs:unlock_file",
        "fs:folder_project_activity",
        "link:*",
        "link:create",
        "link:create_download_link",
        "link:create_upload_link",
        "link:delete",
        "link:delete_download_link",
        "link:delete_upload_link",
        "comment:*",
        "comment:set_comment",
        "comment:remove_comment",
        "permission:*",
        "permission:permission_change",
        "meta:*",
        "meta:add_metadata_key",
        "meta:delete_metadata_key",
        "workflow:created",
        "workflow:completed",
        "workflow:approvaltask_approved",
        "workflow:approvaltask_rejected",
        "group:create",
        "group:delete",
        "group:rename",
        "group:add_members",
        "group:remove_members",
        "group:add_owner",
        "group:remove_owner",
    ]
)

# The secret Egnyte echoes back on every delivery; never printed.
SECRET_FIELDS = {"auth_header"}
AUTH_HEADER_ENV_VAR = "EGNYTE_WEBHOOK_AUTH_HEADER"


def _config_options[F: Callable[..., Any]](func: F) -> F:
    """
    Add the `--event`, `--path`, and `--auth-header` options of create and update.

    Returns:
        F: The decorated command.
    """
    func = click.option(
        "--auth-header",
        default=None,
        envvar=AUTH_HEADER_ENV_VAR,
        show_envvar=True,
        help=(
            "Value Egnyte sends as each delivery's Authorization header; read "
            "from the environment to keep it out of shell history."
        ),
    )(func)
    func = click.option(
        "--path",
        "paths",
        multiple=True,
        help="Folder to watch (repeatable, up to 100). Defaults to the whole domain.",
    )(func)
    return click.option(
        "--event",
        "event_types",
        type=EVENT_TYPES,
        multiple=True,
        help="Event type or wildcard to send (repeatable). Defaults to every event.",
    )(func)


@click.group(name="webhooks", cls=CommonClickGroup)
def group() -> None:
    """
    Register, inspect, and manage webhooks. Needs the `Egnyte.webhooks` scope.
    """


@group.command(name="list")
@click.pass_obj
def list_(ctx: ClientContext) -> None:
    """
    List the webhooks this API client registered.
    """
    render(ctx.client.list_webhooks())


@group.command(name="get")
@click.argument("webhook_id")
@click.pass_obj
def get(ctx: ClientContext, webhook_id: str) -> None:
    """
    Show a webhook's configuration, without its Authorization header.
    """
    render(ctx.client.get_webhook(webhook_id), exclude=SECRET_FIELDS)


@group.command(name="create")
@click.argument("url")
@_config_options
@click.pass_obj
def create(
    ctx: ClientContext,
    url: str,
    event_types: tuple[str, ...],
    paths: tuple[str, ...],
    auth_header: str | None,
) -> None:
    """
    Register a webhook that posts events to an HTTPS URL.

    The URL needs a CA-signed certificate.
    """
    render(
        ctx.client.create_webhook(
            url,
            event_types=list(event_types) or None,  # type: ignore[arg-type]
            paths=list(paths) or None,
            auth_header=auth_header,
        ),
        exclude=SECRET_FIELDS,
    )


@group.command(name="update")
@click.argument("webhook_id")
@click.argument("url")
@_config_options
@click.option(
    "--enable/--disable", "enabled", default=None, help="Set the webhook's status."
)
@click.pass_obj
def update(
    ctx: ClientContext,
    webhook_id: str,
    url: str,
    event_types: tuple[str, ...],
    paths: tuple[str, ...],
    auth_header: str | None,
    enabled: bool | None,
) -> None:
    """
    Reconfigure a webhook. URL is always required; the options are as for create.
    """
    ctx.client.update_webhook(
        webhook_id,
        url,
        event_types=list(event_types) or None,  # type: ignore[arg-type]
        paths=list(paths) or None,
        auth_header=auth_header,
        enabled=enabled,
    )
    click.echo(f"Updated webhook {webhook_id}", err=True)


@group.command(name="status")
@click.argument("webhook_id")
@click.pass_obj
def status(ctx: ClientContext, webhook_id: str) -> None:
    """
    Show whether a webhook is enabled, and when it expires.
    """
    render(ctx.client.get_webhook_status(webhook_id))


@group.command(name="enable")
@click.argument("webhook_id")
@click.pass_obj
def enable(ctx: ClientContext, webhook_id: str) -> None:
    """
    Enable a webhook, such as one Egnyte disabled after failed deliveries.
    """
    render(ctx.client.set_webhook_status(webhook_id, True))


@group.command(name="disable")
@click.argument("webhook_id")
@click.pass_obj
def disable(ctx: ClientContext, webhook_id: str) -> None:
    """
    Disable a webhook; events stop being delivered.
    """
    render(ctx.client.set_webhook_status(webhook_id, False))


@group.command(name="delete")
@click.argument("webhook_id")
@yes_option
@click.pass_obj
def delete(ctx: ClientContext, webhook_id: str, yes: bool) -> None:
    """
    Delete a webhook.
    """
    confirm(yes, f"Delete webhook {webhook_id}?")
    ctx.client.delete_webhook(webhook_id)
    click.echo(f"Deleted webhook {webhook_id}", err=True)
