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


def test_normalizes_python_none_literal():
    """Regression: found live, repeatedly (3/3 retries on the same request)
    with llama3.1 — it emitted Python's None instead of JSON's null in a
    citation field, which raised on every single retry attempt since the
    model made the same mistake every time."""
    raw = '{"citation": {"document_id": None, "chunk_id": None, "location": null}}'
    assert extract_json(raw) == {"citation": {"document_id": None, "chunk_id": None, "location": None}}


def test_normalizes_python_true_false_literals():
    raw = '{"a": True, "b": False}'
    assert extract_json(raw) == {"a": True, "b": False}


def test_does_not_mangle_string_content_containing_none_true_false():
    raw = '{"answer": "None of these are True or False in isolation."}'
    assert extract_json(raw) == {"answer": "None of these are True or False in isolation."}


def test_does_not_mangle_identifiers_containing_the_literal_as_a_substring():
    raw = '{"answer": "Nonesuch and Truest are not the keywords."}'
    assert extract_json(raw) == {"answer": "Nonesuch and Truest are not the keywords."}


def test_raises_on_no_json():
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_raises_on_empty():
    with pytest.raises(ValueError):
        extract_json("")
