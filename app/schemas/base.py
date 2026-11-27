from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.core.constants import MAX_PASSWORD_BYTES


class TrimmedBaseModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


def validate_password_bytes(value: str) -> str:
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must not exceed {MAX_PASSWORD_BYTES} bytes")
    return value


def reject_explicit_nulls(data: Any, fields: Iterable[str]) -> Any:
    if isinstance(data, dict):
        for field in fields:
            if field in data and data[field] is None:
                raise ValueError(f"Field '{field}' cannot be null")
    return data
