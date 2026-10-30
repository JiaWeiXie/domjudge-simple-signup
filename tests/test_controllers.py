import asyncio
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from urllib.parse import parse_qs

import httpx
import pytest

from core.config import POLICY_TTL_SECONDS, Settings
from ui.controllers import (
    AccountCreationError,
    DuplicatedError,
    InvalidPasswordError,
    MainController,
    _rejection_reason,
    password_byte_length,
)
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
        "min_password_length": 0,
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


def _mock_web(**overrides: Any) -> AsyncMock:
    mock_web = AsyncMock()
    mock_web.__aenter__.return_value = mock_web
    mock_web.__aexit__.return_value = None
    mock_web.login.return_value = None
    mock_web.create_team_and_user.return_value = ("team_10", "user_10")
    mock_web.set_user_password.return_value = None
    # Default to "server advertises nothing", matching the installed release.
    mock_web.get_min_password_length.return_value = None
    for name, value in overrides.items():
        setattr(mock_web, name, value)
    return mock_web


def _mock_users_api() -> AsyncMock:
    mock_users_api = AsyncMock()
    mock_users_api.__aenter__.return_value = mock_users_api
    mock_users_api.__aexit__.return_value = None
    mock_users_api.all_users.return_value = []
    return mock_users_api


def _run_creat_account(
    settings: Settings,
    user: NewUser,
    mock_web: AsyncMock,
    mock_users_api: AsyncMock | None = None,
) -> NewUser:
    if mock_users_api is None:
        mock_users_api = _mock_users_api()
    mock_cls = MagicMock(return_value=mock_web)
    mock_gateway_cls = MagicMock(return_value=mock_cls)

    with (
        patch("ui.controllers.UsersAPI", return_value=mock_users_api),
        patch("ui.controllers.DomServerWebGateway", mock_gateway_cls),
    ):
        controller = MainController(settings)
        return asyncio.run(controller.creat_account(user))


def test_creat_account_rejects_short_password_before_any_write() -> None:
    settings = make_settings(min_password_length=10)
    user = NewUser(
        username="shortpw_coder",
        name="shortpw_School",
        email="shortpw@example.com",  # type: ignore[arg-type]
        password="123456",
    )
    mock_web = _mock_web()

    with pytest.raises(InvalidPasswordError) as exc_info:
        _run_creat_account(settings, user, mock_web)

    message = str(exc_info.value)
    assert "至少需 10 個位元組" in message
    assert "目前為 6 個位元組" in message
    mock_web.login.assert_not_awaited()
    mock_web.create_team_and_user.assert_not_awaited()
    mock_web.set_user_password.assert_not_awaited()


def test_creat_account_accepts_password_at_minimum_length() -> None:
    settings = make_settings(min_password_length=10)
    user = NewUser(
        username="exactpw_coder",
        name="exactpw_School",
        email="exactpw@example.com",  # type: ignore[arg-type]
        password="abcdefghij",
    )
    mock_web = _mock_web()

    result = _run_creat_account(settings, user, mock_web)

    assert result == user
    mock_web.set_user_password.assert_awaited_once_with(
        "user_10",
        "abcdefghij",
        [3],
    )


def test_creat_account_accepts_multibyte_password_meeting_byte_minimum() -> None:
    """DOMjudge measures with PHP strlen(), i.e. UTF-8 bytes.

    4 CJK characters are 4 Python characters but 12 bytes, which DOMjudge
    accepts. Counting characters here would reject a valid password.
    """
    settings = make_settings(min_password_length=10)
    user = NewUser(
        username="cjkpw_coder",
        name="cjkpw_School",
        email="cjkpw@example.com",  # type: ignore[arg-type]
        password="密碼測試",
    )
    mock_web = _mock_web()

    result = _run_creat_account(settings, user, mock_web)

    assert result == user
    mock_web.set_user_password.assert_awaited_once_with(
        "user_10",
        "密碼測試",
        [3],
    )


def test_creat_account_rejects_multibyte_password_below_byte_minimum() -> None:
    """3 CJK characters are 9 bytes, which DOMjudge rejects."""
    settings = make_settings(min_password_length=10)
    user = NewUser(
        username="cjk3_coder",
        name="cjk3_School",
        email="cjk3@example.com",  # type: ignore[arg-type]
        password="密碼測",
    )
    mock_web = _mock_web()

    with pytest.raises(InvalidPasswordError):
        _run_creat_account(settings, user, mock_web)

    mock_web.create_team_and_user.assert_not_awaited()


def test_creat_account_rolls_back_user_and_team_when_password_fails() -> None:
    settings = make_settings(min_password_length=10)
    user = NewUser(
        username="rollback_coder",
        name="rollback_School",
        email="rollback@example.com",  # type: ignore[arg-type]
        password="abcdefghij",
    )
    mock_web = _mock_web(
        set_user_password=AsyncMock(
            side_effect=AssertionError("User set password fail. user_10")
        )
    )

    with pytest.raises(AccountCreationError) as exc_info:
        _run_creat_account(settings, user, mock_web)

    message = str(exc_info.value)
    assert "rollback_coder" in message
    # The raw exception can embed the internal DOMjudge URL, so it must not be
    # echoed to an anonymous applicant.
    assert "User set password fail. user_10" not in message
    mock_web.delete_users.assert_awaited_once_with(include=["rollback_coder"])
    mock_web.delete_teams.assert_awaited_once_with(include=["team_10"])


def test_creat_account_reports_orphan_when_rollback_fails() -> None:
    settings = make_settings(min_password_length=10)
    user = NewUser(
        username="orphan_coder",
        name="orphan_School",
        email="orphan@example.com",  # type: ignore[arg-type]
        password="abcdefghij",
    )
    mock_web = _mock_web(
        set_user_password=AsyncMock(side_effect=AssertionError("nope")),
        delete_users=AsyncMock(side_effect=RuntimeError("delete users failed")),
    )

    with pytest.raises(AccountCreationError) as exc_info:
        _run_creat_account(settings, user, mock_web)

    message = str(exc_info.value)
    assert "orphan_coder" in message
    assert "使用者" in message
    assert "delete users failed" not in message
    mock_web.delete_users.assert_awaited_once_with(include=["orphan_coder"])
    mock_web.delete_teams.assert_awaited_once_with(include=["team_10"])


def test_rollback_reports_orphan_when_user_survives_deletion() -> None:
    """The delete helpers silently no-op when nothing matches.

    A surviving user must be reported, not assumed deleted just because the
    delete call raised nothing.
    """
    settings = make_settings(min_password_length=10)
    user = NewUser(
        username="survivor_coder",
        name="survivor_School",
        email="survivor@example.com",  # type: ignore[arg-type]
        password="abcdefghij",
    )
    mock_web = _mock_web(
        set_user_password=AsyncMock(side_effect=AssertionError("nope")),
    )
    surviving = MagicMock()
    surviving.username = "survivor_coder"
    mock_users_api = _mock_users_api()
    # First call is the duplicate pre-check (empty), later calls are the
    # post-rollback verification, which must still see the user.
    mock_users_api.all_users.side_effect = [[], [surviving]]

    with pytest.raises(AccountCreationError) as exc_info:
        _run_creat_account(settings, user, mock_web, mock_users_api)

    message = str(exc_info.value)
    assert "survivor_coder" in message
    assert "使用者" in message
    assert "未建立帳號" not in message


def test_rollback_reports_success_when_user_is_gone() -> None:
    settings = make_settings(min_password_length=10)
    user = NewUser(
        username="cleaned_coder",
        name="cleaned_School",
        email="cleaned@example.com",  # type: ignore[arg-type]
        password="abcdefghij",
    )
    mock_web = _mock_web(
        set_user_password=AsyncMock(side_effect=AssertionError("nope")),
    )

    with pytest.raises(AccountCreationError) as exc_info:
        _run_creat_account(settings, user, mock_web)

    assert "未建立帳號" in str(exc_info.value)


def test_duplicate_username_reported_before_password_policy() -> None:
    """A duplicate submission must keep reporting the duplicate.

    The password check runs before any write, but after the read-only duplicate
    lookup, so a duplicate account with a short password still reports 帳號重複.
    """
    settings = make_settings(min_password_length=10)
    user = NewUser(
        username="taken_coder",
        name="taken_School",
        email="taken@example.com",  # type: ignore[arg-type]
        password="123",  # also too short
    )
    existing = MagicMock()
    existing.username = "taken_coder"
    existing.name = "Other School"
    mock_users_api = _mock_users_api()
    mock_users_api.all_users.return_value = [existing]
    mock_web = _mock_web()

    with (
        patch("ui.controllers.UsersAPI", return_value=mock_users_api),
        patch("ui.controllers.DomServerWebGateway", MagicMock(return_value=mock_web)),
    ):
        controller = MainController(settings)
        with pytest.raises(DuplicatedError) as exc_info:
            asyncio.run(controller.creat_account(user))

    assert "帳號重複" in str(exc_info.value)
    mock_web.create_team_and_user.assert_not_awaited()


def test_password_policy_measured_in_utf8_bytes() -> None:
    assert password_byte_length("密碼測試") == 12
    assert password_byte_length("123456") == 6
    assert password_byte_length("密碼測試") > len("密碼測試")


def test_differing_only_in_case_username_is_a_clean_duplicate() -> None:
    """DOMjudge's username column is case-insensitive.

    Submitting only a case variant used to pass the pre-check and then trip
    DOMjudge's unique constraint, surfacing a raw 500 to the applicant.
    """
    settings = make_settings(min_password_length=10)
    user = NewUser(
        username="CaseCoder",
        name="case_School",
        email="case@example.com",  # type: ignore[arg-type]
        password="abcdefghij",
    )
    existing = MagicMock()
    existing.username = "casecoder"
    existing.name = "Other School"
    mock_users_api = _mock_users_api()
    mock_users_api.all_users.return_value = [existing]
    mock_web = _mock_web()

    with (
        patch("ui.controllers.UsersAPI", return_value=mock_users_api),
        patch("ui.controllers.DomServerWebGateway", MagicMock(return_value=mock_web)),
    ):
        controller = MainController(settings)
        with pytest.raises(DuplicatedError) as exc_info:
            asyncio.run(controller.creat_account(user))

    assert "帳號重複" in str(exc_info.value)
    mock_web.create_team_and_user.assert_not_awaited()


def test_server_reported_minimum_overrides_a_lower_configured_value() -> None:
    """An operator setting below the server's real floor must not be trusted.

    Otherwise the form advertises a policy DOMjudge rejects, producing a
    create-then-rollback round trip for a password the form said was fine.
    """
    settings = make_settings(min_password_length=4)
    user = NewUser(
        username="detect_coder",
        name="detect_School",
        email="detect@example.com",  # type: ignore[arg-type]
        password="123456",  # 6 bytes: passes the configured 4, fails the server's 10
    )
    mock_web = _mock_web(get_min_password_length=AsyncMock(return_value=10))

    with pytest.raises(InvalidPasswordError) as exc_info:
        _run_creat_account(settings, user, mock_web)

    assert "10" in str(exc_info.value)
    mock_web.create_team_and_user.assert_not_awaited()


def test_server_reported_minimum_is_consulted_before_writing() -> None:
    settings = make_settings(min_password_length=0)
    user = NewUser(
        username="detect_ok",
        name="detect_School",
        email="detect2@example.com",  # type: ignore[arg-type]
        password="abcdefghij",
    )
    mock_web = _mock_web(get_min_password_length=AsyncMock(return_value=10))

    result = _run_creat_account(settings, user, mock_web)

    assert result == user
    mock_web.get_min_password_length.assert_awaited_once()


def test_rejection_reason_surfaces_domjudge_feedback_only() -> None:
    """DOMjudge's own validation text is shown; transport text never is."""

    class FakeFormSubmitError(Exception):
        def __init__(self, details: list[str]) -> None:
            self.details = details
            super().__init__("User set password fail. 7")

    assert (
        _rejection_reason(FakeFormSubmitError(["Password should be 10+ chars."]))
        == "Password should be 10+ chars."
    )
    # No details attribute, or empty details, yields nothing. This keeps a raw
    # transport message (which can embed an internal URL) out of the UI.
    assert _rejection_reason(RuntimeError("server 500 at http://internal.host")) is None
    assert _rejection_reason(FakeFormSubmitError([])) is None


def test_affiliation_created_for_the_signup_is_rolled_back() -> None:
    """An affiliation created for the signup must not outlive a failed signup."""
    settings = make_settings(min_password_length=10, affiliation_id=None)
    user = NewUser(
        username="affil_coder",
        name="affil_School",
        email="affil@example.com",  # type: ignore[arg-type]
        password="abcdefghij",
        affiliation="Test University",
    )
    created = MagicMock()
    created.id = "42"
    mock_web = _mock_web(
        get_affiliation=AsyncMock(return_value=None),
        create_affiliation=AsyncMock(return_value=created),
        set_user_password=AsyncMock(side_effect=AssertionError("nope")),
        delete_affiliation=AsyncMock(return_value=1),
    )

    with pytest.raises(AccountCreationError):
        _run_creat_account(settings, user, mock_web)

    mock_web.delete_affiliation.assert_awaited_once_with("42")


def test_pre_existing_affiliation_is_not_rolled_back() -> None:
    """Only an affiliation this call created may be deleted."""
    settings = make_settings(min_password_length=10, affiliation_id=None)
    user = NewUser(
        username="reuse_coder",
        name="reuse_School",
        email="reuse@example.com",  # type: ignore[arg-type]
        password="abcdefghij",
        affiliation="Existing University",
    )
    existing = MagicMock()
    existing.id = "7"
    mock_web = _mock_web(
        get_affiliation=AsyncMock(return_value=existing),
        set_user_password=AsyncMock(side_effect=AssertionError("nope")),
        delete_affiliation=AsyncMock(return_value=1),
    )

    with pytest.raises(AccountCreationError):
        _run_creat_account(settings, user, mock_web)

    mock_web.delete_affiliation.assert_not_awaited()


def test_affiliation_orphan_reported_when_library_cannot_delete_it() -> None:
    """Without delete_affiliation the affiliation cannot be removed.

    That is a real orphan, so it must be reported instead of the signup being
    claimed as cleanly rolled back.
    """
    settings = make_settings(min_password_length=10, affiliation_id=None)
    user = NewUser(
        username="noaff_coder",
        name="noaff_School",
        email="noaff@example.com",  # type: ignore[arg-type]
        password="abcdefghij",
        affiliation="Test University",
    )
    created = MagicMock()
    created.id = "42"
    mock_web = _mock_web(
        get_affiliation=AsyncMock(return_value=None),
        create_affiliation=AsyncMock(return_value=created),
        set_user_password=AsyncMock(side_effect=AssertionError("nope")),
    )
    # Simulate the shipping 0.5.0 library, which has no delete_affiliation.
    del mock_web.delete_affiliation

    with pytest.raises(AccountCreationError) as exc_info:
        _run_creat_account(settings, user, mock_web)

    message = str(exc_info.value)
    assert "學校" in message
    assert "未建立帳號" not in message


def test_missing_detection_on_older_library_falls_back_to_configured_value() -> None:
    """On domjudge-tool-cli 0.5.0 the gateway has no detection method.

    The configured/derived value must still apply and the signup must proceed.
    """
    settings = make_settings(min_password_length=10)
    user = NewUser(
        username="nofallback_coder",
        name="nofallback_School",
        email="nofallback@example.com",  # type: ignore[arg-type]
        password="123456",
    )
    mock_web = _mock_web()
    del mock_web.get_min_password_length

    with pytest.raises(InvalidPasswordError):
        _run_creat_account(settings, user, mock_web)

    mock_web.create_team_and_user.assert_not_awaited()


def test_detection_returning_a_non_integer_is_ignored() -> None:
    """An unexpected return value must not be compared against a length."""
    settings = make_settings(min_password_length=10)
    user = NewUser(
        username="weirddetect",
        name="weird_School",
        email="weird@example.com",  # type: ignore[arg-type]
        password="abcdefghij",
    )
    mock_web = _mock_web(get_min_password_length=AsyncMock(return_value="ten"))

    result = _run_creat_account(settings, user, mock_web)

    assert result == user
    mock_web.set_user_password.assert_awaited_once()


class FakeClock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _new_user(username: str, password: str = "abcdefghij") -> NewUser:
    return NewUser(
        username=username,
        name=f"{username}_School",
        email=f"{username}@example.com",  # type: ignore[arg-type]
        password=password,
    )


def _submit(
    settings: Settings,
    user: NewUser,
    mock_web: AsyncMock,
    clock: FakeClock,
    mock_users_api: AsyncMock | None = None,
) -> NewUser:
    """One signup with a fresh controller, as every Streamlit rerun creates."""
    if mock_users_api is None:
        mock_users_api = _mock_users_api()
    mock_gateway_cls = MagicMock(return_value=MagicMock(return_value=mock_web))

    with (
        patch("ui.controllers.UsersAPI", return_value=mock_users_api),
        patch("ui.controllers.DomServerWebGateway", mock_gateway_cls),
    ):
        controller = MainController(settings, clock=clock)
        return asyncio.run(controller.creat_account(user))


def test_server_minimum_is_read_once_across_submissions() -> None:
    settings = make_settings(min_password_length=0)
    clock = FakeClock()
    mock_web = _mock_web(get_min_password_length=AsyncMock(return_value=10))

    _submit(settings, _new_user("first_coder"), mock_web, clock)
    clock.now += POLICY_TTL_SECONDS - 1
    _submit(settings, _new_user("second_coder"), mock_web, clock)

    mock_web.get_min_password_length.assert_awaited_once()
    assert settings.effective_min_password_length == 10


def test_server_minimum_is_read_again_after_the_ttl() -> None:
    settings = make_settings(min_password_length=0)
    clock = FakeClock()
    mock_web = _mock_web(get_min_password_length=AsyncMock(return_value=10))

    _submit(settings, _new_user("first_coder"), mock_web, clock)
    clock.now += POLICY_TTL_SECONDS
    _submit(settings, _new_user("second_coder"), mock_web, clock)

    assert mock_web.get_min_password_length.await_count == 2


def test_failed_read_is_not_cached_and_signup_continues() -> None:
    settings = make_settings(min_password_length=0)
    clock = FakeClock()
    mock_web = _mock_web(get_min_password_length=AsyncMock(return_value=None))

    first = _submit(settings, _new_user("first_coder"), mock_web, clock)
    second = _submit(settings, _new_user("second_coder"), mock_web, clock)

    assert first.username == "first_coder"
    assert second.username == "second_coder"
    assert mock_web.get_min_password_length.await_count == 2
    assert settings.detected_min_password_length is None


def test_read_error_on_submit_does_not_block_signup() -> None:
    settings = make_settings(min_password_length=0)
    mock_web = _mock_web(
        get_min_password_length=AsyncMock(side_effect=RuntimeError("boom"))
    )

    result = _submit(settings, _new_user("error_coder"), mock_web, FakeClock())

    assert result.username == "error_coder"
    mock_web.set_user_password.assert_awaited_once()


def test_expired_stale_value_is_replaced_before_any_write() -> None:
    """A lower, expired cached value must not let a short password through.

    The cached 4 allows a 6-byte password at the first check. The server now
    requires 10, so the refresh after login must reject it before the team and
    user are created.
    """
    settings = make_settings(min_password_length=0)
    clock = FakeClock()
    settings.record_detected_min_password_length(4, clock.now)
    clock.now += POLICY_TTL_SECONDS
    mock_web = _mock_web(get_min_password_length=AsyncMock(return_value=10))

    with pytest.raises(InvalidPasswordError):
        _submit(settings, _new_user("stale_coder", password="123456"), mock_web, clock)

    mock_web.create_team_and_user.assert_not_awaited()
    mock_web.set_user_password.assert_not_awaited()
    assert settings.detected_min_password_length == 10


def test_fresh_cached_value_rejects_without_login_or_server_read() -> None:
    settings = make_settings(min_password_length=0)
    clock = FakeClock()
    settings.record_detected_min_password_length(10, clock.now)
    mock_web = _mock_web(get_min_password_length=AsyncMock(return_value=10))

    with pytest.raises(InvalidPasswordError):
        _submit(settings, _new_user("short_coder", password="123456"), mock_web, clock)

    mock_web.login.assert_not_awaited()
    mock_web.get_min_password_length.assert_not_awaited()


def test_policy_refresh_is_due_only_after_a_successful_read_expires() -> None:
    settings = make_settings()
    assert settings.policy_refresh_due(5.0) is True

    settings.record_detected_min_password_length(10, 5.0)
    assert settings.policy_refresh_due(5.0 + POLICY_TTL_SECONDS - 0.1) is False
    assert settings.policy_refresh_due(5.0 + POLICY_TTL_SECONDS) is True


def _existing_user(username: str, name: str) -> MagicMock:
    existing = MagicMock()
    existing.username = username
    existing.name = name
    return existing


def _users_api_with(*existing: MagicMock) -> AsyncMock:
    mock_users_api = _mock_users_api()
    mock_users_api.all_users.return_value = list(existing)
    return mock_users_api


def test_username_contained_in_an_existing_one_is_not_a_duplicate() -> None:
    settings = make_settings(min_password_length=0)
    users_api = _users_api_with(_existing_user("amy2", "Other_School_amy2"))

    result = _submit(
        settings, _new_user("amy"), _mock_web(), FakeClock(), mock_users_api=users_api
    )

    assert result.username == "amy"


def test_username_containing_an_existing_one_is_not_a_duplicate() -> None:
    settings = make_settings(min_password_length=0)
    users_api = _users_api_with(_existing_user("amy", "Other_School_amy"))

    result = _submit(
        settings, _new_user("amy2"), _mock_web(), FakeClock(), mock_users_api=users_api
    )

    assert result.username == "amy2"


def test_identical_username_in_another_case_is_still_a_duplicate() -> None:
    settings = make_settings(min_password_length=0)
    users_api = _users_api_with(_existing_user("amy", "Other_School_amy"))
    mock_web = _mock_web()

    with pytest.raises(DuplicatedError) as exc_info:
        _submit(
            settings,
            _new_user("AMY"),
            mock_web,
            FakeClock(),
            mock_users_api=users_api,
        )

    assert "帳號重複" in str(exc_info.value)
    mock_web.create_team_and_user.assert_not_awaited()


def test_display_name_is_compared_exactly() -> None:
    settings = make_settings(min_password_length=0)
    user = _new_user("amy")  # display name "amy_School"
    near = _users_api_with(_existing_user("other", "amy_School2"))
    exact = _users_api_with(_existing_user("other", "amy_School"))

    assert (
        _submit(settings, user, _mock_web(), FakeClock(), mock_users_api=near) == user
    )
    with pytest.raises(DuplicatedError) as exc_info:
        _submit(settings, user, _mock_web(), FakeClock(), mock_users_api=exact)

    assert "名稱重複" in str(exc_info.value)
