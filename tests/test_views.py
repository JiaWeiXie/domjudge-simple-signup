import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

from core.config import Settings
from ui.views import MainInterface


def make_settings(**kwargs: Any) -> Settings:
    defaults: dict[str, Any] = {
        "host": "https://domserver.example.test",
        "username": "api_admin",
        "password": "api_password",
        "category_id": 1,
        "affiliation_id": 2,
        "affiliation_country": "TWN",
        "user_roles": [3],
        "version": "8.3.1",
        "api_version": "v4",
        "min_password_length": 4,
    }
    defaults.update(kwargs)
    return Settings(**defaults)  # type: ignore[arg-type]


def render(settings: Settings) -> tuple[MagicMock, list[dict[str, Any]]]:
    """Render once with Streamlit mocked; return it and any gateway instances."""
    created: list[dict[str, Any]] = []

    class Gateway:
        def __init__(self, **kwargs: Any) -> None:
            created.append(kwargs)

    factory = MagicMock(return_value=Gateway)
    with (
        patch("ui.views.DomServerWebGateway", factory),
        patch("ui.controllers.DomServerWebGateway", factory),
        patch("ui.views.st") as st,
    ):
        st.form_submit_button.return_value = False
        asyncio.run(MainInterface(settings).render())
    return st, created


def password_help_text(st: MagicMock) -> str:
    for call in st.text_input.call_args_list:
        if call.kwargs.get("type") == "password":
            return str(call.kwargs["help"])
    raise AssertionError("password field was not rendered")


def test_render_never_instantiates_a_gateway_so_it_cannot_log_in() -> None:
    st, created = render(make_settings())

    assert created == []
    st.form.assert_called_once()


def test_repeated_renders_and_sessions_never_contact_domjudge() -> None:
    settings = make_settings()
    created_total: list[dict[str, Any]] = []

    for _ in range(5):
        _, created = render(settings)
        created_total.extend(created)

    assert created_total == []


def test_help_text_follows_the_configured_minimum_until_a_submit_reads() -> None:
    settings = make_settings(min_password_length=4)

    st, _ = render(settings)
    assert "至少 4 個位元組" in password_help_text(st)

    settings.record_detected_min_password_length(10, 0.0)
    st, _ = render(settings)
    assert "至少 10 個位元組" in password_help_text(st)
