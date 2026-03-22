from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_auth_extended_service, get_auth_service, get_current_user
from app.core.exceptions import NotFoundError
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginTokenResponse,
    LogoutRequest,
    RefreshRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.auth_extended_service import AuthExtendedService
from app.services.auth_service import AuthService
from app.utils.request_info import get_client_ip
from app.utils.response import success_response

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup")
async def signup(
    request: Request,
    body: SignupRequest,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> dict:
    user = await auth.signup(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        ip=get_client_ip(request),
    )
    return success_response(UserResponse.model_validate(user).model_dump(mode="json"))


@router.post("/login")
async def login(
    request: Request,
    body: LoginRequest,
    auth: Annotated[AuthExtendedService, Depends(get_auth_extended_service)],
) -> dict:
    ua = request.headers.get("user-agent")
    access, refresh, _user = await auth.login_with_refresh(
        email=body.email,
        password=body.password,
        ip=get_client_ip(request),
        user_agent=ua,
    )
    payload = LoginTokenResponse(access_token=access, refresh_token=refresh).model_dump(mode="json")
    return success_response(payload)


@router.post("/refresh")
async def refresh_token(
    body: RefreshRequest,
    auth: Annotated[AuthExtendedService, Depends(get_auth_extended_service)],
) -> dict:
    access, _user = await auth.refresh_access(refresh_token=body.refresh_token)
    return success_response(TokenResponse(access_token=access).model_dump(mode="json"))


@router.post("/logout")
async def logout(
    body: LogoutRequest,
    auth: Annotated[AuthExtendedService, Depends(get_auth_extended_service)],
) -> dict:
    await auth.logout(refresh_token=body.refresh_token)
    return success_response({"ok": True})


@router.get("/sessions")
async def list_sessions(
    user: Annotated[object, Depends(get_current_user)],
    auth: Annotated[AuthExtendedService, Depends(get_auth_extended_service)],
) -> dict:
    rows = await auth.list_sessions(getattr(user, "id"))  # type: ignore[arg-type]
    return success_response(rows)


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    user: Annotated[object, Depends(get_current_user)],
    auth: Annotated[AuthExtendedService, Depends(get_auth_extended_service)],
) -> dict:
    ok = await auth.revoke_session(user_id=getattr(user, "id"), session_id=session_id)  # type: ignore[arg-type]
    if not ok:
        raise NotFoundError("Session not found")
    return success_response({"ok": True})


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    auth: Annotated[AuthExtendedService, Depends(get_auth_extended_service)],
) -> dict:
    out = await auth.forgot_password(email=body.email)
    return success_response(out)


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    auth: Annotated[AuthExtendedService, Depends(get_auth_extended_service)],
) -> dict:
    await auth.reset_password(token=body.token, new_password=body.new_password)
    return success_response({"ok": True})
