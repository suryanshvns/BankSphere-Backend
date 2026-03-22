from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_current_user, get_user_service
from app.schemas.user import (
    ChangePasswordRequest,
    KycSubmitRequest,
    ProfileUpdateRequest,
    UserLimitsResponse,
    UserLimitsUpdateRequest,
    UserResponse,
)
from app.services.user_service import UserService
from app.utils.request_info import get_client_ip
from app.utils.response import success_response

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def me(user: Annotated[object, Depends(get_current_user)]) -> dict:
    return success_response(UserResponse.model_validate(user).model_dump(mode="json"))


@router.patch("/me")
async def patch_me(
    body: ProfileUpdateRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[UserService, Depends(get_user_service)],
) -> dict:
    updated = await svc.update_me(
        user=user,  # type: ignore[arg-type]
        full_name=body.full_name,
        phone=body.phone,
        notify_email=body.notify_email,
        notify_push=body.notify_push,
    )
    return success_response(UserResponse.model_validate(updated).model_dump(mode="json"))


@router.post("/me/password")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[UserService, Depends(get_user_service)],
) -> dict:
    await svc.change_password(
        user=user,  # type: ignore[arg-type]
        current_password=body.current_password,
        new_password=body.new_password,
        ip=get_client_ip(request),
    )
    return success_response({"ok": True})


@router.get("/me/limits")
async def get_limits(user: Annotated[object, Depends(get_current_user)]) -> dict:
    payload = UserLimitsResponse.model_validate(user).model_dump(mode="json")
    return success_response(payload)


@router.patch("/me/limits")
async def patch_limits(
    body: UserLimitsUpdateRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[UserService, Depends(get_user_service)],
) -> dict:
    updated = await svc.update_limits(
        user=user,  # type: ignore[arg-type]
        daily_transfer_max=body.daily_transfer_max,
        daily_atm_max=body.daily_atm_max,
    )
    return success_response(UserLimitsResponse.model_validate(updated).model_dump(mode="json"))


@router.post("/me/kyc/submit")
async def submit_kyc(
    request: Request,
    body: KycSubmitRequest,
    user: Annotated[object, Depends(get_current_user)],
    svc: Annotated[UserService, Depends(get_user_service)],
) -> dict:
    updated = await svc.submit_kyc(
        user=user,  # type: ignore[arg-type]
        reference_id=body.reference_id,
        ip=get_client_ip(request),
    )
    return success_response(UserResponse.model_validate(updated).model_dump(mode="json"))
