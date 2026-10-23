"""AI fix proposals must respect the editor's field length limits."""

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.routes.adventures.editing.ai_fix_limits import (
    READABLE_DESCRIPTION_MAX,
    format_length_limits,
)
from backend.api.routes.adventures.editing.ai_fix_sanitize import sanitize_proposals
from backend.main import app
from backend.models.user import User
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_ai_fix_endpoint import _auth_headers, _seed_simple_adventure

_SUMMARY = {
    "objects": [
        {"id": "DIARY", "name": "Old Diary", "item_type": "READABLE"},
        {"id": "SAFE_01", "name": "Safe", "item_type": "CONTAINER"},
    ]
}
_TOO_LONG = "x" * (READABLE_DESCRIPTION_MAX + 1)


def _proposal(target_id: str, description: str) -> dict:
    return {
        "title": "Rewrite description",
        "summary": "Adjust the object description.",
        "patches": [
            {
                "target_type": "object",
                "target_id": target_id,
                "description": "New text.",
                "field_updates": {"description": description},
            }
        ],
    }


@pytest.fixture
async def client():
    app.dependency_overrides.clear()
    from backend.core.database import get_db
    from tests.conftest import override_get_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def test_sanitizer_drops_overlong_readable_description_by_id_or_name():
    result = sanitize_proposals(
        [_proposal("DIARY", _TOO_LONG), _proposal("old diary", _TOO_LONG)], _SUMMARY
    )

    assert result.proposals == []
    assert f"max {READABLE_DESCRIPTION_MAX}" in result.error_message()


def test_sanitizer_keeps_long_description_of_non_readable_object():
    result = sanitize_proposals([_proposal("SAFE_01", _TOO_LONG)], _SUMMARY)

    assert len(result.proposals) == 1
    assert result.rejected == []


def test_system_prompt_lists_length_limits():
    limits = format_length_limits()

    assert f"READABLE objects: {READABLE_DESCRIPTION_MAX}" in limits
    assert "adventure.teaser: 300" in limits


async def test_suggest_fix_reports_overlong_proposals(client, setup_test_db, monkeypatch):
    user = User(
        username="fix_limits_suggest",
        hashed_password="x",
        role="admin",
        llm_settings={"complex_model_provider": "openai", "complex_model": "gpt-4o"},
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)
        db.add(
            WorldEntity(
                id="DIARY",
                template_id=tpl_id,
                entity_type="OBJECT",
                name="Old Diary",
                description="A diary.",
                current_scene_id="START",
                item_type="READABLE",
            )
        )
        await db.commit()

    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            return SimpleNamespace(proposals=[_proposal("DIARY", _TOO_LONG)])

    from backend.api.routes.adventures.editing import ai_fix_llm

    monkeypatch.setattr(ai_fix_llm, "GameMasterLLM", _FakeLLM)

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("fix_limits_suggest"),
        json={
            "finding_code": "readable_hint_missing",
            "finding_message": "Diary lacks the hint.",
            "finding_location": "object:DIARY",
            "finding_context": {},
            "finding_severity": "warn",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["proposals"] == []
    assert "object.description" in body["error"]


async def test_apply_fix_rejects_overlong_adventure_field(client, setup_test_db):
    user = User(username="fix_limits_apply", hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    proposal = {
        "title": "Longer teaser",
        "summary": "Expand the teaser.",
        "rationale": None,
        "patches": [
            {
                "target_type": "adventure",
                "target_id": None,
                "description": "Too long.",
                "field_updates": {"teaser": "t" * 301},
            }
        ],
    }

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("fix_limits_apply"),
        json={"finding_signature": "warn|x|y|z", "proposal": proposal},
    )

    assert resp.status_code == 400
    assert "adventure.teaser" in resp.json()["detail"]
