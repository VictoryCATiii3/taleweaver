"""The bundled default adventure ("The Architect") reaches every new user exactly once."""

import pytest
from sqlalchemy import func, select

from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.services import default_adventures
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _template_titles() -> list[str]:
    async with TestSessionLocal() as session:
        return list((await session.execute(select(AdventureTemplate.title))).scalars())


async def _imported_flag() -> bool:
    async with TestSessionLocal() as session:
        user = (await session.execute(select(User).where(User.username == "test_user"))).scalar()
        return user.has_imported_defaults


async def test_bundled_defaults_include_the_architect():
    # Arrange / Act
    names = [p.name for p in default_adventures.default_adventure_files()]

    # Assert
    assert "The_Architect.adz" in names


async def test_first_login_imports_the_architect_once(auth_client):
    # Arrange / Act
    first = await auth_client.get("/api/auth/me")
    second = await auth_client.get("/api/auth/me")

    # Assert
    assert first.status_code == 200
    assert second.status_code == 200
    assert (await _template_titles()).count("The Architect") == 1
    assert await _imported_flag() is True


async def test_failed_import_is_retried_on_next_login(auth_client, monkeypatch):
    # Arrange
    real_import = default_adventures.import_default_adventures

    async def failing_import(db, owner_id, overwrite=False) -> bool:
        return False

    monkeypatch.setattr(default_adventures, "import_default_adventures", failing_import)

    # Act
    await auth_client.get("/api/auth/me")
    flag_after_failure = await _imported_flag()
    monkeypatch.setattr(default_adventures, "import_default_adventures", real_import)
    await auth_client.get("/api/auth/me")

    # Assert
    assert flag_after_failure is False
    assert "The Architect" in await _template_titles()
    assert await _imported_flag() is True


async def test_missing_defaults_directory_keeps_flag_unset(auth_client, monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setattr(default_adventures, "DEFAULT_ADVENTURES_DIR", tmp_path / "missing")

    # Act
    response = await auth_client.get("/api/auth/me")

    # Assert
    assert response.status_code == 200
    assert await _imported_flag() is False


async def test_claim_is_atomic(auth_client):
    # Arrange
    async with TestSessionLocal() as session:
        user_id = (
            await session.execute(select(User.id).where(User.username == "test_user"))
        ).scalar()

    # Act
    async with TestSessionLocal() as first, TestSessionLocal() as second:
        won_first = await default_adventures._set_flag(first, user_id, True)
        won_second = await default_adventures._set_flag(second, user_id, True)

    # Assert
    assert (won_first, won_second) == (True, False)
    async with TestSessionLocal() as session:
        count = await session.scalar(select(func.count()).select_from(AdventureTemplate))
    assert count == 0
