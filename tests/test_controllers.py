import asyncio
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from urllib.parse import parse_qs

import httpx
import pytest

from core.config import Settings
from ui.controllers import DuplicatedError, MainController
from ui.models import NewUser


def make_settings(**kwargs: Any) -> Settings:
    defaults: dict[str, Any] = {
        "host": "https://domserver.example.test",
        "username": "api_admin",
        "password": "api_password",
        "category_id": 1,
        "affiliation_id": 2,
        "affiliation_country": "TWN",
        "user_roles": [3],
        "version": "7.3.2",
        "api_version": "v4",
    }
    defaults.update(kwargs)
    return Settings(**defaults)  # type: ignore[arg-type]


def test_googleform_no_id_does_not_call_transport() -> None:
    settings = make_settings(google_form_id=None)
    controller = MainController(settings)
    user = NewUser(
        username="test_user",
        name="Test School",
        email="test@example.com",  # type: ignore[arg-type]
        password="pwd",
    )

    result = asyncio.run(controller.log_to_googleform(user))
    assert result is False


def test_googleform_with_id_posts_formdata() -> None:
    settings = make_settings(google_form_id="FORM_123")
    controller = MainController(settings)
    user = NewUser(
        username="test_user",
        name="Test School",
        email="test@example.com",  # type: ignore[arg-type]
        password="pwd",
    )
    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(200, text="OK")

    transport = httpx.MockTransport(handler)

    with patch(
        "httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)
    ):
        result = asyncio.run(controller.log_to_googleform(user))

    assert result is True
    assert len(recorded_requests) == 1
    req = recorded_requests[0]
    assert "FORM_123" in str(req.url)
    payload = parse_qs(req.content.decode())
    assert set(payload) == {
        "entry.2005418205",
        "entry.533178960",
        "emailAddress",
        "entry.55480983",
    }
    assert payload["entry.2005418205"] == ["test_user"]
    assert payload["entry.533178960"] == ["Test School"]
    assert payload["emailAddress"] == ["test@example.com"]
    assert payload["entry.55480983"] == ["streamlit-form"]


def test_creat_account_duplicate_username_raises_error() -> None:
    settings = make_settings()
    controller = MainController(settings)
    user = NewUser(
        username="existing_coder",
        name="Unique Name",
        email="coder@example.com",  # type: ignore[arg-type]
        password="pwd",
    )

    mock_users_api = AsyncMock()
    mock_users_api.__aenter__.return_value = mock_users_api
    mock_users_api.__aexit__.return_value = None
    mock_user_model = MagicMock()
    mock_user_model.username = "existing_coder"
    mock_user_model.name = "Other Name"
    mock_users_api.all_users.return_value = [mock_user_model]

    with patch("ui.controllers.UsersAPI", return_value=mock_users_api):
        with pytest.raises(DuplicatedError) as exc_info:
            asyncio.run(controller.creat_account(user))

    assert "帳號重複" in str(exc_info.value)


def test_creat_account_missing_category_id_raises_value_error() -> None:
    settings = make_settings(category_id=None)
    controller = MainController(settings)
    user = NewUser(
        username="new_coder",
        name="New School",
        email="coder@example.com",  # type: ignore[arg-type]
        password="pwd",
    )

    with pytest.raises(ValueError) as exc_info:
        asyncio.run(controller.creat_account(user))

    assert "CATEGORY_ID" in str(exc_info.value)


def test_creat_account_success() -> None:
    settings = make_settings(category_id=1, affiliation_id=2)
    controller = MainController(settings)
    user = NewUser(
        username="fresh_coder",
        name="Fresh School",
        email="fresh@example.com",  # type: ignore[arg-type]
        password="secret_fresh_password",
    )

    mock_users_api = AsyncMock()
    mock_users_api.__aenter__.return_value = mock_users_api
    mock_users_api.__aexit__.return_value = None
    mock_users_api.all_users.return_value = []

    mock_web = AsyncMock()
    mock_web.__aenter__.return_value = mock_web
    mock_web.__aexit__.return_value = None
    mock_web.login.return_value = None
    mock_web.create_team_and_user.return_value = ("team_10", "user_10")
    mock_web.set_user_password.return_value = None

    mock_cls = MagicMock(return_value=mock_web)
    mock_gateway_cls = MagicMock(return_value=mock_cls)

    with (
        patch("ui.controllers.UsersAPI", return_value=mock_users_api),
        patch(
            "ui.controllers.DomServerWebGateway",
            mock_gateway_cls,
        ),
    ):
        result = asyncio.run(controller.creat_account(user))

    assert result.username == "fresh_coder"
    mock_web.login.assert_awaited_once()
    mock_web.create_team_and_user.assert_awaited_once_with(
        ANY,
        1,
        2,
    )
    mock_web.set_user_password.assert_awaited_once_with(
        "user_10",
        "secret_fresh_password",
        [3],
    )


def test_creat_account_duplicate_name_does_not_mutate() -> None:
    settings = make_settings()
    controller = MainController(settings)
    user = NewUser(
        username="new_coder",
        name="Existing School",
        email="coder@example.com",  # type: ignore[arg-type]
        password="pwd",
    )

    mock_users_api = AsyncMock()
    mock_users_api.__aenter__.return_value = mock_users_api
    existing = MagicMock()
    existing.username = "other_coder"
    existing.name = "Existing School"
    mock_users_api.all_users.return_value = [existing]
    mock_gateway = MagicMock()

    with (
        patch("ui.controllers.UsersAPI", return_value=mock_users_api),
        patch("ui.controllers.DomServerWebGateway", mock_gateway),
    ):
        with pytest.raises(DuplicatedError):
            asyncio.run(controller.creat_account(user))

    mock_gateway.assert_not_called()
