import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from domjudge_tool_cli.models import CreateUser
from domjudge_tool_cli.services.api.v4 import UsersAPI
from domjudge_tool_cli.services.web import DomServerWebGateway
from domjudge_tool_cli.services.web.base import BaseDomServerWeb

from core.config import Settings
from ui.models import NewUser

logger = logging.getLogger(__name__)

GOOGLEFORM_URL = "https://docs.google.com/forms/d/e/%s/formResponse"
GOOGLEFORM_FIELDS = {
    "username": "entry.2005418205",
    "name": "entry.533178960",
    "email": "emailAddress",
    "school_code": "entry.55480983",
}


def _rejection_reason(exc: BaseException) -> str | None:
    """The validation message DOMjudge rendered, if the library reported one.

    Only DOMjudge's own feedback is returned. Raw transport/HTTP text is never
    included because it can carry internal URLs, and it is logged instead.
    domjudge-tool-cli gained this detail after 0.5.0, so its absence is normal.
    """
    details = getattr(exc, "details", None)
    if not isinstance(details, list) or not details:
        return None
    messages = [d for d in details if isinstance(d, str) and d]
    return "; ".join(messages) if messages else None


async def _server_min_password_length(web: BaseDomServerWeb) -> int | None:
    """The minimum password length the server itself reports, when available.

    The gateway knows this only in newer domjudge-tool-cli releases, so an
    older one simply yields None and the configured default is used.
    """
    getter = getattr(web, "get_min_password_length", None)
    if getter is None:
        return None
    try:
        detected = await getter()
    except Exception:
        logger.exception("Failed to read the server's minimum password length")
        return None
    if isinstance(detected, bool) or not isinstance(detected, int):
        return None
    return detected


class SignupError(Exception):
    """A signup failure whose message is safe to show the applicant."""


def password_byte_length(password: str) -> int:
    """Length as DOMjudge measures it: PHP strlen(), i.e. UTF-8 bytes.

    DOMjudge compares `strlen($plainPassword)` against its configured minimum,
    so multi-byte characters count once per UTF-8 byte. Measuring characters
    instead would reject passwords DOMjudge accepts (4 CJK characters = 12
    bytes) and accept passwords it rejects.
    """
    return len(password.encode("utf-8"))


class DuplicatedError(SignupError):
    """The requested username or display name already exists."""


class InvalidPasswordError(SignupError):
    """The password does not satisfy the target DOMjudge policy."""


class AccountCreationError(SignupError):
    """DOMjudge rejected the account after the team and user already existed."""


class MainController:
    def __init__(
        self,
        settings: Settings,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.settings = settings
        self._clock = clock

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

        # DOMjudge stores usernames in a case-insensitive collation
        # (utf8mb4_unicode_ci), so a differing only-in-case name passes this
        # check but violates its unique constraint and returns a 500. Compare
        # casefolded to keep the pre-check in step with the server.
        username_key = formdata.username.casefold()
        duplicated_username_list = [
            it.username for it in users if it.username.casefold() == username_key
        ]
        duplicated_name_list = [it.name for it in users if it.name == formdata.name]

        if duplicated_username_list:
            raise DuplicatedError(f"帳號重複, {formdata.username}")

        if duplicated_name_list:
            raise DuplicatedError(f"名稱重複, {formdata.name}")

        self._check_password_policy(formdata.password)

        DomServerWeb = DomServerWebGateway(self.settings.version)
        async with DomServerWeb(**self.settings.api_params) as web:
            await web.login()

            # Read the server's own minimum when the shared value has expired
            # and enforce it before any write, so an operator setting below the
            # real floor cannot cause a create-then-rollback round trip. The
            # login above happens for this submission anyway; page renders
            # never log in. A failed read is not cached and falls back to the
            # value already checked.
            now = self._clock()
            if self.settings.policy_refresh_due(now):
                detected = await _server_min_password_length(web)
                if detected is not None:
                    self.settings.record_detected_min_password_length(detected, now)
                    self._check_password_policy(formdata.password)

            created_affiliation_id: str | None = None
            if formdata.affiliation:
                affiliation = await web.get_affiliation(formdata.affiliation)
                if affiliation and affiliation.id and affiliation.id.isdigit():
                    affiliation_id = int(affiliation.id)
                else:
                    affiliation = await web.create_affiliation(
                        formdata.affiliation,
                        formdata.affiliation,
                        self.settings.affiliation_country or "TWN",
                    )
                    affiliation_id = (
                        int(affiliation.id)
                        if affiliation.id and affiliation.id.isdigit()
                        else None
                    )
                    # Only an affiliation created by this call may be removed
                    # again, so a rejected password does not leave it behind.
                    created_affiliation_id = (
                        affiliation.id if affiliation_id is not None else None
                    )
            else:
                affiliation_id = self.settings.affiliation_id

            if affiliation_id is None:
                raise ValueError("AFFILIATION_ID is required to create an account.")

            create_user_data = CreateUser.model_validate(formdata.model_dump())
            team_id, user_id = await web.create_team_and_user(
                create_user_data,
                category_id,
                affiliation_id,
            )

            try:
                await web.set_user_password(
                    user_id,
                    formdata.password,
                    user_roles,
                )
            except Exception as exc:
                logger.exception(
                    "Failed to set the DOMjudge password for %s", formdata.username
                )
                orphan = await self._rollback_account(
                    web,
                    formdata.username,
                    team_id,
                    affiliation_id=created_affiliation_id,
                )
                reason = _rejection_reason(exc)
                if orphan is None:
                    message = f"設定密碼失敗, 未建立帳號 {formdata.username}"
                else:
                    message = (
                        f"設定密碼失敗, 且無法確認已清除{orphan} "
                        f"{formdata.username}, 請通知管理者檢查"
                    )
                if reason:
                    message = f"{message}: {reason}"
                raise AccountCreationError(message) from None

            return formdata

    def _check_password_policy(self, password: str) -> None:
        """Reject a password the target DOMjudge would refuse.

        Runs before any write so a rejected password cannot leave an orphaned
        passwordless account behind. The minimum comes from
        effective_min_password_length, which already prefers the value the
        server reported.
        """
        minimum = self.settings.effective_min_password_length
        actual = password_byte_length(password)
        if actual < minimum:
            raise InvalidPasswordError(
                f"密碼長度不足, 至少需 {minimum} 個位元組"
                f"(英數各算 1 個, 中文每字通常算 3 個), 目前為 {actual} 個位元組"
            )

    async def _rollback_account(
        self,
        web: BaseDomServerWeb,
        username: str,
        team_id: str,
        affiliation_id: str | None = None,
    ) -> str | None:
        """Delete a partially created account so no passwordless user is left.

        Returns a description of what could not be removed, or None on success.
        The delete helpers match rows from a listing page and silently no-op when
        nothing matches, so the result is confirmed through the API instead of
        trusting that no exception means the rows are gone.
        """
        errors: list[str] = []
        cleanups: list[tuple[str, Callable[[], Awaitable[object]]]] = [
            ("使用者", lambda: web.delete_users(include=[username])),
            ("隊伍", lambda: web.delete_teams(include=[team_id])),
        ]
        if affiliation_id is not None:
            # An affiliation created for this signup must be removed too. Older
            # domjudge-tool-cli releases cannot do it, which leaves a real
            # orphan, so that is reported rather than counted as success.
            delete_affiliation = getattr(web, "delete_affiliation", None)
            if delete_affiliation is None:
                logger.error(
                    "Cannot roll back the affiliation %s created for %s: "
                    "installed domjudge-tool-cli has no delete_affiliation",
                    affiliation_id,
                    username,
                )
                errors.append("學校")
            else:
                cleanups.append(("學校", lambda: delete_affiliation(affiliation_id)))
        for label, cleanup in cleanups:
            try:
                await cleanup()
            except Exception:
                logger.exception("Failed to roll back the %s for %s", label, username)
                errors.append(label)

        if await self._user_exists(username):
            errors.append("使用者")
        return "、".join(dict.fromkeys(errors)) if errors else None

    async def _user_exists(self, username: str) -> bool:
        """Whether a user with this username is still present on DOMjudge.

        Returns True when the check itself fails, so an unverifiable rollback is
        reported to the applicant instead of being assumed successful.
        """
        username_key = username.casefold()
        try:
            async with UsersAPI(**self.settings.api_params) as api:
                users = await api.all_users()
        except Exception:
            logger.exception("Failed to verify rollback of %s", username)
            return True
        return any(it.username.casefold() == username_key for it in users)
