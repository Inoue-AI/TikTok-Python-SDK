"""Shared base types used across all TikTok API response models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TikTokError(BaseModel):
    """Error object embedded in every TikTok API response.

    Attributes:
        code:    Short error identifier (``"ok"`` when the call succeeded).
        message: Human-readable description of the error.
        log_id:  Opaque request identifier for support / debugging.
    """

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    log_id: str


class TikTokBaseModel(BaseModel):
    """Base class for all SDK response models.

    All response models inherit from this class so that unknown fields
    returned by future API versions are silently ignored rather than
    causing validation failures.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
        populate_by_name=True,
    )
