from __future__ import annotations
from fastapi import Request


def get_client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host
