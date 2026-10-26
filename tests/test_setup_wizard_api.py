"""Setup wizard state endpoints: per-user, admin-only, merged partial updates."""

import pytest

from backend.core.auth import create_access_token, get_password_hash
from backend.models.user import User
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

URL = "/api/settings/setup-wizard"


async def test_new_admin_starts_pending(auth_client):
    # Act
    response = await auth_client.get(URL)

    # Assert
    assert response.status_code == 200
    assert response.json() == {"state": "pending", "visuals_opt_out": False}


async def test_update_merges_fields(auth_client):
    # Arrange
    await auth_client.put(URL, json={"visuals_opt_out": True})

    # Act
    response = await auth_client.put(URL, json={"state": "dismissed"})

    # Assert
    assert response.status_code == 200
    assert response.json() == {"state": "dismissed", "visuals_opt_out": True}
    assert (await auth_client.get(URL)).json()["state"] == "dismissed"


async def test_rejects_unknown_state(auth_client):
    # Act
    response = await auth_client.put(URL, json={"state": "maybe"})

    # Assert
    assert response.status_code == 422


async def test_non_admin_is_forbidden(client):
    # Arrange
    async with TestSessionLocal() as session:
        session.add(User(username="player", hashed_password=get_password_hash("pw"), role="user"))
        await session.commit()
    player_headers = {"Authorization": f"Bearer {create_access_token({'sub': 'player'})}"}

    # Act
    response = await client.get(URL, headers=player_headers)

    # Assert
    assert response.status_code == 403
