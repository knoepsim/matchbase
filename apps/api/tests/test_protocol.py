"""Contract tests: the API reads table messages exactly as protocol/ describes them.

protocol/mqtt/ is the language-neutral source of truth (JSON Schema plus sample messages); the firmware is tested
against the same samples. Every valid sample must pass both the schema and TableState, every invalid one must fail
both, so the Pydantic model cannot drift from the published contract.
"""
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from app.schemas.table_state import TableState

PROTOCOL = Path(__file__).resolve().parents[3] / "protocol" / "mqtt"
SCHEMA = json.loads((PROTOCOL / "table-state.v1.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)


def _samples(kind: str) -> list[Path]:
    return sorted((PROTOCOL / "examples" / kind).glob("*.json"))


def test_schema_is_valid_json_schema():
    Draft202012Validator.check_schema(SCHEMA)


def test_samples_exist():
    assert _samples("valid") and _samples("invalid")


@pytest.mark.parametrize("sample", _samples("valid"), ids=lambda p: p.stem)
def test_valid_sample_is_accepted_by_schema_and_api(sample: Path):
    payload = sample.read_text(encoding="utf-8")
    VALIDATOR.validate(json.loads(payload))
    state = TableState.model_validate_json(payload)  # what the MQTT listener does
    message = json.loads(payload)
    assert (state.left_cups, state.right_cups) == (message["leftCups"], message["rightCups"])


@pytest.mark.parametrize("sample", _samples("invalid"), ids=lambda p: p.stem)
def test_invalid_sample_is_rejected_by_schema_and_api(sample: Path):
    payload = sample.read_text(encoding="utf-8")
    assert not VALIDATOR.is_valid(json.loads(payload)), "the schema accepts it"
    with pytest.raises(ValidationError):
        TableState.model_validate_json(payload)
