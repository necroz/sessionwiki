"""Tests for entity type taxonomy (v1.0, #137)."""

from __future__ import annotations

import pytest

from sessionwiki.schema import ENTITY_TYPES, validate_entity_type


def test_entity_types_has_7_values():
    assert len(ENTITY_TYPES) == 7


def test_entity_types_contains_all_spec_values():
    expected = {"person", "org", "tool", "concept", "api", "library", "project"}
    assert set(ENTITY_TYPES) == expected


@pytest.mark.parametrize("value", ENTITY_TYPES)
def test_validate_entity_type_valid(value):
    valid, msg = validate_entity_type(value)
    assert valid is True
    assert "valid" in msg


def test_validate_entity_type_case_insensitive():
    valid, _ = validate_entity_type("PERSON")
    assert valid is True


def test_validate_entity_type_with_whitespace():
    valid, _ = validate_entity_type("  tool  ")
    assert valid is True


def test_validate_entity_type_invalid():
    valid, msg = validate_entity_type("dinosaur")
    assert valid is False
    assert "not valid" in msg
    assert "person" in msg  # lists valid options


def test_validate_entity_type_empty():
    valid, msg = validate_entity_type("")
    assert valid is False
    assert "empty" in msg
