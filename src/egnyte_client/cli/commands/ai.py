from collections.abc import Callable
from datetime import datetime
from typing import Any

import click
from pydantic import TypeAdapter, ValidationError

from egnyte_client.cli.context import ClientContext
from egnyte_client.cli.group import CommonClickGroup
from egnyte_client.cli.options import parse_json
from egnyte_client.cli.output import render
from egnyte_client.operations.ai import (
    DEFAULT_AI_POLL_INTERVAL,
    DEFAULT_AI_WAIT_TIMEOUT,
)
from egnyte_client.schemas.ai import ChatMessage

_HISTORY = TypeAdapter(list[ChatMessage])

# =============================================================================
# FUNCTIONS: Shared options
# =============================================================================


def _parse_history(
    ctx: click.Context, param: click.Parameter, value: str | None
) -> list[ChatMessage] | None:
    """
    Decode `--history` and check it against the message model.
    """
    raw: object = parse_json(value)
    if raw is None:
        return None
    try:
        return _HISTORY.validate_python(raw)
    except ValidationError as exc:
        raise click.BadParameter(
            "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors(include_url=False)
            )
        ) from exc


def _history_option[F: Callable[..., Any]](func: F) -> F:
    """
    Add the `--history` option carrying earlier conversation turns.

    Returns:
        F: The decorated command.
    """
    return click.option(
        "--history",
        callback=_parse_history,
        default=None,
        metavar="JSON",
        help='Earlier turns, as [{"role": "user"|"assistant", "content": "..."}].',
    )(func)


def _wait_options[F: Callable[..., Any]](func: F) -> F:
    """
    Add the `--wait`, `--interval`, and `--timeout` options for background answers.

    Returns:
        F: The decorated command.
    """
    func = click.option(
        "--timeout",
        type=click.FloatRange(min=0),
        default=DEFAULT_AI_WAIT_TIMEOUT,
        show_default=True,
        help="With --wait, give up after this many seconds.",
    )(func)
    func = click.option(
        "--interval",
        type=click.FloatRange(min=0),
        default=DEFAULT_AI_POLL_INTERVAL,
        show_default=True,
        help="With --wait, seconds between checks; each check is an AI call.",
    )(func)
    return click.option(
        "--wait",
        is_flag=True,
        default=False,
        help="Poll until the answer is ready and print it.",
    )(func)


# =============================================================================
# GROUP: ai
# =============================================================================


@click.group(name="ai", cls=CommonClickGroup)
def group() -> None:
    """
    Ask Egnyte AI about documents, the AI Assistant, and agents; hybrid search.

    These calls need the `Egnyte.ai` scope and are limited to 100 a day,
    10 a minute, and 2 a second per token.
    """


@group.command(name="ask")
@click.argument("entry_id")
@click.argument("question")
@click.option(
    "--citations", is_flag=True, default=False, help="Include cited passages."
)
@_history_option
@click.pass_obj
def ask(
    ctx: ClientContext,
    entry_id: str,
    question: str,
    citations: bool,
    history: list[ChatMessage] | None,
) -> None:
    """
    Ask a question about one file version, by ENTRY_ID.
    """
    render(
        ctx.client.ask_document(
            entry_id,
            question,
            include_citations=citations or None,
            chat_history=history,
        )
    )


@group.command(name="summarize")
@click.argument("entry_id")
@_history_option
@click.pass_obj
def summarize(
    ctx: ClientContext, entry_id: str, history: list[ChatMessage] | None
) -> None:
    """
    Summarize one file version, by ENTRY_ID.
    """
    render(ctx.client.summarize_document(entry_id, chat_history=history))


@group.command(name="assistant-ask")
@click.argument("question")
@click.option(
    "--folder-id",
    "folder_ids",
    multiple=True,
    help="Use this folder as context (repeatable).",
)
@click.option(
    "--entry-id",
    "entry_ids",
    multiple=True,
    help="Use this file version as context (repeatable).",
)
@click.option(
    "--all",
    "search_all",
    is_flag=True,
    default=False,
    help="Search all domain content.",
)
@click.option("--web", is_flag=True, default=False, help="Include web search results.")
@click.option(
    "--citations", is_flag=True, default=False, help="Include cited passages."
)
@click.option("--conversation-id", default=None, help="Continue this conversation.")
@click.option("--mcp-selection-id", default=None, help="MCP server selection to use.")
@click.option("--model-name", default=None, help="Display name of the model.")
@click.option(
    "--model-version",
    default=None,
    help="Model to answer with (Egnyte's default: gemini-2.5-flash).",
)
@_history_option
@_wait_options
@click.pass_obj
def assistant_ask(
    ctx: ClientContext,
    question: str,
    folder_ids: tuple[str, ...],
    entry_ids: tuple[str, ...],
    search_all: bool,
    web: bool,
    citations: bool,
    conversation_id: str | None,
    mcp_selection_id: str | None,
    model_name: str | None,
    model_version: str | None,
    history: list[ChatMessage] | None,
    wait: bool,
    interval: float,
    timeout: float,
) -> None:
    """
    Ask the AI Assistant a question across files, folders, or the domain.

    Prints the execution to poll with `ai assistant-status`, or with --wait
    the final status, alongside the IDs for a follow-up question.
    """
    execution = ctx.client.ask_assistant(
        question,
        folder_ids=list(folder_ids) or None,
        entry_ids=list(entry_ids) or None,
        search_all=search_all or None,
        web_search=web or None,
        include_citations=citations or None,
        chat_history=history,
        conversation_id=conversation_id,
        mcp_selection_id=mcp_selection_id,
        model_name=model_name,
        model_version=model_version,
    )
    if not wait:
        render(execution)
        return
    status = ctx.client.wait_for_assistant(
        execution.execution_id, interval=interval, timeout=timeout
    )
    render(
        {
            "conversation_id": execution.conversation_id,
            "execution_id": execution.execution_id,
            **status.model_dump(mode="json"),
        }
    )


@group.command(name="assistant-status")
@click.argument("execution_id")
@click.option(
    "--no-citations",
    is_flag=True,
    default=False,
    help="Leave out the cited passages.",
)
@_wait_options
@click.pass_obj
def assistant_status(
    ctx: ClientContext,
    execution_id: str,
    no_citations: bool,
    wait: bool,
    interval: float,
    timeout: float,
) -> None:
    """
    Show an AI Assistant question's status, and its answer once done.
    """
    include = False if no_citations else None
    if wait:
        render(
            ctx.client.wait_for_assistant(
                execution_id,
                include_citations=include,
                interval=interval,
                timeout=timeout,
            )
        )
        return
    render(ctx.client.get_assistant_execution(execution_id, include_citations=include))


@group.command(name="agents")
@click.option(
    "--sort-by",
    type=click.Choice(["name", "createdOn"]),
    default=None,
    help="Sort field; name by default.",
)
@click.option(
    "--sort-order",
    type=click.Choice(["asc", "desc"]),
    default=None,
    help="Sort direction; asc by default.",
)
@click.pass_obj
def agents(ctx: ClientContext, sort_by: str | None, sort_order: str | None) -> None:
    """
    List the AI agents configured for the domain.
    """
    render(
        ctx.client.list_agents(
            sort_by=sort_by,  # type: ignore[arg-type]
            sort_order=sort_order,  # type: ignore[arg-type]
        )
    )


@group.command(name="agent-ask")
@click.argument("agent_id")
@click.argument("question")
@click.option("--instructions", default=None, help="A system prompt for this question.")
@click.option(
    "--entry-id",
    "entry_ids",
    multiple=True,
    help="Use this file version as context (repeatable).",
)
@click.option(
    "--folder-id",
    "folder_ids",
    multiple=True,
    help="Use this folder as context (repeatable).",
)
@click.option("--conversation-id", default=None, help="Continue this conversation.")
@_history_option
@_wait_options
@click.pass_obj
def agent_ask(
    ctx: ClientContext,
    agent_id: str,
    question: str,
    instructions: str | None,
    entry_ids: tuple[str, ...],
    folder_ids: tuple[str, ...],
    conversation_id: str | None,
    history: list[ChatMessage] | None,
    wait: bool,
    interval: float,
    timeout: float,
) -> None:
    """
    Ask an AI agent a question.

    Prints the request to poll with `ai agent-status`, or with --wait the
    final status, alongside the IDs for a follow-up question.
    """
    execution = ctx.client.ask_agent(
        agent_id,
        question,
        instructions=instructions,
        entry_ids=list(entry_ids) or None,
        folder_ids=list(folder_ids) or None,
        chat_history=history,
        conversation_id=conversation_id,
    )
    if not wait:
        render(execution)
        return
    status = ctx.client.wait_for_agent(
        agent_id, execution.request_id, interval=interval, timeout=timeout
    )
    render(
        {
            "conversation_id": execution.conversation_id,
            "request_id": execution.request_id,
            **status.model_dump(mode="json"),
        }
    )


@group.command(name="agent-status")
@click.argument("agent_id")
@click.argument("request_id")
@_wait_options
@click.pass_obj
def agent_status(
    ctx: ClientContext,
    agent_id: str,
    request_id: str,
    wait: bool,
    interval: float,
    timeout: float,
) -> None:
    """
    Show an agent question's status, and its answer once done.
    """
    if wait:
        render(
            ctx.client.wait_for_agent(
                agent_id, request_id, interval=interval, timeout=timeout
            )
        )
        return
    render(ctx.client.get_agent_execution(agent_id, request_id))


@group.command(name="search")
@click.argument("query")
@click.option(
    "--semantic-weight",
    type=click.FloatRange(0.0, 1.0),
    default=0.5,
    show_default=True,
    help="0.0 matches keywords only, 1.0 meaning only.",
)
@click.option(
    "--folder",
    "folders",
    multiple=True,
    help="Search only this folder (repeatable).",
)
@click.option(
    "--exclude-folder",
    "exclude_folders",
    multiple=True,
    help="Leave out this folder (repeatable).",
)
@click.option(
    "--prefer-folder", default=None, help="Rank this folder's results higher."
)
@click.option(
    "--entry-id",
    "entry_ids",
    multiple=True,
    help="Search only this file version (repeatable).",
)
@click.option("--collection-id", default=None, help="Search only this collection.")
@click.option("--created-by", default=None, help="Only files created by this username.")
@click.option(
    "--created-after",
    type=click.DateTime(),
    default=None,
    help="Created after (YYYY-MM-DD or ISO 8601, UTC).",
)
@click.option(
    "--created-before",
    type=click.DateTime(),
    default=None,
    help="Created before (YYYY-MM-DD or ISO 8601, UTC).",
)
@click.option(
    "--limit", type=click.IntRange(1, 1000), default=None, help="Most files to return."
)
@click.pass_obj
def search(
    ctx: ClientContext,
    query: str,
    semantic_weight: float,
    folders: tuple[str, ...],
    exclude_folders: tuple[str, ...],
    prefer_folder: str | None,
    entry_ids: tuple[str, ...],
    collection_id: str | None,
    created_by: str | None,
    created_after: datetime | None,
    created_before: datetime | None,
    limit: int | None,
) -> None:
    """
    Search file content by keyword and meaning, printing matching passages.
    """
    render(
        ctx.client.hybrid_search(
            query,
            semantic_weight=semantic_weight,
            folders=list(folders) or None,
            exclude_folders=list(exclude_folders) or None,
            preferred_folder=prefer_folder,
            entry_ids=list(entry_ids) or None,
            collection_id=collection_id,
            created_by=created_by,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
        )
    )
