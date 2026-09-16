from typing import Any

import streamlit as st
from domjudge_tool_cli.services.web import DomServerWebGateway
from pydantic import ValidationError

from core.config import Settings
from ui.controllers import MainController, SignupError
from ui.models import NewUser, normalize_username


class MainInterface:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.controller = MainController(settings)

    async def submit_form(
        self,
        username: str,
        email: str,
        password: str,
        school_name: str,
    ) -> None:
        field_mapping = {
            "username": "帳號",
            "email": "email",
            "password": "密碼",
            "name": "學校名稱",
        }
        try:
            normalized_username = normalize_username(username)
            formdata = NewUser.model_validate(
                {
                    "username": normalized_username or None,
                    "email": email or None,
                    "password": password or None,
                    "name": f"{school_name}_{normalized_username}"
                    if school_name
                    else None,
                }
            )
            account = await self.controller.creat_account(formdata)
            await self.controller.log_to_googleform(account)
            st.success("新增成功")
            st.write(
                account.model_dump(
                    include={"username", "email", "name"},
                )
            )
        except ValidationError as e:
            error_messages: dict[str, Any] = {}
            for error in e.errors():
                for field in error["loc"]:
                    if field in field_mapping:
                        error_messages[field_mapping[field]] = error["msg"]
            st.write(error_messages)
        except SignupError as e:
            st.error(str(e))

    async def make_form(self) -> None:
        with st.form("signup_form"):
            email_val = st.text_input("email*", autocomplete="email")
            username_val = st.text_input(
                "帳號*",
                max_chars=16,
                autocomplete="username",
            )
            st.markdown("系統顯示名稱將會是`{學校名稱}_{帳號}`")
            min_password_length = self.settings.effective_min_password_length
            password_help_msg = (
                f"至少 {min_password_length} 個位元組"
                f"(英數各算 1 個, 中文每字通常算 3 個)。"
            )
            password_val = st.text_input(
                "密碼*",
                type="password",
                autocomplete="new-password",
                help=password_help_msg,
            )
            confirm_password_val = st.text_input(
                "確認密碼*",
                type="password",
                autocomplete="new-password",
                help=password_help_msg,
            )
            school_name_help_msg = "ex: 國立臺北商業大學，請填寫`北商大`。"
            school_name_val = st.text_input(
                "學校名稱*",
                max_chars=32,
                help=school_name_help_msg,
            )
            st.markdown(school_name_help_msg)

            submitted = st.form_submit_button("送出")
            if submitted:
                if password_val == confirm_password_val:
                    await self.submit_form(
                        username=username_val,
                        email=email_val,
                        password=password_val,
                        school_name=school_name_val,
                    )
                else:
                    st.error("密碼與確認密碼不符!")

    async def render(self) -> None:
        text = "DOMjudge 申請帳號表單:"
        st.title(text)
        st.text(str(self.settings.host))
        gateway_cls = DomServerWebGateway(self.settings.version)
        st.caption(
            f"DOMjudge {self.settings.version} ({gateway_cls.__module__}.{gateway_cls.__name__})"
        )
        await self.ensure_password_policy()
        await self.make_form()

    async def ensure_password_policy(self) -> None:
        """Learn the server's password policy once per session.

        The form's help text and the enforcement both read
        effective_min_password_length, so they agree only if the server value is
        known before the form renders. The session flag records that the probe
        was attempted, so a server that cannot report a value (an older
        domjudge-tool-cli) is not re-probed on every rerun.
        """
        if st.session_state.get("password_policy_loaded"):
            return
        st.session_state["password_policy_loaded"] = True
        await self.controller.refresh_min_password_length()
