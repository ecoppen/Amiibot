"""Unit tests for product validation."""

import logging

from models import deduplicate_by_url, validate_products


def _item(**overrides):
    item = {
        "Title": "Mario",
        "Price": "£14.99",
        "Stock": "In Stock",
        "URL": "https://example.com/mario",
        "Website": "Example",
        "Image": "https://example.com/mario.png",
        "Colour": 0xFF0000,
    }
    item.update(overrides)
    return item


class TestValidateProducts:
    def test_returns_stripped_values(self):
        valid, errors = validate_products(
            [_item(Title="Mario\t", Stock="In\x00 Stock")]
        )
        assert errors == []
        assert valid[0]["Title"] == "Mario"
        assert valid[0]["Stock"] == "In Stock"

    def test_surrounding_whitespace_trimmed_without_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="models"):
            valid, _ = validate_products([_item(Title=" Leon amiibo\t\n")])
        assert valid[0]["Title"] == "Leon amiibo"
        assert "Stripped control characters" not in caplog.text

    def test_embedded_control_characters_still_warn(self, caplog):
        with caplog.at_level(logging.WARNING, logger="models"):
            valid, _ = validate_products([_item(Title="Leon\x00 amiibo")])
        assert valid[0]["Title"] == "Leon amiibo"
        assert "Stripped control characters" in caplog.text

    def test_release_absent_when_none(self):
        valid, _ = validate_products([_item()])
        assert "Release" not in valid[0]

    def test_release_kept_when_present(self):
        valid, _ = validate_products([_item(Release="2026-11-01")])
        assert valid[0]["Release"] == "2026-11-01"

    def test_colour_stays_int(self):
        valid, _ = validate_products([_item()])
        assert valid[0]["Colour"] == 0xFF0000
        assert isinstance(valid[0]["Colour"], int)

    def test_invalid_items_reported(self):
        valid, errors = validate_products([_item(URL="http://insecure.example")])
        assert valid == []
        assert len(errors) == 1
        assert errors[0].startswith("item 0:")

    def test_cleaned_output_is_not_restripped_on_next_pass(self, caplog):
        valid, _ = validate_products([_item(Title="Mario\t")])
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="models"):
            validate_products(valid)
        assert "Stripped control characters" not in caplog.text

    def test_works_with_deduplicate_by_url(self):
        valid, _ = validate_products(
            [_item(), _item(URL="https://example.com/mario/", Title="Dup")]
        )
        assert len(deduplicate_by_url(valid)) == 1
