"""
Coverage of the AI, AI Assistant, agent, and hybrid search methods.

Fixture bodies follow the examples in Egnyte's AI and Agents API docs; the
endpoints have not been exercised live.
"""

import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from conftest import API, body, respond

from egnyte_client import EgnyteForbiddenError, EgnyteTimeoutError
from egnyte_client.async_client import AsyncEgnyteClient
from egnyte_client.client import EgnyteClient
from egnyte_client.schemas.ai import ChatMessage

ANSWER: dict[str, Any] = {
    "response": {"text": "Christmas Day in 2025 falls on a Thursday."},
    "citations": [
        {
            "filename": "Policy.pdf",
            "entryId": "e-1",
            "chunks": [{"chunkId": "0", "sourceText": "Policy Renewal"}],
        }
    ],
}

ASSISTANT_EXECUTION: dict[str, Any] = {
    "conversationId": "c-1",
    "executionId": "x-1",
    "executionStatus": "IN_PROGRESS",
    "truncated": False,
    "actions": [],
}

ASSISTANT_DONE: dict[str, Any] = {
    "status": "COMPLETED",
    "responseText": "The document shows several premium examples",
    "thoughts": [],
    "citations": [
        {
            "filename": "Policy.pdf",
            "entryId": "e-1",
            "objectId": "52.1e0b",
            "previewUrl": "/navigate/file/3bf2",
            "chunks": [{"chunkId": "c5", "sourceText": "Text"}],
        }
    ],
    "intent": "qna",
    "lastUpdated": 1780660757000,
    "numToolCalls": 1,
    "pendingActions": [],
    "toolCalls": {
        "call_abc123": {
            "name": "search_documents",
            "sourceDisplayName": "Egnyte",
            "toolDisplayName": "Document Search",
            "thought": "Searching for relevant documents",
            "input": {"query": "premium examples"},
            "output": "Found 3 relevant documents",
            "status": "success",
            "timestamp": "2025-06-05T10:00:00Z",
        }
    },
}

AGENT: dict[str, Any] = {
    "agentId": "a-1",
    "name": "llm agent",
    "description": "llm details",
    "status": "ACTIVE",
    "subType": "USER_DEFINED",
    "category": "GENERIC",
    "instruction": "llm details",
    "createdBy": "John Millar",
}

AGENT_EXECUTION: dict[str, Any] = {"requestId": "r-1", "conversationId": "c-2"}

AGENT_DONE: dict[str, Any] = {
    "status": "COMPLETED",
    "responseText": "LLMs are deep learning models.",
    "citations": [
        {"previewUrl": "https://en.wikipedia.org/wiki/LLM", "type": "WEB_SEARCH"}
    ],
    "lastUpdated": "2025-09-18T10:24:59Z",
}

HYBRID: dict[str, Any] = {
    "results": [
        {
            "filename": "Financial_Report_2023.pdf",
            "entryId": "e-2",
            "objectId": "obj123456",
            "chunks": [
                {
                    "chunkId": "chunk-123",
                    "chunkText": "Revenue rose 15%.",
                    "type": "TEXT",
                    "score": 0.92,
                }
            ],
        }
    ]
}


def _client(
    make_client: Callable[..., EgnyteClient], *responses: httpx.Response
) -> tuple[EgnyteClient, list[httpx.Request]]:
    sent: list[httpx.Request] = []
    queue: Iterator[httpx.Response] = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return next(queue)

    return make_client(handler), sent


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]) -> None:
    """
    Make `time.monotonic` advance only by the waits the clients ask for.
    """
    monkeypatch.setattr(time, "monotonic", lambda: sum(no_sleep))


# =============================================================================
# TESTS: Document Q&A and summaries
# =============================================================================


def test_ask_document(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(ANSWER))

    answer = client.ask_document(
        "e/1",
        "When is Christmas?",
        include_citations=True,
        chat_history=[ChatMessage(role="user", content="Hi")],
    )

    assert sent[0].method == "POST"
    assert sent[0].url.raw_path == b"/pubapi/v1/ai/document/e%2F1/ask"
    assert body(sent[0]) == {
        "question": "When is Christmas?",
        "includeCitations": True,
        "chatHistory": {"messages": [{"role": "user", "content": "Hi"}]},
    }
    assert answer.text.startswith("Christmas Day")
    assert answer.citations[0].entry_id == "e-1"
    assert answer.citations[0].chunks[0].source_text == "Policy Renewal"


def test_ask_document_sends_only_the_question_by_default(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond({"response": {"text": "Yes"}}))

    answer = client.ask_document("e-1", "Is it signed?")

    assert body(sent[0]) == {"question": "Is it signed?"}
    assert answer.citations == []


def test_summarize_document(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond({"response": {"text": "A summary"}}))

    summary = client.summarize_document("e-1")

    assert sent[0].url.path == "/pubapi/v1/ai/document/e-1/summary"
    assert body(sent[0]) == {}
    assert summary.text == "A summary"


# =============================================================================
# TESTS: AI Assistant
# =============================================================================


def test_ask_assistant_builds_the_selection(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(ASSISTANT_EXECUTION))

    execution = client.ask_assistant(
        "Describe the file",
        folder_ids=["f-1"],
        entry_ids=["e-1"],
        web_search=True,
        include_citations=True,
        conversation_id="c-0",
        mcp_selection_id="m-1",
        model_version="gemini-2.5-flash",
    )

    assert sent[0].url.path == "/pubapi/v1/ai/assistant/ask"
    assert body(sent[0]) == {
        "question": "Describe the file",
        "selectedItems": {
            "folders": [{"id": "f-1"}],
            "files": [{"entryId": "e-1"}],
            "webSearch": True,
        },
        "includeCitations": True,
        "conversationId": "c-0",
        "mcpSelectionId": "m-1",
        "modelDetails": {"version": "gemini-2.5-flash"},
    }
    assert execution.execution_id == "x-1"
    assert execution.conversation_id == "c-1"
    assert execution.execution_status == "IN_PROGRESS"


def test_ask_assistant_search_all_alone(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(ASSISTANT_EXECUTION))

    client.ask_assistant("Where is the budget?", search_all=True)

    assert body(sent[0]) == {
        "question": "Where is the budget?",
        "selectedItems": {"allEgnyteSearch": True},
    }


def test_get_assistant_execution(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(ASSISTANT_DONE))

    status = client.get_assistant_execution("x-1", include_citations=False)

    assert sent[0].url.path == "/pubapi/v1/ai/assistant/x-1/status"
    assert sent[0].url.params["includeCitations"] == "false"
    assert status.status == "COMPLETED"
    assert status.response_text is not None
    assert status.citations[0].preview_url == "/navigate/file/3bf2"
    assert status.last_updated == datetime(2026, 6, 5, 11, 59, 17, tzinfo=UTC)
    call = status.tool_calls["call_abc123"]
    assert call.tool_display_name == "Document Search"
    assert call.input == {"query": "premium examples"}


def test_wait_for_assistant_polls_until_done(
    make_client: Callable[..., EgnyteClient], no_sleep: list[float], clock: None
) -> None:
    running = respond({"status": "IN_PROGRESS"})
    client, sent = _client(make_client, running, running, respond(ASSISTANT_DONE))

    status = client.wait_for_assistant("x-1", interval=7)

    assert status.status == "COMPLETED"
    assert len(sent) == 3
    assert no_sleep == [7, 7]


def test_wait_for_assistant_returns_a_status_needing_the_user(
    make_client: Callable[..., EgnyteClient], clock: None
) -> None:
    pending = {
        "status": "AWAITING_USER_CONFIRMATION",
        "pendingActions": [
            {"type": "MCP_AUTH", "serverId": "s-1", "toolCallId": "call_1"}
        ],
    }
    client, _ = _client(make_client, respond(pending))

    status = client.wait_for_assistant("x-1")

    assert status.pending_actions[0].server_id == "s-1"


def test_wait_for_assistant_times_out(
    make_client: Callable[..., EgnyteClient], no_sleep: list[float], clock: None
) -> None:
    running = respond({"status": "IN_PROGRESS"})
    client, sent = _client(make_client, *[running] * 5)

    with pytest.raises(EgnyteTimeoutError, match="x-1 still IN_PROGRESS after 30s"):
        client.wait_for_assistant("x-1", interval=10, timeout=30)

    assert len(sent) == 4
    assert no_sleep == [10, 10, 10]


def test_timeout_error_is_a_timeout_error() -> None:
    assert issubclass(EgnyteTimeoutError, TimeoutError)


# =============================================================================
# TESTS: Agents
# =============================================================================


def test_list_agents(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond([AGENT]))

    agents = client.list_agents(sort_by="createdOn", sort_order="desc")

    assert sent[0].url.path == "/pubapi/v1/ai/agents/list"
    assert dict(sent[0].url.params) == {"sortBy": "createdOn", "sortOrder": "desc"}
    assert agents[0].agent_id == "a-1"
    assert agents[0].sub_type == "USER_DEFINED"
    assert agents[0].created_by == "John Millar"


def test_agents_not_enabled_keeps_the_error_code(
    make_client: Callable[..., EgnyteClient],
) -> None:
    refused = respond(
        {
            "errorMessage": "The Agents feature is not enabled for this domain",
            "errorCode": "AGENTS_FEATURE_NOT_ENABLED",
        },
        status=403,
    )
    client, _ = _client(make_client, refused)

    with pytest.raises(EgnyteForbiddenError) as raised:
        client.list_agents()

    assert raised.value.code == "AGENTS_FEATURE_NOT_ENABLED"
    assert "not enabled" in raised.value.message


def test_ask_agent(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(AGENT_EXECUTION))

    execution = client.ask_agent(
        "a-1",
        "What are the key findings?",
        instructions="Be brief",
        entry_ids=["e-1"],
        folder_ids=["f-1"],
        chat_history=[
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi"),
        ],
        conversation_id="c-2",
    )

    assert sent[0].url.path == "/pubapi/v1/ai/agents/a-1/ask"
    assert body(sent[0]) == {
        "question": "What are the key findings?",
        "instructions": "Be brief",
        "conversationId": "c-2",
        "chatHistory": {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
            ]
        },
        "entryIds": ["e-1"],
        "selectedItems": {"folders": [{"id": "f-1"}]},
    }
    assert execution.request_id == "r-1"


def test_get_agent_execution(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(AGENT_DONE))

    status = client.get_agent_execution("a-1", "r-1")

    assert sent[0].url.path == "/pubapi/v1/ai/agents/a-1/ask/r-1/status"
    assert status.response_text == "LLMs are deep learning models."
    assert status.citations[0].type == "WEB_SEARCH"
    assert status.last_updated == datetime(2025, 9, 18, 10, 24, 59, tzinfo=UTC)


def test_wait_for_agent(
    make_client: Callable[..., EgnyteClient], no_sleep: list[float], clock: None
) -> None:
    client, sent = _client(
        make_client,
        respond({"status": "PENDING"}),
        respond({"status": "RUNNING"}),
        respond({"status": "FAILED"}),
    )

    status = client.wait_for_agent("a-1", "r-1")

    assert status.status == "FAILED"
    assert len(sent) == 3
    assert no_sleep == [10.0, 10.0]


def test_wait_for_agent_times_out(
    make_client: Callable[..., EgnyteClient], clock: None
) -> None:
    client, sent = _client(make_client, *[respond({"status": "RUNNING"})] * 20)

    with pytest.raises(EgnyteTimeoutError, match="r-1 still RUNNING after 180s"):
        client.wait_for_agent("a-1", "r-1")

    assert len(sent) == 19


# =============================================================================
# TESTS: Hybrid search
# =============================================================================


def test_hybrid_search(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(HYBRID))

    results = client.hybrid_search(
        "quarterly report",
        semantic_weight=0.25,
        folder="Shared/Finance/",
        folders=["/Shared/A"],
        exclude_folders=["/Shared/A/Old"],
        preferred_folder="/Shared/Finance/2023",
        entry_ids=["e-2"],
        collection_id="k-1",
        created_by="jdoe",
        created_after=datetime(2021, 1, 1, tzinfo=UTC),
        created_before=datetime(2022, 1, 1),
        limit=50,
    )

    assert sent[0].url.path == "/pubapi/v1/hybrid-search"
    assert body(sent[0]) == {
        "query": "quarterly report",
        "semanticWeight": 0.25,
        "folderPath": "/Shared/Finance",
        "folderPaths": ["/Shared/A"],
        "excludeFolderPaths": ["/Shared/A/Old"],
        "preferredFolderPath": "/Shared/Finance/2023",
        "collectionId": "k-1",
        "entryIds": ["e-2"],
        "createdBy": "jdoe",
        "createdAfter": 1609459200000,
        "createdBefore": 1640995200000,
        "limit": 50,
    }
    assert results[0].filename == "Financial_Report_2023.pdf"
    assert results[0].chunks[0].chunk_text == "Revenue rose 15%."
    assert results[0].chunks[0].score == 0.92


def test_hybrid_search_defaults_to_an_even_weight(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond({"results": []}))

    assert client.hybrid_search("budget") == []
    assert body(sent[0]) == {"query": "budget", "semanticWeight": 0.5}


@pytest.mark.parametrize("weight", [-0.1, 1.5])
def test_hybrid_search_refuses_a_weight_out_of_range(
    make_client: Callable[..., EgnyteClient], weight: float
) -> None:
    client, sent = _client(make_client)

    with pytest.raises(ValueError, match="semantic_weight"):
        client.hybrid_search("budget", semantic_weight=weight)

    assert sent == []


# =============================================================================
# TESTS: Async client
# =============================================================================


async def test_async_ask_document(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == f"{API}/v1/ai/document/e-1/ask"
        return respond(ANSWER)

    client = make_async_client(handler)

    answer = await client.ask_document("e-1", "When is Christmas?")

    assert answer.citations[0].filename == "Policy.pdf"


async def test_async_wait_for_assistant(
    make_async_client: Callable[..., AsyncEgnyteClient],
    no_sleep: list[float],
    clock: None,
) -> None:
    responses = iter([respond({"status": "IN_PROGRESS"}), respond(ASSISTANT_DONE)])
    client = make_async_client(lambda request: next(responses))

    status = await client.wait_for_assistant("x-1")

    assert status.status == "COMPLETED"
    assert no_sleep == [10.0]


async def test_async_wait_for_agent_times_out(
    make_async_client: Callable[..., AsyncEgnyteClient], clock: None
) -> None:
    client = make_async_client(lambda request: respond({"status": "PENDING"}))

    with pytest.raises(EgnyteTimeoutError):
        await client.wait_for_agent("a-1", "r-1", interval=5, timeout=10)
