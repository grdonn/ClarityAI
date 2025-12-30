from __future__ import annotations

from pathlib import Path

import pytest

from core.schema import (
    SchemaValidationError,
    get_input_schema,
    get_synonyms,
    auto_map_columns_scored,
    load_csv_with_schema,
)


def test_mapping_allows_custom_columns(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "tickets.csv"
    path.write_text(
        "TicketID,CreatedAt,Channel,CustomerText,Amount\n"
        "T1,2024-01-01,email,Hello,100\n",
        encoding="utf-8",
    )
    schema = get_input_schema("ticket", "tickets")
    mapping = {
        "ticket_id": "TicketID",
        "created_at": "CreatedAt",
        "channel": "Channel",
        "customer_text": "CustomerText",
        "amount": "Amount",
    }
    df = load_csv_with_schema(path, schema, mapping)
    assert "ticket_id" in df.columns
    assert "created_at" in df.columns


def test_no_mapping_when_schema_matches(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "tickets.csv"
    path.write_text(
        "ticket_id,created_at,channel,customer_text\n"
        "T1,2024-01-01,email,Hello\n",
        encoding="utf-8",
    )
    schema = get_input_schema("ticket", "tickets")
    df = load_csv_with_schema(path, schema, None)
    assert len(df) == 1


def test_missing_column_error(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "tickets.csv"
    path.write_text(
        "ticket_id,channel,customer_text\n"
        "T1,email,Hello\n",
        encoding="utf-8",
    )
    schema = get_input_schema("ticket", "tickets")
    with pytest.raises(SchemaValidationError) as exc:
        load_csv_with_schema(path, schema, None)
    assert "Şu kolon eksik" in str(exc.value)


def test_numeric_type_error(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "tickets.csv"
    path.write_text(
        "ticket_id,created_at,channel,customer_text,amount\n"
        "T1,2024-01-01,email,Hello,abc\n",
        encoding="utf-8",
    )
    schema = get_input_schema("ticket", "tickets")
    with pytest.raises(SchemaValidationError) as exc:
        load_csv_with_schema(path, schema, None)
    assert "Şu kolonda sayı bekleniyordu" in str(exc.value)


def test_auto_mapping_synonyms() -> None:
    expected = ["ticket_id", "created_at", "channel", "customer_text"]
    actual = ["ID", "Date", "Source", "Message"]
    synonyms = get_synonyms("ticket", "tickets")
    mapping, scores = auto_map_columns_scored(expected, actual, synonyms)
    assert mapping["ticket_id"] == "ID"
    assert mapping["created_at"] == "Date"
    assert mapping["channel"] == "Source"
    assert mapping["customer_text"] == "Message"
    assert all(scores.get(key) is not None for key in expected)
