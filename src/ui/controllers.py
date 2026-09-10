from typing import Any

import httpx
from domjudge_tool_cli.models import CreateUser
from domjudge_tool_cli.services.api.v4 import UsersAPI
from domjudge_tool_cli.services.web import DomServerWebGateway

from core.config import Settings
from ui.models import NewUser

GOOGLEFORM_URL = "https://docs.google.com/forms/d/e/%s/formResponse"
GOOGLEFORM_FIELDS = {
    "username": "entry.2005418205",
    "name": "entry.533178960",
    "email": "emailAddress",
    "school_code": "entry.55480983",
}


class DuplicatedError(Exception):
    def __init__(self, message: str, *args: Any) -> None:
        self.message = message
        super().__init__(*args)

    def __str__(self) -> str:
        return self.message


class MainController:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def log_to_googleform(self, account: NewUser) -> bool:
        google_form_id = self.settings.google_form_id
        if not google_form_id:
            return False

        account_dict = account.model_dump()
        formdata: dict[str, Any] = {
            GOOGLEFORM_FIELDS[k]: account_dict[k]
            for k in ["username", "name", "email"]
            if k in account_dict
        }
        formdata[GOOGLEFORM_FIELDS["school_code"]] = "streamlit-form"
        url = GOOGLEFORM_URL % google_form_id
        async with httpx.AsyncClient() as client:
            r = await client.post(
                url,
                data=formdata,
                follow_redirects=True,
            )
            if r.status_code == 200:
                return True
        return False

    async def creat_account(self, formdata: NewUser) -> NewUser:
        category_id = self.settings.category_id
        if category_id is None:
            raise ValueError("CATEGORY_ID is required to create an account.")

        user_roles = self.settings.user_roles or []

        async with UsersAPI(**self.settings.api_params) as api:
            users = await api.all_users()

        duplicated_name_list = [it.name for it in users if formdata.name in it.name]
        duplicated_username_list = [
            it.username for it in users if formdata.username in it.username
        ]

        if duplicated_username_list:
            raise DuplicatedError(f"帳號重複, {formdata.username}")

        if duplicated_name_list:
            raise DuplicatedError(f"名稱重複, {formdata.name}")

        DomServerWeb = DomServerWebGateway(self.settings.version)
        async with DomServerWeb(**self.settings.api_params) as web:
            await web.login()

            affiliation_name = formdata.name
            affiliation = await web.get_affiliation(affiliation_name)

            if affiliation and affiliation.id:
                affiliation_id = (
                    int(affiliation.id) if affiliation.id.isdigit() else None
                )
            else:
                country = self.settings.affiliation_country or "TWN"
                affiliation = await web.create_affiliation(
                    affiliation_name,
                    affiliation_name,
                    country,
                )
                affiliation_id = (
                    int(affiliation.id)
                    if affiliation and affiliation.id and affiliation.id.isdigit()
                    else None
                )

            if affiliation_id is None:
                raise ValueError("AFFILIATION_ID is required to create an account.")

            create_user_data = CreateUser.model_validate(formdata.model_dump())
            team_id, user_id = await web.create_team_and_user(
                create_user_data,
                category_id,
                affiliation_id,
            )

            await web.set_user_password(
                user_id,
                formdata.password,
                user_roles,
            )

            return formdata
