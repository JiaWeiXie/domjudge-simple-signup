import urllib.parse
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from core.config import Settings
from ui.controllers import MainController
from ui.models import NewUser

LOGIN_HTML = """<!doctype html>
<html>
<body>
<form action="/login" method="post">
  <input type="hidden" name="_csrf_token" value="TEST_CSRF_TOKEN">
  <input type="text" name="_username">
  <input type="password" name="_password">
</form>
</body>
</html>"""

TEAM_ADD_HTML = """<!doctype html>
<html>
<body>
<form method="post" action="/jury/teams/add">
  <input name="team[name]" value="">
  <input name="team[displayName]" value="">
  <select name="team[category]">
    <option value="1" selected>default</option>
  </select>
  <select name="team[affiliation]">
    <option value="1" selected>course001</option>
  </select>
  <input name="team[penalty]" value="0">
  <input type="checkbox" name="team[enabled]" value="1" checked>
  <select name="team[addUserForTeam]">
    <option value="">none</option>
    <option value="create-new-user" selected>create new user</option>
  </select>
  <input name="team[newUsername]" value="">
</form>
</body>
</html>"""

TEAM_VIEW_HTML = """<!doctype html>
<html>
<body>
<table>
  <tbody>
    <tr><th>ID</th><td>99</td></tr>
    <tr><th>User</th><td><a href="/jury/users/7">test-v8-user</a></td></tr>
  </tbody>
</table>
</body>
</html>"""

USER_EDIT_HTML = """<!doctype html>
<html>
<body>
<form method="post" action="/jury/users/7/edit">
  <input name="user[username]" value="test-v8-user">
  <input name="user[name]" value="Test V8 User">
  <input name="user[email]" value="v8@example.org">
  <input name="user[plainPassword]" value="">
  <input type="checkbox" name="user[enabled]" value="1" checked>
  <select name="user[user_roles][]" multiple>
    <option value="3" selected>Team Member</option>
    <option value="5">observer</option>
  </select>
</form>
</body>
</html>"""


def make_signup_settings(**kwargs: Any) -> Settings:
    defaults: dict[str, Any] = {
        "host": "https://example.test",
        "username": "admin",
        "password": "secret",
        "version": "8.3.1",
        "api_version": "v4",
        "category_id": 3,
        "affiliation_id": 8,
        "affiliation_country": "TWN",
        "user_roles": [3],
    }
    defaults.update(kwargs)
    return Settings(**defaults)  # type: ignore[arg-type]


def parse_body(request: httpx.Request) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(
        request.content.decode("utf-8"), keep_blank_values=True
    )


@pytest.mark.anyio
async def test_creat_account_v8_domjudge_integration() -> None:
    captured_posts: dict[str, dict[str, list[str]]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method

        if path == "/login" and method == "GET":
            return httpx.Response(200, text=LOGIN_HTML)
        if path == "/login" and method == "POST":
            captured_posts["login"] = parse_body(request)
            return httpx.Response(302, headers={"Location": "/jury"})
        if path == "/jury" and method == "GET":
            return httpx.Response(200, text="<html><body>Jury Dashboard</body></html>")

        if path == "/jury/teams/add" and method == "GET":
            return httpx.Response(200, text=TEAM_ADD_HTML)
        if path == "/jury/teams/add" and method == "POST":
            captured_posts["team_add"] = parse_body(request)
            return httpx.Response(302, headers={"Location": "/jury/teams/99"})
        if path == "/jury/teams/99" and method == "GET":
            return httpx.Response(200, text=TEAM_VIEW_HTML)

        if path == "/jury/users/7/edit" and method == "GET":
            return httpx.Response(200, text=USER_EDIT_HTML)
        if path == "/jury/users/7/edit" and method == "POST":
            captured_posts["user_edit"] = parse_body(request)
            return httpx.Response(302, headers={"Location": "/jury/users/7"})
        if path == "/jury/users/7" and method == "GET":
            return httpx.Response(200, text="<html><body>User View</body></html>")

        return httpx.Response(404)

    settings = make_signup_settings(user_roles=[3])
    controller = MainController(settings)

    form_user = NewUser(
        username="test-v8-user",
        name="Test V8 User",
        password="v8-password",
        email="v8@example.org",
    )

    mock_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://example.test",
    )

    with (
        patch("ui.controllers.UsersAPI") as mock_users_api_cls,
        patch(
            "domjudge_tool_cli.services.web.v8.DomServerWeb.new_client",
            return_value=mock_client,
        ),
    ):
        mock_api = AsyncMock()
        mock_api.all_users.return_value = []
        mock_users_api_cls.return_value.__aenter__.return_value = mock_api

        result = await controller.creat_account(form_user)

    assert result == form_user
    assert result.username == "test-v8-user"

    # Verify team add POST data
    assert "team_add" in captured_posts
    team_post = captured_posts["team_add"]
    assert team_post["team[name]"] == ["test-v8-user"]
    assert team_post["team[displayName]"] == ["Test V8 User"]
    assert team_post["team[category]"] == ["3"]
    assert team_post["team[affiliation]"] == ["8"]
    assert team_post["team[addUserForTeam]"] == ["create-new-user"]
    assert team_post["team[newUsername]"] == ["test-v8-user"]
    # Critical: MUST NOT send v7 nested username field
    assert "team[users][0][username]" not in team_post

    # Verify user edit / password POST data
    assert "user_edit" in captured_posts
    user_post = captured_posts["user_edit"]
    assert user_post["user[plainPassword]"] == ["v8-password"]
    assert user_post["user[user_roles][]"] == ["3"]
