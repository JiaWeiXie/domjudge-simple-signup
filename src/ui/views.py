import streamlit as st
from pydantic import ValidationError

from core.config import Settings
from ui.controllers import DuplicatedError, MainController
from ui.models import NewUser


class MainInterface:
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
            formdata = NewUser(
                username=username if username else None,
                email=email if email else None,
                password=password if password else None,
                name=f"{school_name}_{username}" if school_name else None,
            )
            account = await self.controller.creat_account(formdata)
            await self.controller.log_to_googleform(account)
            st.success("新增成功")
            st.write(
                account.dict(
                    include={"username", "email", "password", "name"},
                ),
            )
        except ValidationError as e:
            error_messages = {}
            for error in e.errors():
                for field in error["loc"]:
                    if field in field_mapping:
                        field_name = field_mapping[field]
                        error_messages[field_name] = error["msg"]
            st.write(error_messages)
        except DuplicatedError as e:
            st.write(
                f"<div style='color:red;'>{e}</div><br/>",
                unsafe_allow_html=True,
            )

    async def make_form(self):
        with st.form("signup_form"):
            email_val = st.text_input("email*", autocomplete="email")
            username_val = st.text_input(
                "帳號*",
                max_chars=16,
                autocomplete="username",
            )
            st.markdown("系統顯示名稱將會是`{學校名稱}_{帳號}`")
            password_val = st.text_input(
                "密碼*",
                type="password",
                autocomplete="new-password",
            )
            confirm_password_val = st.text_input(
                "確認密碼*",
                type="password",
                autocomplete="new-password",
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
                    st.write(
                        "<div style='color:red;'>密碼與確認密碼不符!</div><br/>",
                        unsafe_allow_html=True,
                    )

    def __init__(self, settings: Settings):
        self.settings = settings
        self.controller = MainController(settings)

    async def render(self):
        text = "DOMjudge 申請帳號表單:"
        st.title(text)
        st.text(self.settings.host)
        await self.make_form()
