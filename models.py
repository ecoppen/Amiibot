import re

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)

MAX_TITLE_LENGTH = 300
MAX_URL_LENGTH = 2048
MAX_IMAGE_LENGTH = 2048
MAX_PRICE_LENGTH = 30


class ScrapedProduct(BaseModel):
    Title: str = Field(max_length=MAX_TITLE_LENGTH, min_length=1)
    Price: str = Field(max_length=MAX_PRICE_LENGTH, min_length=1)
    Stock: str
    URL: str = Field(max_length=MAX_URL_LENGTH)
    Website: str = Field(max_length=100)
    Image: str = Field(max_length=MAX_IMAGE_LENGTH)
    Colour: int

    @field_validator("Title", "Stock", "Website")
    @classmethod
    def strip_control_chars(cls, v: str) -> str:
        return _strip_control_characters(v)

    @field_validator("URL", "Image")
    @classmethod
    def validate_urls(cls, v: str) -> str:
        if not re.match(r"^https://", v):
            raise ValueError(f"URL must use HTTPS: {v[:80]}")
        return _strip_control_characters(v)


_control_char_pattern = re.compile(
    "[" + re.escape("".join(chr(i) for i in range(32))) + "\x7f" + "]"
)


def _strip_control_characters(text: str) -> str:
    stripped = _control_char_pattern.sub("", text)
    if stripped != text:
        import logging

        log = logging.getLogger(__name__)
        log.warning(f"Stripped control characters from field: {repr(text[:80])}")
    return stripped


def deduplicate_by_url(products: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for item in products:
        key = _canonical_url(item.get("URL", ""))
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _canonical_url(url: str) -> str:
    cleaned = url.rstrip("/").lower()
    return cleaned


def validate_products(
    products: list[dict],
) -> tuple[list[dict], list[str]]:
    valid = []
    errors = []
    for idx, item in enumerate(products):
        try:
            ScrapedProduct(**item)
            valid.append(item)
        except Exception as e:
            errors.append(f"item {idx}: {e}")
    return valid, errors
