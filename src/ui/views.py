from typing import Any

import streamlit as st
from pydantic import ValidationError

from core.config import Settings
from ui.controllers import DuplicatedError, MainController
from ui.models import NewUser


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
            formdata = NewUser.model_validate(
                {
                    "username": username or None,
                    "name": school_name or None,
                    "email": email or None,
                    "password": password or None,
                }
            )
            account = await self.controller.creat_account(formdata)
            await self.controller.log_to_googleform(account)
            st.success("新增成功")
            st.write(
                account.model_dump(
                    include={
                        "username",
                        "name",
                        "email",
                    }
                )
            )
        except ValidationError as e:
            error_messages: dict[str, Any] = {}
            for error in e.errors():
                loc = error.get("loc", ())
                first_loc = str(loc[0]) if loc else ""
                key = field_mapping.get(first_loc, first_loc)
                error_messages[key] = error["msg"]

            st.write(error_messages)
        except DuplicatedError as e:
            st.write(
                {
                    "message": e.message,
                }
            )

    async def make_form(self) -> None:
        with st.form("signup_form"):
            email_val = st.text_input("email*", autocomplete="email")
            school_name_val = st.text_input("學校名稱*")
            username_val = st.text_input("自訂帳號*")
            password_val = st.text_input(
                "自訂密碼*",
                type="password",
                autocomplete="new-password",
            )
            confirm_password_val = st.text_input(
                "確認密碼*",
                type="password",
                autocomplete="new-password",
            )

            submit_button = st.form_submit_button("送出")

            if submit_button:
                if password_val != confirm_password_val:
                    st.error("密碼與確認密碼不符!")
                else:
                    await self.submit_form(
                        username=username_val,
                        email=email_val,
                        password=password_val,
                        school_name=school_name_val,
                    )

    async def render(self) -> None:
        text = "DOMjudge 申請帳號表單:"
        st.title(text)
        st.text(str(self.settings.host))
        await self.make_form()
