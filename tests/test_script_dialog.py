"""Script-driven choice dialogs: tw.dialog.choose opens, the choice endpoint runs the handler."""

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from backend.api.routes.adventures import dialog_service
from backend.api.routes.adventures.dialog_service import DialogChoiceResolver
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.core.script_validator import check_scripts_and_guards
from backend.engine.scripting.context import GameContext
from backend.engine.scripting.dialog import client_dialog, pending_dialog
from backend.engine.scripting.runner import ScriptRunner
from backend.models.chat import ChatMessage
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context

INIT_SCRIPT = """
def on_bomb_wire(answ):
    if answ == 0:
        tw.vars.set('bomb_disarmed', 1)
        tw.narrate('You disarmed the trap.')
        return
    if answ == 1:
        tw.game.game_over('The bomb exploded.')
        return
    tw.dialog.choose('It keeps ticking. Now what?', ['Run', 'Pray'], on_choice=on_bomb_wire)
"""
OPEN_BOMB_DIALOG = (
    "tw.dialog.choose('The bomb starts ticking.', "
    "['Cut the red wire', 'Cut the blue wire', 'Scream like a baby'], on_choice='on_bomb_wire')"
)


def _run(code: str, context: GameContext, init_script: str = INIT_SCRIPT) -> None:
    runner = ScriptRunner([], init_script=init_script)
    runner.execute_code(code, {"tw": context, "game": context})


async def _manager(db, narrate: bool = False) -> GameTurnManager:
    user, adv, _avatar, _state = await _seed_game_context(db)
    adv.original_manifest = {"init_script": INIT_SCRIPT}
    await db.commit()
    manager = GameTurnManager(db, "session-1", user)
    await manager.initialize()
    code = OPEN_BOMB_DIALOG.replace(")", f", narrate={narrate})") if narrate else OPEN_BOMB_DIALOG
    await manager._execute_inline_script(code, "on_pickup", "BOMB")
    await db.commit()
    return manager


def _dialog(manager: GameTurnManager) -> dict:
    return pending_dialog(manager.state.entity_states)


def test_choose_records_pending_dialog_with_author_indices():
    # Arrange
    context = GameContext()

    # Act
    _run(OPEN_BOMB_DIALOG, context)

    # Assert
    dialog = context.changeset.pending_dialog
    assert dialog["handler"] == "on_bomb_wire"
    assert [o["index"] for o in dialog["options"]] == [0, 1, 2]
    assert context.changeset.has_changes


def test_visible_if_hides_options_but_keeps_original_index():
    # Arrange
    context = GameContext(script_vars={"has_pliers": False})
    code = (
        "tw.dialog.choose('Wires?', [{'label': 'Use pliers', "
        "'visible_if': \"tw.vars.get('has_pliers') == True\"}, 'Pull'], on_choice='on_bomb_wire')"
    )

    # Act
    _run(code, context)

    # Assert
    assert context.changeset.pending_dialog["options"] == [{"index": 1, "label": "Pull"}]


def test_function_reference_is_accepted_and_second_dialog_ignored():
    # Arrange
    context = GameContext()
    code = (
        "tw.dialog.choose('A?', ['x'], on_choice=on_bomb_wire)\n"
        "opened = tw.dialog.choose('B?', ['y'], on_choice=on_bomb_wire)\n"
        "tw.vars.set('second_opened', opened)"
    )

    # Act
    _run(code, context)

    # Assert
    assert context.changeset.pending_dialog["prompt"] == "A?"
    assert context.changeset.pending_dialog["handler"] == "on_bomb_wire"
    assert context.changeset.var_updates["second_opened"] is False


def test_invalid_handler_does_not_open_dialog():
    # Arrange
    context = GameContext()

    # Act
    _run("tw.dialog.choose('A?', ['x'], on_choice='not valid()')", context)

    # Assert
    assert context.changeset.pending_dialog is None


def test_client_dialog_hides_handler():
    # Arrange
    context = GameContext()
    _run(OPEN_BOMB_DIALOG, context)

    # Act
    payload = client_dialog(context.changeset.pending_dialog)

    # Assert
    assert "handler" not in payload
    assert payload["options"][2] == {"index": 2, "label": "Scream like a baby"}


@pytest.mark.asyncio
async def test_choice_runs_handler_and_clears_dialog():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)
        dialog_id = _dialog(manager)["id"]

        # Act
        result = await DialogChoiceResolver(manager).resolve(dialog_id, 0, None)

        # Assert
        assert result["messages"] == ["You disarmed the trap."]
        assert _dialog(manager) is None
        assert manager.state.entity_states["__script_vars__"]["bomb_disarmed"] == 1
        rows = (await db.execute(select(ChatMessage.content))).scalars().all()
        assert "[Choice] Cut the red wire" in rows


@pytest.mark.asyncio
async def test_handler_can_open_follow_up_dialog():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)
        first_id = _dialog(manager)["id"]

        # Act
        await DialogChoiceResolver(manager).resolve(first_id, 2, None)

        # Assert
        follow_up = _dialog(manager)
        assert follow_up["id"] != first_id
        assert follow_up["prompt"] == "It keeps ticking. Now what?"


@pytest.mark.asyncio
async def test_game_over_handler_ends_session():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)

        # Act
        await DialogChoiceResolver(manager).resolve(_dialog(manager)["id"], 1, None)

        # Assert
        assert manager.state.session.status == "game_over"


@pytest.mark.asyncio
async def test_stale_dialog_id_and_unknown_index_are_rejected():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)
        resolver = DialogChoiceResolver(manager)

        # Act
        with pytest.raises(HTTPException) as stale:
            await resolver.resolve("stale", 0, None)
        with pytest.raises(HTTPException) as unknown:
            await resolver.resolve(_dialog(manager)["id"], 7, None)

        # Assert
        assert stale.value.status_code == 409
        assert unknown.value.status_code == 400
        assert _dialog(manager) is not None


@pytest.mark.asyncio
async def test_narrated_choice_saves_llm_outcome(monkeypatch):
    class FakeLLM:
        def __init__(self, *_args, **_kwargs):
            pass

        async def aexecute_simple_task(self, _system, user_prompt, _model, **_kwargs):
            assert "Cut the red wire" in user_prompt
            return "The red wire parts with a soft snip."

    async with TestSessionLocal() as db:
        # Arrange
        monkeypatch.setattr(dialog_service, "GameMasterLLM", FakeLLM)
        manager = await _manager(db, narrate=True)

        # Act
        result = await DialogChoiceResolver(manager).resolve(_dialog(manager)["id"], 0, None)

        # Assert
        assert result["messages"][-1] == "The red wire parts with a soft snip."


def test_validator_flags_handler_missing_from_init_script():
    # Arrange
    payload = {
        "adventure": {"init_script": INIT_SCRIPT},
        "objects": [
            {"id": "BOMB", "item_type": "MISC", "on_pickup_script": OPEN_BOMB_DIALOG},
            {"id": "BOX", "on_read_script": "tw.dialog.ask('?', ['a'], on_choice='nowhere')"},
        ],
    }

    # Act
    findings = check_scripts_and_guards(payload)

    # Assert
    missing = [f for f in findings if f.code == "dialog_handler_missing"]
    assert [f.context["handler"] for f in missing] == ["nowhere"]
