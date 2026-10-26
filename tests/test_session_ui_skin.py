"""Tests for the per-session dialog skin stored in the database (not in the browser)."""

from sqlalchemy import select

from backend.models.session_state import SessionState
from tests.conftest import TestSessionLocal
from tests.test_adventures_api import _create_adventure


async def _stored_skin(game_id: str):
    async with TestSessionLocal() as db:
        result = await db.execute(select(SessionState).where(SessionState.session_id == game_id))
        return result.scalars().first().ui_skin


async def test_new_sessions_follow_the_adventure_skin(auth_client):
    # Arrange / Act
    ids = await _create_adventure(auth_client, "Default Skin Quest")

    # Assert
    assert await _stored_skin(ids["game_id"]) is None


async def test_session_update_stores_ui_skin(auth_client):
    # Arrange
    ids = await _create_adventure(auth_client, "Skin Quest")

    # Act
    resp = await auth_client.patch(
        f"/api/adventures/sessions/{ids['game_id']}", json={"ui_skin": "terminal"}
    )

    # Assert
    assert resp.status_code == 200, resp.text
    assert await _stored_skin(ids["game_id"]) == "terminal"


async def test_auto_clears_the_stored_skin(auth_client):
    # Arrange
    ids = await _create_adventure(auth_client, "Auto Skin Quest")
    await auth_client.patch(f"/api/adventures/sessions/{ids['game_id']}", json={"ui_skin": "toon"})

    # Act
    resp = await auth_client.patch(
        f"/api/adventures/sessions/{ids['game_id']}", json={"ui_skin": "auto"}
    )

    # Assert
    assert resp.status_code == 200, resp.text
    assert await _stored_skin(ids["game_id"]) is None


async def test_session_update_rejects_unknown_ui_skin(auth_client):
    # Arrange
    ids = await _create_adventure(auth_client, "Bad Skin Quest")

    # Act
    resp = await auth_client.patch(
        f"/api/adventures/sessions/{ids['game_id']}", json={"ui_skin": "neon"}
    )

    # Assert
    assert resp.status_code == 422
