from datetime import datetime

from pydantic import TypeAdapter

from egnyte_client.operations.generic import (
    Operation,
    encode_id,
    epoch_ms,
    model,
    normalize_path,
    query,
)
from egnyte_client.schemas.ai import (
    Agent,
    AgentExecution,
    AgentExecutionStatus,
    AgentQuestionRequest,
    AgentSortBy,
    AgentSortOrder,
    AiAnswer,
    AssistantExecution,
    AssistantExecutionStatus,
    AssistantQuestionRequest,
    ChatHistory,
    ChatMessage,
    DocumentQuestionRequest,
    DocumentSummaryRequest,
    FileSelection,
    FolderSelection,
    HybridSearchRequest,
    HybridSearchResult,
    HybridSearchResults,
    ModelDetails,
    SelectedItems,
)

AI = "/v1/ai"

# Waiting on a background answer polls every 10 seconds for up to 3 minutes:
# under the 10-a-minute AI limit, and at most 19 of the 100 daily AI calls.
DEFAULT_AI_POLL_INTERVAL = 10.0
DEFAULT_AI_WAIT_TIMEOUT = 180.0

_AGENT_LIST = TypeAdapter(list[Agent])


def _history(messages: list[ChatMessage] | None) -> ChatHistory | None:
    return ChatHistory(messages=messages) if messages else None


def _agent(agent_id: str) -> str:
    return f"{AI}/agents/{encode_id(agent_id)}"


# -----------------------------------------------------------------------------
# OPERATION: ask_document
# -----------------------------------------------------------------------------


def ask_document(
    entry_id: str,
    question: str,
    *,
    include_citations: bool | None = None,
    chat_history: list[ChatMessage] | None = None,
) -> Operation[AiAnswer]:
    """
    Build a question about one file version.

    Returns:
        Operation[AiAnswer]: The ask document operation.
    """
    return Operation(
        method="POST",
        path=f"{AI}/document/{encode_id(entry_id)}/ask",
        body=DocumentQuestionRequest(
            question=question,
            include_citations=include_citations,
            chat_history=_history(chat_history),
        ),
        parse=model(AiAnswer),
    )


# -----------------------------------------------------------------------------
# OPERATION: summarize_document
# -----------------------------------------------------------------------------


def summarize_document(
    entry_id: str, *, chat_history: list[ChatMessage] | None = None
) -> Operation[AiAnswer]:
    """
    Build a summary of one file version.

    Returns:
        Operation[AiAnswer]: The summarize document operation.
    """
    return Operation(
        method="POST",
        path=f"{AI}/document/{encode_id(entry_id)}/summary",
        body=DocumentSummaryRequest(chat_history=_history(chat_history)),
        parse=model(AiAnswer),
    )


# -----------------------------------------------------------------------------
# OPERATION: ask_assistant
# -----------------------------------------------------------------------------


def ask_assistant(
    question: str,
    *,
    folder_ids: list[str] | None = None,
    entry_ids: list[str] | None = None,
    search_all: bool | None = None,
    web_search: bool | None = None,
    include_citations: bool | None = None,
    chat_history: list[ChatMessage] | None = None,
    conversation_id: str | None = None,
    mcp_selection_id: str | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
) -> Operation[AssistantExecution]:
    """
    Build an AI Assistant question, answered in the background.

    Returns:
        Operation[AssistantExecution]: The ask assistant operation.
    """
    selected = None
    if folder_ids or entry_ids or search_all is not None or web_search is not None:
        selected = SelectedItems(
            folders=[FolderSelection(id=i) for i in folder_ids] if folder_ids else None,
            files=[FileSelection(entry_id=i) for i in entry_ids] if entry_ids else None,
            all_egnyte_search=search_all,
            web_search=web_search,
        )
    details = None
    if model_name is not None or model_version is not None:
        details = ModelDetails(name=model_name, version=model_version)

    return Operation(
        method="POST",
        path=f"{AI}/assistant/ask",
        body=AssistantQuestionRequest(
            question=question,
            selected_items=selected,
            include_citations=include_citations,
            chat_history=_history(chat_history),
            conversation_id=conversation_id,
            mcp_selection_id=mcp_selection_id,
            model_details=details,
        ),
        parse=model(AssistantExecution),
    )


# -----------------------------------------------------------------------------
# OPERATION: get_assistant_execution
# -----------------------------------------------------------------------------


def get_assistant_execution(
    execution_id: str, *, include_citations: bool | None = None
) -> Operation[AssistantExecutionStatus]:
    """
    Build the AI Assistant status read for one question.

    Returns:
        Operation[AssistantExecutionStatus]: The status operation.
    """
    return Operation(
        method="GET",
        path=f"{AI}/assistant/{encode_id(execution_id)}/status",
        params=query(includeCitations=include_citations),
        parse=model(AssistantExecutionStatus),
    )


# -----------------------------------------------------------------------------
# OPERATION: list_agents
# -----------------------------------------------------------------------------


def list_agents(
    *, sort_by: AgentSortBy | None = None, sort_order: AgentSortOrder | None = None
) -> Operation[list[Agent]]:
    """
    Build the agent listing.

    Returns:
        Operation[list[Agent]]: The list agents operation.
    """
    return Operation(
        method="GET",
        path=f"{AI}/agents/list",
        params=query(sortBy=sort_by, sortOrder=sort_order),
        parse=lambda response: _AGENT_LIST.validate_json(response.content),
    )


# -----------------------------------------------------------------------------
# OPERATION: ask_agent
# -----------------------------------------------------------------------------


def ask_agent(
    agent_id: str,
    question: str,
    *,
    instructions: str | None = None,
    entry_ids: list[str] | None = None,
    folder_ids: list[str] | None = None,
    chat_history: list[ChatMessage] | None = None,
    conversation_id: str | None = None,
) -> Operation[AgentExecution]:
    """
    Build a question to an agent, answered in the background.

    Returns:
        Operation[AgentExecution]: The ask agent operation.
    """
    selected = None
    if folder_ids:
        selected = SelectedItems(folders=[FolderSelection(id=i) for i in folder_ids])

    return Operation(
        method="POST",
        path=f"{_agent(agent_id)}/ask",
        body=AgentQuestionRequest(
            question=question,
            instructions=instructions,
            conversation_id=conversation_id,
            chat_history=_history(chat_history),
            entry_ids=entry_ids or None,
            selected_items=selected,
        ),
        parse=model(AgentExecution),
    )


# -----------------------------------------------------------------------------
# OPERATION: get_agent_execution
# -----------------------------------------------------------------------------


def get_agent_execution(
    agent_id: str, request_id: str
) -> Operation[AgentExecutionStatus]:
    """
    Build the agent status read for one question.

    Returns:
        Operation[AgentExecutionStatus]: The status operation.
    """
    return Operation(
        method="GET",
        path=f"{_agent(agent_id)}/ask/{encode_id(request_id)}/status",
        parse=model(AgentExecutionStatus),
    )


# -----------------------------------------------------------------------------
# OPERATION: hybrid_search
# -----------------------------------------------------------------------------


def hybrid_search(
    query: str,
    *,
    semantic_weight: float = 0.5,
    folder: str | None = None,
    folders: list[str] | None = None,
    exclude_folders: list[str] | None = None,
    preferred_folder: str | None = None,
    collection_id: str | None = None,
    entry_ids: list[str] | None = None,
    created_by: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    limit: int | None = None,
) -> Operation[list[HybridSearchResult]]:
    """
    Build a hybrid keyword and semantic search.

    Returns:
        Operation[list[HybridSearchResult]]: The hybrid search operation.
    """
    if not 0.0 <= semantic_weight <= 1.0:
        raise ValueError("semantic_weight must be between 0.0 and 1.0")

    return Operation(
        method="POST",
        path="/v1/hybrid-search",
        body=HybridSearchRequest(
            query=query,
            semantic_weight=semantic_weight,
            folder_path=normalize_path(folder) if folder else None,
            folder_paths=[normalize_path(f) for f in folders] if folders else None,
            exclude_folder_paths=(
                [normalize_path(f) for f in exclude_folders]
                if exclude_folders
                else None
            ),
            preferred_folder_path=(
                normalize_path(preferred_folder) if preferred_folder else None
            ),
            collection_id=collection_id,
            entry_ids=entry_ids or None,
            created_by=created_by,
            created_after=epoch_ms(created_after),
            created_before=epoch_ms(created_before),
            limit=limit,
        ),
        parse=lambda response: (
            HybridSearchResults.model_validate_json(response.content).results
        ),
    )
