from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.api.routes.adventures.sequence_hooks import (
    build_sequence_intro,
    run_sequence_transition_hooks,
)

ADVENTURE = SimpleNamespace(
    sequences=[
        {
            "id": "SEQ_1",
            "title": "Chapter 1",
            "on_end_sequence_text": "Chapter one is over.",
        },
        {
            "id": "SEQ_2",
            "title": "Chapter 2",
            "description": "Enter the trenches.",
            "on_start_sequence_script": "tw.say('go')",
            "on_start_sequence_text": "Chapter 2 begins.",
        },
    ]
)


@pytest.mark.asyncio
async def test_transition_hooks_run_end_then_start():
    # Arrange
    manager = SimpleNamespace(_execute_inline_script=AsyncMock(return_value=["script msg"]))
    save = AsyncMock()

    # Act
    messages = await run_sequence_transition_hooks(manager, save, ADVENTURE, "SEQ_1", "SEQ_2")

    # Assert
    assert messages == ["Chapter one is over.", "script msg", "Chapter 2 begins."]
    manager._execute_inline_script.assert_awaited_once_with(
        "tw.say('go')", "on_start_sequence", "SEQ_2"
    )
    assert [c.args for c in save.await_args_list] == [
        ("system", "Chapter one is over."),
        ("system", "Chapter 2 begins."),
    ]


@pytest.mark.asyncio
async def test_transition_hooks_final_sequence_runs_only_end():
    # Arrange
    manager = SimpleNamespace(_execute_inline_script=AsyncMock(return_value=[]))
    save = AsyncMock()

    # Act
    messages = await run_sequence_transition_hooks(manager, save, ADVENTURE, "SEQ_1", "SEQ_1")

    # Assert
    assert messages == ["Chapter one is over."]


def test_sequence_intro_contains_title_and_premise():
    # Act
    intro = build_sequence_intro(ADVENTURE, "SEQ_2")

    # Assert
    assert intro is not None
    assert intro["title"] == "Chapter 2"
    assert "[SEQUENCE_START]" in intro["prompt"]
    assert "Enter the trenches." in intro["prompt"]


def test_sequence_intro_unknown_sequence_is_none():
    # Act / Assert
    assert build_sequence_intro(ADVENTURE, "MISSING") is None
