from typing import Any

import httpx
from domjudge_tool_cli.models import CreateUser
from domjudge_tool_cli.services.api.v4 import UsersAPI
from domjudge_tool_cli.services.web import DomServerWebGateway

from core.config import GOOGLEFORM_ID, Settings
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
        if not GOOGLEFORM_ID:
            return False

        formdata = {
            GOOGLEFORM_FIELDS[k]: v
            for k, v in account.dict().items()
            if k in GOOGLEFORM_FIELDS
        }
        formdata[GOOGLEFORM_FIELDS["school_code"]] = "streamlit-form"
        url = GOOGLEFORM_URL % GOOGLEFORM_ID
        async with httpx.AsyncClient() as client:
            r = await client.post(
                url,
                data=formdata,
                allow_redirects=True,
            )
            if r.status_code == 200:
                return True
        return False

    async def creat_account(self, formdata: NewUser) -> NewUser:
        category_id = self.settings.category_id
        user_roles = self.settings.user_roles
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
            if not formdata.affiliation:
                affiliation_id = self.settings.affiliation_id
            elif formdata.affiliation:
                affiliation = await web.get_affiliation(formdata.affiliation)

                if affiliation:
                    affiliation_id = affiliation.id
                else:
                    name = formdata.affiliation
                    affiliation = await web.create_affiliation(
                        name,
                        name,
                        self.settings.affiliation_country,
                    )
                    affiliation_id = affiliation.id

            team_id, user_id = await web.create_team_and_user(
                CreateUser(**formdata.dict()),
                category_id,
                affiliation_id,
            )

            await web.set_user_password(user_id, formdata.password, user_roles)

            return formdata
