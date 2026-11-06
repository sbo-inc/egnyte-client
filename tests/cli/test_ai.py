"""
Coverage of the `ai` commands against a mock-transport client.
"""

import json
import time
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from click.testing import Result
from conftest import body, respond

Runner = Callable[..., tuple[Result, list[httpx.Request]]]


@pytest.fixture
def run(cli_runner: Callable[..., Runner]) -> Callable[..., Runner]:
    """
    Return a factory for a runner invoking `egnyte-client ai`.

    Returns:
        Callable[..., Runner]: Takes a handler, gives back the runner.
    """
    return lambda handler: cli_runner(handler, prefix=("ai",))


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]) -> None:
    """
    Make `time.monotonic` advance only by the waits the client asks for.
    """
    monkeypatch.setattr(time, "monotonic", lambda: sum(no_sleep))


def _queue(*payloads: Any) -> Callable[[httpx.Request], httpx.Response]:
    responses: Iterator[Any] = iter(payloads)
    return lambda request: respond(next(responses))


def _json(result: Result) -> Any:
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def test_ask(run: Callable[..., Runner]) -> None:
    result, sent = run(_queue({"response": {"text": "Yes"}}))(
        "ask",
        "e-1",
        "Is it signed?",
        "--citations",
        "--history",
        '[{"role": "user", "content": "Hi"}]',
    )

    assert _json(result) == {"text": "Yes", "citations": []}
    assert sent[0].url.path == "/pubapi/v1/ai/document/e-1/ask"
    assert body(sent[0]) == {
        "question": "Is it signed?",
        "includeCitations": True,
        "chatHistory": {"messages": [{"role": "user", "content": "Hi"}]},
    }


def test_ask_refuses_a_bad_history(run: Callable[..., Runner]) -> None:
    result, sent = run(_queue())("ask", "e-1", "Q?", "--history", '[{"role": "bot"}]')

    assert result.exit_code == 2
    assert "0.role" in result.output
    assert sent == []


def test_summarize(run: Callable[..., Runner]) -> None:
    result, sent = run(_queue({"response": {"text": "A summary"}}))("summarize", "e-1")

    assert _json(result)["text"] == "A summary"
    assert sent[0].url.path == "/pubapi/v1/ai/document/e-1/summary"


def test_assistant_ask_without_wait(run: Callable[..., Runner]) -> None:
    execution = {"conversationId": "c-1", "executionId": "x-1"}
    result, sent = run(_queue(execution))(
        "assistant-ask",
        "Where is the budget?",
        "--folder-id",
        "f-1",
        "--entry-id",
        "e-1",
        "--entry-id",
        "e-2",
        "--all",
        "--web",
        "--model-version",
        "gemini-2.5-flash",
    )

    assert _json(result)["execution_id"] == "x-1"
    assert len(sent) == 1
    assert body(sent[0]) == {
        "question": "Where is the budget?",
        "selectedItems": {
            "folders": [{"id": "f-1"}],
            "files": [{"entryId": "e-1"}, {"entryId": "e-2"}],
            "allEgnyteSearch": True,
            "webSearch": True,
        },
        "modelDetails": {"version": "gemini-2.5-flash"},
    }


def test_assistant_ask_waits_and_keeps_the_ids(
    run: Callable[..., Runner], no_sleep: list[float]
) -> None:
    result, sent = run(
        _queue(
            {"conversationId": "c-1", "executionId": "x-1"},
            {"status": "IN_PROGRESS"},
            {"status": "COMPLETED", "responseText": "In Finance"},
        )
    )("assistant-ask", "Where is the budget?", "--wait", "--interval", "3")

    output = _json(result)
    assert output["conversation_id"] == "c-1"
    assert output["execution_id"] == "x-1"
    assert output["response_text"] == "In Finance"
    assert [r.url.path for r in sent[1:]] == ["/pubapi/v1/ai/assistant/x-1/status"] * 2
    assert no_sleep == [3.0]


def test_assistant_status(run: Callable[..., Runner]) -> None:
    result, sent = run(_queue({"status": "IN_PROGRESS"}))(
        "assistant-status", "x-1", "--no-citations"
    )

    assert _json(result)["status"] == "IN_PROGRESS"
    assert sent[0].url.params["includeCitations"] == "false"


def test_assistant_status_waits(
    run: Callable[..., Runner], no_sleep: list[float]
) -> None:
    result, sent = run(_queue({"status": "IN_PROGRESS"}, {"status": "FAILED"}))(
        "assistant-status", "x-1", "--wait"
    )

    assert _json(result)["status"] == "FAILED"
    assert len(sent) == 2
    assert no_sleep == [10.0]


def test_assistant_status_wait_times_out(run: Callable[..., Runner]) -> None:
    running = {"status": "IN_PROGRESS"}
    result, sent = run(_queue(running, running, running))(
        "assistant-status", "x-1", "--wait", "--interval", "5", "--timeout", "5"
    )

    assert result.exit_code == 1
    assert "still IN_PROGRESS after 5s" in str(result.exception)
    assert len(sent) == 2


def test_agents(run: Callable[..., Runner]) -> None:
    result, sent = run(_queue([{"agentId": "a-1", "name": "llm agent"}]))(
        "agents", "--sort-by", "createdOn", "--sort-order", "desc"
    )

    assert _json(result)[0]["agent_id"] == "a-1"
    assert dict(sent[0].url.params) == {"sortBy": "createdOn", "sortOrder": "desc"}


def test_agent_ask(run: Callable[..., Runner]) -> None:
    result, sent = run(_queue({"requestId": "r-1", "conversationId": "c-2"}))(
        "agent-ask",
        "a-1",
        "Key findings?",
        "--instructions",
        "Be brief",
        "--entry-id",
        "e-1",
        "--folder-id",
        "f-1",
        "--conversation-id",
        "c-2",
    )

    assert _json(result)["request_id"] == "r-1"
    assert sent[0].url.path == "/pubapi/v1/ai/agents/a-1/ask"
    assert body(sent[0]) == {
        "question": "Key findings?",
        "instructions": "Be brief",
        "conversationId": "c-2",
        "entryIds": ["e-1"],
        "selectedItems": {"folders": [{"id": "f-1"}]},
    }


def test_agent_ask_waits(run: Callable[..., Runner]) -> None:
    result, sent = run(
        _queue(
            {"requestId": "r-1", "conversationId": "c-2"},
            {"status": "COMPLETED", "responseText": "Done"},
        )
    )("agent-ask", "a-1", "Key findings?", "--wait")

    output = _json(result)
    assert output["request_id"] == "r-1"
    assert output["conversation_id"] == "c-2"
    assert output["response_text"] == "Done"
    assert sent[1].url.path == "/pubapi/v1/ai/agents/a-1/ask/r-1/status"


@pytest.mark.parametrize("wait", [False, True])
def test_agent_status(run: Callable[..., Runner], wait: bool) -> None:
    flags = ["--wait"] if wait else []
    result, sent = run(_queue({"status": "FAILED"}))(
        "agent-status", "a-1", "r-1", *flags
    )

    assert _json(result)["status"] == "FAILED"
    assert sent[0].url.path == "/pubapi/v1/ai/agents/a-1/ask/r-1/status"


def test_search(run: Callable[..., Runner]) -> None:
    hit = {"filename": "Report.pdf", "chunks": [{"chunkText": "Revenue", "score": 0.9}]}
    result, sent = run(_queue({"results": [hit]}))(
        "search",
        "quarterly report",
        "--semantic-weight",
        "0.8",
        "--folder",
        "/Shared/Finance",
        "--exclude-folder",
        "/Shared/Finance/Old",
        "--prefer-folder",
        "/Shared/Finance/2023",
        "--created-after",
        "2021-01-01",
        "--limit",
        "10",
    )

    assert _json(result)[0]["chunks"][0]["chunk_text"] == "Revenue"
    assert sent[0].url.path == "/pubapi/v1/hybrid-search"
    assert body(sent[0]) == {
        "query": "quarterly report",
        "semanticWeight": 0.8,
        "folderPaths": ["/Shared/Finance"],
        "excludeFolderPaths": ["/Shared/Finance/Old"],
        "preferredFolderPath": "/Shared/Finance/2023",
        "createdAfter": 1609459200000,
        "limit": 10,
    }


def test_search_refuses_a_weight_out_of_range(run: Callable[..., Runner]) -> None:
    result, sent = run(_queue())("search", "budget", "--semantic-weight", "2")

    assert result.exit_code == 2
    assert sent == []
