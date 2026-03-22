from __future__ import annotations

from prisma import Prisma
from prisma.enums import KybStatus
from prisma.models import User

from app.core.exceptions import NotFoundError, ValidationAppError
from app.services.audit_service import AuditService


class CxPortalService:
    def __init__(self, prisma: Prisma, audit: AuditService) -> None:
        self._prisma = prisma
        self._audit = audit

    async def create_support_case(
        self, *, user: User, subject: str, body: str | None, priority: int, ip: str | None
    ):
        row = await self._prisma.supportcase.create(
            data={"user_id": user.id, "subject": subject, "body": body, "priority": priority},
        )
        await self._audit.log(
            user_id=user.id,
            action="SUPPORT_CASE_CREATED",
            resource=f"support_case:{row.id}",
            ip_address=ip,
        )
        return row

    async def list_support_cases(self, *, user: User):
        return await self._prisma.supportcase.find_many(
            where={"user_id": user.id},
            order={"created_at": "desc"},
        )

    async def upsert_business_profile(
        self,
        *,
        user: User,
        company_name: str,
        registration_number: str | None,
        country: str,
        ip: str | None,
    ):
        row = await self._prisma.businessprofile.upsert(
            where={"user_id": user.id},
            data={
                "create": {
                    "user_id": user.id,
                    "company_name": company_name,
                    "registration_number": registration_number,
                    "country": country,
                    "status": KybStatus.PENDING,
                },
                "update": {
                    "company_name": company_name,
                    "registration_number": registration_number,
                    "country": country,
                    "status": KybStatus.PENDING,
                },
            },
        )
        await self._audit.log(
            user_id=user.id,
            action="KYB_PROFILE_UPSERTED",
            resource=f"business_profile:{row.id}",
            ip_address=ip,
        )
        return row

    async def request_data_export(self, *, user: User, ip: str | None):
        row = await self._prisma.dataexportrequest.create(data={"user_id": user.id})
        await self._audit.log(
            user_id=user.id,
            action="DATA_EXPORT_REQUESTED",
            resource=f"data_export:{row.id}",
            ip_address=ip,
        )
        return row

    async def get_data_export(self, *, user: User, export_id: str):
        row = await self._prisma.dataexportrequest.find_first(
            where={"id": export_id, "user_id": user.id}
        )
        if row is None:
            raise NotFoundError("Export not found")
        return row
