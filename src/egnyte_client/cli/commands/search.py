from datetime import datetime

import click

from egnyte_client.cli.context import ClientContext
from egnyte_client.cli.output import render
from egnyte_client.schemas.search import MetadataFilter


@click.command(name="search")
@click.argument("query", required=False)
@click.option("--folder", default=None, help="Search only this folder and below.")
@click.option(
    "--type",
    "type_",
    type=click.Choice(["file", "folder", "all"], case_sensitive=False),
    default=None,
    help="Match only files or only folders.",
)
@click.option(
    "--in",
    "fields",
    type=click.Choice(["filename", "content", "comments"], case_sensitive=False),
    multiple=True,
    help="Where a file must match (repeatable). Defaults to everywhere.",
)
@click.option(
    "--match-all",
    is_flag=True,
    default=False,
    help="Require every query term, not any.",
)
@click.option(
    "--metadata",
    "metadata",
    type=(str, str, str),
    multiple=True,
    metavar="NAMESPACE KEY VALUE",
    help="Custom metadata that must equal VALUE (repeatable).",
)
@click.option(
    "--modified-after",
    type=click.DateTime(),
    default=None,
    help="Modified at or after (YYYY-MM-DD or ISO 8601, UTC).",
)
@click.option(
    "--modified-before",
    type=click.DateTime(),
    default=None,
    help="Modified before (YYYY-MM-DD or ISO 8601, UTC).",
)
@click.option(
    "--sort-by",
    type=click.Choice(["score", "last_modified", "size", "name"]),
    default=None,
    help="Sort field; relevance by default.",
)
@click.option(
    "--sort-direction",
    type=click.Choice(["ascending", "descending"]),
    default=None,
)
@click.option("--offset", type=int, default=None, help="Index of the first hit.")
@click.option("--count", type=click.IntRange(1, 20), default=None, help="Page size.")
@click.pass_obj
def command(
    ctx: ClientContext,
    query: str | None,
    folder: str | None,
    type_: str | None,
    fields: tuple[str, ...],
    match_all: bool,
    metadata: tuple[tuple[str, str, str], ...],
    modified_after: datetime | None,
    modified_before: datetime | None,
    sort_by: str | None,
    sort_direction: str | None,
    offset: int | None,
    count: int | None,
) -> None:
    """
    Search file and folder names, file content, comments, and metadata.

    Prints one page of hits with `has_more`; pass `--offset` to page on.
    """
    if not query and not metadata:
        raise click.UsageError("Give a QUERY, --metadata, or both.")

    render(
        ctx.client.search(
            query,
            folder=folder,
            type=type_.upper() if type_ else None,  # type: ignore[arg-type]
            file_query_fields=[f.upper() for f in fields] or None,
            query_operator="ALL" if match_all else None,
            metadata_filters=[
                MetadataFilter(namespace=namespace, key=key, value=value)
                for namespace, key, value in metadata
            ]
            or None,
            modified_after=modified_after,
            modified_before=modified_before,
            sort_by=sort_by,  # type: ignore[arg-type]
            sort_direction=sort_direction,  # type: ignore[arg-type]
            offset=offset,
            count=count,
        )
    )
