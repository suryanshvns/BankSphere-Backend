from __future__ import annotations
class AppException(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "bad_request") -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found", code: str = "not_found") -> None:
        super().__init__(message, status_code=404, code=code)


class UnauthorizedError(AppException):
    def __init__(self, message: str = "Unauthorized", code: str = "unauthorized") -> None:
        super().__init__(message, status_code=401, code=code)


class ForbiddenError(AppException):
    def __init__(self, message: str = "Forbidden", code: str = "forbidden") -> None:
        super().__init__(message, status_code=403, code=code)


class ConflictError(AppException):
    def __init__(self, message: str = "Conflict", code: str = "conflict") -> None:
        super().__init__(message, status_code=409, code=code)


class ValidationAppError(AppException):
    def __init__(self, message: str, code: str = "validation_error") -> None:
        super().__init__(message, status_code=422, code=code)
