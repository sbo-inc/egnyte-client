from datetime import datetime
from typing import Literal

from pydantic import AliasPath, Field, JsonValue

from egnyte_client.schemas.generic import GenericBaseModel

type ChatRole = Literal["user", "assistant"]
type AgentSortBy = Literal["name", "createdOn"]
type AgentSortOrder = Literal["asc", "desc"]

# Execution states. Responses are typed as plain strings so a state Egnyte adds
# later still parses. Agents are documented as `PENDING` or `RUNNING` while
# they work, but answer `IN_PROGRESS` live, so all three count as running.
ASSISTANT_RUNNING_STATUSES = frozenset({"IN_PROGRESS"})
AGENT_RUNNING_STATUSES = frozenset({"IN_PROGRESS", "PENDING", "RUNNING"})

# =============================================================================
# CLASS: ChatMessage
# =============================================================================


class ChatMessage(GenericBaseModel):
    """
    One earlier turn of a conversation, passed as `chat_history`.
    """

    role: ChatRole = Field(
        description="Who said it: `user` or `assistant`.",
    )
    content: str = Field(
        description="What was said.",
    )


# =============================================================================
# CLASS: AiCitationChunk
# =============================================================================


class AiCitationChunk(GenericBaseModel):
    """
    A passage of a cited file that an answer drew on.
    """

    chunk_id: str | None = Field(
        default=None,
        alias="chunkId",
        description="ID of the passage.",
    )
    source_text: str | None = Field(
        default=None,
        alias="sourceText",
        description="The passage text.",
    )


# =============================================================================
# CLASS: AiCitation
# =============================================================================


class AiCitation(GenericBaseModel):
    """
    A source an AI answer cites: an Egnyte file, or a web page for agents.
    """

    filename: str | None = Field(
        default=None,
        description="Name of the cited file.",
    )
    entry_id: str | None = Field(
        default=None,
        alias="entryId",
        description="Version ID of the cited file.",
    )
    group_id: str | None = Field(
        default=None,
        alias="groupId",
        description="File ID across versions.",
    )
    object_id: str | None = Field(
        default=None,
        alias="objectId",
        description="Object ID of the cited file.",
    )
    file_path: str | None = Field(
        default=None,
        alias="filePath",
        description="Path of the cited file.",
    )
    preview_url: str | None = Field(
        default=None,
        alias="previewUrl",
        description="Where to view the source: a web UI path or a web URL.",
    )
    type: str | None = Field(
        default=None,
        description="Kind of source, such as `FILE` or `WEB_SEARCH`.",
    )
    chunks: list[AiCitationChunk] = Field(
        default_factory=list,
        description="The passages the answer drew on.",
    )


# =============================================================================
# CLASS: AiAnswer
# =============================================================================


class AiAnswer(GenericBaseModel):
    """
    An answer about, or summary of, one document.
    """

    text: str = Field(
        default="",
        validation_alias=AliasPath("response", "text"),
        description="The answer or summary.",
    )
    citations: list[AiCitation] = Field(
        default_factory=list,
        description="Where the answer came from, when citations were requested.",
    )


# =============================================================================
# CLASS: AssistantExecution
# =============================================================================


class AssistantExecution(GenericBaseModel):
    """
    A question accepted by the AI Assistant, still being answered.
    """

    execution_id: str = Field(
        alias="executionId",
        description="Poll this with `get_assistant_execution` for the answer.",
    )
    conversation_id: str | None = Field(
        default=None,
        alias="conversationId",
        description="Pass to a follow-up question to continue the conversation.",
    )
    execution_status: str | None = Field(
        default=None,
        alias="executionStatus",
        description="State at submission, normally `IN_PROGRESS`.",
    )
    truncated: bool = Field(
        default=False,
        description="Whether the response was truncated.",
    )
    actions: list[JsonValue] = Field(
        default_factory=list,
        description="Actions returned at submission, if any.",
    )


# =============================================================================
# CLASS: AssistantPendingAction
# =============================================================================


class AssistantPendingAction(GenericBaseModel):
    """
    Something the AI Assistant needs from the user before it can go on.
    """

    type: str | None = Field(
        default=None,
        description="What is needed, such as `MCP_AUTH`.",
    )
    server_id: str | None = Field(
        default=None,
        alias="serverId",
        description="The server that needs it.",
    )
    tool_call_id: str | None = Field(
        default=None,
        alias="toolCallId",
        description="The tool call that asked for it.",
    )


# =============================================================================
# CLASS: AssistantToolCall
# =============================================================================


class AssistantToolCall(GenericBaseModel):
    """
    One tool the AI Assistant used while answering.
    """

    id: str | None = Field(
        default=None,
        description="Tool call ID, the key it is listed under.",
    )
    name: str | None = Field(
        default=None,
        description="Internal tool name.",
    )
    source_display_name: str | None = Field(
        default=None,
        alias="sourceDisplayName",
        description="The data source the tool worked on.",
    )
    tool_display_name: str | None = Field(
        default=None,
        alias="toolDisplayName",
        description="Readable tool name.",
    )
    thought: str | None = Field(
        default=None,
        description="The model's reasoning before calling the tool.",
    )
    thoughts: list[JsonValue] = Field(
        default_factory=list,
        description="The model's reasoning steps for this call.",
    )
    input: JsonValue = Field(
        default=None,
        description="What the tool was given.",
    )
    output: JsonValue = Field(
        default=None,
        description="What the tool returned.",
    )
    status: str | None = Field(
        default=None,
        description="How the call went.",
    )
    timestamp: datetime | None = Field(
        default=None,
        description="When the tool was called (sent as epoch seconds).",
    )
    metadata: dict[str, JsonValue] | None = Field(
        default=None,
        description="Extra details about the call.",
    )


# =============================================================================
# CLASS: AssistantExecutionStatus
# =============================================================================


class AssistantExecutionStatus(GenericBaseModel):
    """
    Where an AI Assistant question stands, and its answer once done.

    `status` is `IN_PROGRESS` while it works, then `COMPLETED`, `FAILED`, or
    `AWAITING_USER_CONFIRMATION` (see `pending_actions`).
    """

    status: str = Field(
        description="`IN_PROGRESS`, `COMPLETED`, `FAILED`, or `AWAITING_USER_CONFIRMATION`.",
    )
    response_text: str | None = Field(
        default=None,
        alias="responseText",
        description="The answer, once `COMPLETED`.",
    )
    thoughts: list[JsonValue] = Field(
        default_factory=list,
        description="The model's reasoning steps.",
    )
    citations: list[AiCitation] = Field(
        default_factory=list,
        description="Where the answer came from.",
    )
    actions: list[JsonValue] = Field(
        default_factory=list,
        description="Actions returned by the execution.",
    )
    intent: str | None = Field(
        default=None,
        description="How the question was read, such as `qna`.",
    )
    last_updated: datetime | None = Field(
        default=None,
        alias="lastUpdated",
        description="When the status last changed.",
    )
    num_tool_calls: int | None = Field(
        default=None,
        alias="numToolCalls",
        description="How many tools were called.",
    )
    pending_actions: list[AssistantPendingAction] = Field(
        default_factory=list,
        alias="pendingActions",
        description="What the user must do before it can go on.",
    )
    tool_calls: dict[str, AssistantToolCall] = Field(
        default_factory=dict,
        alias="toolCalls",
        description="The tools called, by tool call ID.",
    )


# =============================================================================
# CLASS: Agent
# =============================================================================


class Agent(GenericBaseModel):
    """
    A configured Egnyte AI agent.
    """

    agent_id: str = Field(
        alias="agentId",
        description="Agent ID.",
    )
    name: str | None = Field(
        default=None,
        description="Agent name.",
    )
    description: str | None = Field(
        default=None,
        description="What the agent does.",
    )
    status: str | None = Field(
        default=None,
        description="`DRAFT` or `ACTIVE`.",
    )
    sub_type: str | None = Field(
        default=None,
        alias="subType",
        description="Kind of agent, such as `USER_DEFINED` or `TRANSLATION_AGENT`.",
    )
    category: str | None = Field(
        default=None,
        description="`TASK`, `QUESTION`, or `GENERIC`.",
    )
    instruction: str | None = Field(
        default=None,
        description="The agent's core instructions.",
    )
    created_by: str | None = Field(
        default=None,
        alias="createdBy",
        description="Name of the user who created the agent.",
    )


# =============================================================================
# CLASS: AgentExecution
# =============================================================================


class AgentExecution(GenericBaseModel):
    """
    A question accepted by an agent, still being answered.
    """

    request_id: str = Field(
        alias="requestId",
        description="Poll this with `get_agent_execution` for the answer.",
    )
    conversation_id: str | None = Field(
        default=None,
        alias="conversationId",
        description="Pass to a follow-up question to continue the conversation.",
    )


# =============================================================================
# CLASS: AgentExecutionStatus
# =============================================================================


class AgentExecutionStatus(GenericBaseModel):
    """
    Where an agent question stands, and its answer once done.

    `status` is `IN_PROGRESS` while it works (`PENDING` or `RUNNING` in
    Egnyte's documentation), then `COMPLETED` or `FAILED`. A failure carries
    no detail.
    """

    status: str = Field(
        description="`IN_PROGRESS`, `PENDING`, `RUNNING`, `COMPLETED`, or `FAILED`.",
    )
    response_text: str | None = Field(
        default=None,
        alias="responseText",
        description="The answer, once `COMPLETED`.",
    )
    citations: list[AiCitation] = Field(
        default_factory=list,
        description="Where the answer came from, once `COMPLETED`.",
    )
    last_updated: datetime | None = Field(
        default=None,
        alias="lastUpdated",
        description="When the status last changed.",
    )


# =============================================================================
# CLASS: HybridSearchChunk
# =============================================================================


class HybridSearchChunk(GenericBaseModel):
    """
    A passage of a file that matched a hybrid search.
    """

    chunk_id: str | None = Field(
        default=None,
        alias="chunkId",
        description="ID of the passage.",
    )
    chunk_text: str | None = Field(
        default=None,
        alias="chunkText",
        description="The passage text.",
    )
    type: str | None = Field(
        default=None,
        description="`TEXT` or `TABLE`.",
    )
    score: float | None = Field(
        default=None,
        description="Relevance; higher is better. Not bounded to 0-1.",
    )


# =============================================================================
# CLASS: HybridSearchResult
# =============================================================================


class HybridSearchResult(GenericBaseModel):
    """
    One file matched by a hybrid search, with its matching passages.
    """

    filename: str | None = Field(
        default=None,
        description="Path of the file (Egnyte's field name says name).",
    )
    entry_id: str | None = Field(
        default=None,
        alias="entryId",
        description="Version ID of the file.",
    )
    group_id: str | None = Field(
        default=None,
        alias="groupId",
        description="File ID across versions.",
    )
    object_id: str | None = Field(
        default=None,
        alias="objectId",
        description="Object ID of the file.",
    )
    uploaded: datetime | None = Field(
        default=None,
        alias="uploadedTimestamp",
        description="When this version was uploaded.",
    )
    chunks: list[HybridSearchChunk] = Field(
        default_factory=list,
        description="The passages that matched.",
    )


class HybridSearchResults(GenericBaseModel):
    """
    The hybrid search response envelope.
    """

    results: list[HybridSearchResult] = Field(default_factory=list)


# =============================================================================
# CLASSES: Request bodies
# =============================================================================


class ChatHistory(GenericBaseModel):
    messages: list[ChatMessage]


class FolderSelection(GenericBaseModel):
    id: str


class FileSelection(GenericBaseModel):
    entry_id: str = Field(alias="entryId")


class SelectedItems(GenericBaseModel):
    folders: list[FolderSelection] | None = None
    files: list[FileSelection] | None = None
    all_egnyte_search: bool | None = Field(default=None, alias="allEgnyteSearch")
    web_search: bool | None = Field(default=None, alias="webSearch")


class ModelDetails(GenericBaseModel):
    name: str | None = None
    version: str | None = None


class DocumentQuestionRequest(GenericBaseModel):
    question: str
    include_citations: bool | None = Field(default=None, alias="includeCitations")
    chat_history: ChatHistory | None = Field(default=None, alias="chatHistory")


class DocumentSummaryRequest(GenericBaseModel):
    chat_history: ChatHistory | None = Field(default=None, alias="chatHistory")


class AssistantQuestionRequest(GenericBaseModel):
    question: str
    selected_items: SelectedItems | None = Field(default=None, alias="selectedItems")
    include_citations: bool | None = Field(default=None, alias="includeCitations")
    chat_history: ChatHistory | None = Field(default=None, alias="chatHistory")
    conversation_id: str | None = Field(default=None, alias="conversationId")
    mcp_selection_id: str | None = Field(default=None, alias="mcpSelectionId")
    model_details: ModelDetails | None = Field(default=None, alias="modelDetails")


class AgentQuestionRequest(GenericBaseModel):
    question: str
    instructions: str | None = None
    conversation_id: str | None = Field(default=None, alias="conversationId")
    chat_history: ChatHistory | None = Field(default=None, alias="chatHistory")
    entry_ids: list[str] | None = Field(default=None, alias="entryIds")
    selected_items: SelectedItems | None = Field(default=None, alias="selectedItems")


class HybridSearchRequest(GenericBaseModel):
    query: str
    semantic_weight: float = Field(alias="semanticWeight")
    folder_path: str | None = Field(default=None, alias="folderPath")
    folder_paths: list[str] | None = Field(default=None, alias="folderPaths")
    exclude_folder_paths: list[str] | None = Field(
        default=None, alias="excludeFolderPaths"
    )
    preferred_folder_path: str | None = Field(default=None, alias="preferredFolderPath")
    collection_id: str | None = Field(default=None, alias="collectionId")
    entry_ids: list[str] | None = Field(default=None, alias="entryIds")
    created_by: str | None = Field(default=None, alias="createdBy")
    created_after: int | None = Field(default=None, alias="createdAfter")
    created_before: int | None = Field(default=None, alias="createdBefore")
    limit: int | None = None
