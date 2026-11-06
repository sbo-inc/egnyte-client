import logging
import sys

import click
import httpx

from egnyte_client.cli.commands import (
    audit,
    auth,
    bookmarks,
    comments,
    events,
    fs,
    groups,
    links,
    metadata,
    perms,
    search,
    trash,
    users,
    webhooks,
)
from egnyte_client.cli.context import ClientContext
from egnyte_client.cli.group import CommonClickGroup
from egnyte_client.errors import EgnyteError

CLI_DOCS = """
Egnyte Public API command-line interface.

Connection settings are read from environment variables:

\b
- EGNYTE_DOMAIN as the domain (`acme`, `acme.egnyte.com`, or a URL).
- EGNYTE_ACCESS_TOKEN as the OAuth bearer token.
- EGNYTE_REFRESH_TOKEN, EGNYTE_CLIENT_ID, and EGNYTE_CLIENT_SECRET to
  refresh an expired token automatically.
- EGNYTE_API_HEADERS as a JSON object of extra request headers.
- EGNYTE_API_TIMEOUT as a per-request timeout in seconds.
- EGNYTE_API_RETRIES as a connection-retry count.
"""


@click.group(
    cls=CommonClickGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
    help=CLI_DOCS,
)
@click.option(
    "--log",
    is_flag=True,
    default=False,
    help="Log each request, retry, and token refresh to stderr.",
)
@click.version_option(package_name="egnyte-client", prog_name="egnyte-client")
@click.pass_context
def cli(ctx: click.Context, log: bool) -> None:
    if log:
        enable_logging()
    # An embedding runtime (or a test) may pass its own context in `obj`.
    if not isinstance(ctx.obj, ClientContext):
        ctx.obj = ClientContext()


LOG_HANDLER_NAME = "egnyte-client-cli"


def enable_logging() -> None:
    """
    Send the package's log records to stderr, as `--log` asks.

    The CLI is an application, so it may configure logging; the library itself
    only attaches a NullHandler. The handler is replaced rather than added on
    each call, so repeated invocations in one process neither duplicate lines
    nor write to a stream that has since been closed.
    """
    package = logging.getLogger("egnyte_client")
    for handler in [h for h in package.handlers if h.get_name() == LOG_HANDLER_NAME]:
        package.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr)
    handler.set_name(LOG_HANDLER_NAME)
    handler.setFormatter(logging.Formatter("egnyte-client: %(message)s"))
    package.addHandler(handler)
    package.setLevel(logging.DEBUG)


# Registration order is help order; EGNYTE_CLI_DISABLE gates at runtime.
for command in (
    auth.group,
    fs.group,
    search.command,
    trash.group,
    links.group,
    perms.group,
    comments.group,
    bookmarks.group,
    metadata.group,
    users.group,
    groups.group,
    events.group,
    webhooks.group,
    audit.group,
):
    cli.add_command(command)


def main() -> None:
    """
    Console-script entry point.

    Translates expected errors into a non-zero exit with a readable message
    instead of a traceback.
    """
    try:
        cli(standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        sys.exit(exc.exit_code)
    except click.exceptions.Abort:
        sys.exit(1)
    except EgnyteError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except httpx.HTTPError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("egnyte_client").debug("CLI error", exc_info=True)
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


__all__ = ["cli", "main"]
