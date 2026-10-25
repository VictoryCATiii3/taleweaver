"""AI fix suggestions and patches for sequence-level validation findings."""

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.routes.adventures.editing.ai_fix_context import (
    _format_focused_world_block,
    _summarize_world_for_fix,
)
from backend.main import app
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from tests.conftest import TestSessionLocal
from tests.test_ai_fix_endpoint import _auth_headers, _seed_simple_adventure

_SEQUENCES = [
    {
        "id": "SEQ_2_ESCAPE",
        "order": 2,
        "title": "Escape",
        "walkthrough": "Enter the cryo pod to win.",
        "guard_expression": "parasite_extracted and entered_cryo",
        "soft_rules": [
            {
                "id": "BRIBE_GUARD",
                "condition": "The player bribes the pod guard",
                "script": "tw.vars.set('guard_bribed', True)",
                "max_triggers": 1,
            }
        ],
    },
    {
        "id": "SEQ_1_WAKE",
        "order": 1,
        "title": "Wake Up",
        "walkthrough": "Extract the parasite.",
        "guard_expression": "",
    },
]


@pytest.fixture
async def client():
    app.dependency_overrides.clear()
    from backend.core.database import get_db
    from tests.conftest import override_get_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _seed_with_sequences(username: str) -> str:
    user = User(
        username=username,
        hashed_password="x",
        role="admin",
        llm_settings={"complex_model_provider": "openai", "complex_model": "gpt-4o"},
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)
        tpl = await db.get(AdventureTemplate, tpl_id)
        assert tpl is not None
        tpl.sequences = [dict(s) for s in _SEQUENCES]
        tpl.original_manifest = {"sequences": [dict(s) for s in _SEQUENCES]}
        await db.commit()
    return tpl_id


def _fake_llm(monkeypatch, proposals: list[dict]) -> dict:
    captured: dict = {}

    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, *, user_prompt, **kwargs):
            captured["user_prompt"] = user_prompt
            return SimpleNamespace(proposals=proposals)

    from backend.api.routes.adventures.editing import ai_fix_llm

    monkeypatch.setattr(ai_fix_llm, "GameMasterLLM", _FakeLLM)
    return captured


def _sequence_finding() -> dict:
    return {
        "finding_code": "sequence_guard_pacing_mismatch",
        "finding_message": "Chapter guard requires its own ending.",
        "finding_location": "sequence:SEQ_2_ESCAPE",
        "finding_context": {},
        "finding_severity": "warn",
    }


def test_summary_and_focused_prompt_include_target_sequence():
    payload = SimpleNamespace(adventure={"title": "T", "sequences": _SEQUENCES})

    summary = _summarize_world_for_fix(payload)
    block = _format_focused_world_block(summary, location="sequence:SEQ_2_ESCAPE")

    assert [s["id"] for s in summary["sequences"]] == ["SEQ_1_WAKE", "SEQ_2_ESCAPE"]
    assert "TARGET SEQUENCE (SEQ_2_ESCAPE)" in block
    assert "Enter the cryo pod to win." in block
    assert "Extract the parasite." in block


async def test_suggest_fix_keeps_sequence_proposals(client, setup_test_db, monkeypatch):
    tpl_id = await _seed_with_sequences("seq_fix_suggest")
    captured = _fake_llm(
        monkeypatch,
        [
            {
                "title": "Drop self-referencing flags",
                "summary": "Only require state from earlier chapters.",
                "patches": [
                    {
                        "target_type": "sequence",
                        "target_id": "SEQ_2_ESCAPE",
                        "description": "Relax the start guard.",
                        "field_updates": {"guard_expression": "parasite_extracted"},
                    }
                ],
            }
        ],
    )

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("seq_fix_suggest"),
        json=_sequence_finding(),
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["error"] is None
    assert body["proposals"][0]["patches"][0]["target_type"] == "sequence"
    assert "TARGET SEQUENCE (SEQ_2_ESCAPE)" in captured["user_prompt"]


async def test_suggest_fix_reports_discarded_proposals(client, setup_test_db, monkeypatch):
    tpl_id = await _seed_with_sequences("seq_fix_dropped")
    _fake_llm(
        monkeypatch,
        [
            {
                "title": "Edit the quest",
                "summary": "Patch an unsupported target.",
                "patches": [
                    {
                        "target_type": "quest",
                        "target_id": "Q1",
                        "description": "Not patchable.",
                        "field_updates": {"description": "x"},
                    }
                ],
            }
        ],
    )

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("seq_fix_dropped"),
        json=_sequence_finding(),
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["proposals"] == []
    assert "quest" in body["error"]


async def test_apply_fix_updates_and_clears_sequence_guards(client, setup_test_db):
    tpl_id = await _seed_with_sequences("seq_fix_apply")
    proposal = {
        "title": "Relax guards",
        "summary": "Fix pacing.",
        "rationale": None,
        "patches": [
            {
                "target_type": "sequence",
                "target_id": "seq_2_escape",
                "description": "Start guard only needs earlier state.",
                "field_updates": {"guard_expression": "", "walkthrough": "Board the pod."},
            }
        ],
    }

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("seq_fix_apply"),
        json={"finding_signature": "warn|x|y|z", "proposal": proposal},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["applied_targets"] == ["sequence:SEQ_2_ESCAPE"]
    async with TestSessionLocal() as db:
        tpl = await db.get(AdventureTemplate, tpl_id)
        assert tpl is not None
        seq = next(s for s in tpl.sequences if s["id"] == "SEQ_2_ESCAPE")
        assert seq["guard_expression"] == ""
        assert seq["walkthrough"] == "Board the pod."
        assert tpl.original_manifest["sequences"] == tpl.sequences


async def test_apply_fix_rejects_invalid_sequence_guard(client, setup_test_db):
    tpl_id = await _seed_with_sequences("seq_fix_bad_guard")
    proposal = {
        "title": "Broken guard",
        "summary": "Syntax error.",
        "rationale": None,
        "patches": [
            {
                "target_type": "sequence",
                "target_id": "SEQ_2_ESCAPE",
                "description": "Invalid expression.",
                "field_updates": {"guard_expression": "parasite_extracted and ("},
            }
        ],
    }

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("seq_fix_bad_guard"),
        json={"finding_signature": "warn|x|y|z", "proposal": proposal},
    )

    assert resp.status_code == 400
    assert "guard_expression" in resp.json()["detail"]


def test_focused_prompt_includes_sequence_soft_rules():
    payload = SimpleNamespace(adventure={"title": "T", "sequences": _SEQUENCES})

    block = _format_focused_world_block(
        _summarize_world_for_fix(payload), location="sequence:SEQ_2_ESCAPE"
    )

    assert "BRIBE_GUARD" in block
    assert "The player bribes the pod guard" in block


def _soft_rule_proposal(field_updates: dict) -> dict:
    return {
        "title": "Tune soft rule",
        "summary": "Fix the bribe rule.",
        "rationale": None,
        "patches": [
            {
                "target_type": "sequence",
                "target_id": "SEQ_2_ESCAPE",
                "description": "Adjust the bribe soft rule.",
                "field_updates": field_updates,
            }
        ],
    }


async def test_apply_fix_patches_existing_soft_rule(client, setup_test_db):
    tpl_id = await _seed_with_sequences("seq_fix_soft_rule")
    updates = {
        "soft_rules.BRIBE_GUARD.guard_expression": "tw.player.has_item('GOLD')",
        "soft_rules.BRIBE_GUARD.max_triggers": 0,
        "soft_rules.BRIBE_GUARD.text": "",
    }

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("seq_fix_soft_rule"),
        json={"finding_signature": "warn|x|y|z", "proposal": _soft_rule_proposal(updates)},
    )

    assert resp.status_code == 200, resp.text
    async with TestSessionLocal() as db:
        tpl = await db.get(AdventureTemplate, tpl_id)
        assert tpl is not None
        seq = next(s for s in tpl.sequences if s["id"] == "SEQ_2_ESCAPE")
        rule = seq["soft_rules"][0]
        assert rule["guard_expression"] == "tw.player.has_item('GOLD')"
        assert rule["max_triggers"] is None
        assert rule["script"] == "tw.vars.set('guard_bribed', True)"


async def test_apply_fix_rejects_unknown_soft_rule(client, setup_test_db):
    tpl_id = await _seed_with_sequences("seq_fix_soft_rule_unknown")
    updates = {"soft_rules.INVENTED_RULE.condition": "Something new"}

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("seq_fix_soft_rule_unknown"),
        json={"finding_signature": "warn|x|y|z", "proposal": _soft_rule_proposal(updates)},
    )

    # Unknown rule ids are treated like any stale AI reference: nothing is applied.
    assert resp.status_code == 200, resp.text
    assert resp.json()["applied_targets"] == []
    async with TestSessionLocal() as db:
        tpl = await db.get(AdventureTemplate, tpl_id)
        assert tpl is not None
        seq = next(s for s in tpl.sequences if s["id"] == "SEQ_2_ESCAPE")
        assert [r["id"] for r in seq["soft_rules"]] == ["BRIBE_GUARD"]
