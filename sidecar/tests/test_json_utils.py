import pytest

from src.llm.json_utils import extract_json


def test_extracts_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_strips_markdown_fences():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_ignores_surrounding_prose():
    assert extract_json('Here you go:\n{"a": 1}\nHope that helps.') == {"a": 1}


def test_tolerates_trailing_commas():
    assert extract_json('{"a": 1, "b": [1, 2,],}') == {"a": 1, "b": [1, 2]}


def test_tolerates_braces_inside_string_values():
    raw = '{"answer": "Revenue rose (see footnote}", "x": 1}'
    assert extract_json(raw) == {"answer": "Revenue rose (see footnote}", "x": 1}


def test_tolerates_escaped_quotes_inside_string_values():
    raw = r'{"answer": "He said \"revenue is up\"."}'
    assert extract_json(raw) == {"answer": 'He said "revenue is up".'}


def test_raises_on_no_json():
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_raises_on_empty():
    with pytest.raises(ValueError):
        extract_json("")
