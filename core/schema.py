from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd

from core import io as io_utils
from core import storage
from core.settings import Settings, load_settings


@dataclass
class InputSchema:
    required: Dict[str, str]
    optional: Dict[str, str]

    def all_columns(self) -> Dict[str, str]:
        return {**self.required, **self.optional}


SCHEMAS: Dict[str, Dict[str, InputSchema]] = {
    "ticket": {
        "tickets": InputSchema(
            required={
                "ticket_id": "string",
                "created_at": "date",
                "channel": "string",
                "customer_text": "string",
            },
            optional={
                "category": "string",
                "order_id": "string",
                "amount": "number",
            },
        )
    },
    "edoc": {
        "invoices": InputSchema(
            required={
                "invoice_id": "string",
                "vendor": "string",
                "date": "date",
                "subtotal": "number",
                "vat_rate": "number",
                "vat_amount": "number",
                "total": "number",
                "po_id": "string",
                "dn_id": "string",
            },
            optional={},
        ),
        "purchase_orders": InputSchema(
            required={
                "po_id": "string",
                "item_count": "number",
                "total_expected": "number",
            },
            optional={},
        ),
        "delivery_notes": InputSchema(
            required={
                "dn_id": "string",
                "delivered_item_count": "number",
            },
            optional={},
        ),
    },
}


class SchemaValidationError(ValueError):
    def __init__(self, messages: List[str]) -> None:
        super().__init__("\n".join(messages))
        self.messages = messages


def get_input_schema(demo_type: str, input_name: str) -> InputSchema:
    demo_schema = SCHEMAS.get(demo_type)
    if demo_schema is None or input_name not in demo_schema:
        raise ValueError(f"Unknown schema for demo={demo_type} input={input_name}")
    return demo_schema[input_name]


def normalize_column_name(name: str) -> str:
    text = name.strip().lower()
    translations = str.maketrans(
        {
            "ı": "i",
            "İ": "i",
            "ç": "c",
            "ş": "s",
            "ö": "o",
            "ü": "u",
            "ğ": "g",
        }
    )
    text = text.translate(translations)
    text = re.sub(r"[\\s\\-\\._/\\\\]+", "", text)
    text = text.replace("idno", "id")
    for suffix in ("number", "num", "no", "id"):
        if text.endswith(suffix) and len(text) > len(suffix) + 2:
            text = text[: -len(suffix)]
    return text


def _build_synonym_map(synonyms: Dict[str, List[str]] | None) -> Dict[str, set]:
    mapping: Dict[str, set] = {}
    if not synonyms:
        return mapping
    for key, values in synonyms.items():
        normalized = {normalize_column_name(key)}
        for value in values:
            normalized.add(normalize_column_name(value))
        mapping[key] = normalized
    return mapping


def auto_map_columns_scored(
    expected: List[str],
    actual: List[str],
    synonyms: Dict[str, List[str]] | None = None,
) -> tuple[Dict[str, str], Dict[str, int]]:
    actual_norm = {col: normalize_column_name(col) for col in actual}
    synonym_map = _build_synonym_map(synonyms)

    candidates: List[tuple[int, str, str]] = []
    for exp in expected:
        exp_norm = normalize_column_name(exp)
        exp_syn = synonym_map.get(exp, {exp_norm})
        for actual_col, actual_norm_value in actual_norm.items():
            score = 0
            if actual_norm_value == exp_norm:
                score = 100
            elif actual_norm_value in exp_syn:
                score = 90
            elif exp_norm in actual_norm_value or actual_norm_value in exp_norm:
                score = 70
            if score > 0:
                candidates.append((score, exp, actual_col))

    candidates.sort(key=lambda item: (-item[0], len(item[2])))

    mapping: Dict[str, str] = {exp: None for exp in expected}
    scores: Dict[str, int] = {}
    used = set()
    for score, exp, actual_col in candidates:
        if mapping[exp] is None and actual_col not in used:
            mapping[exp] = actual_col
            scores[exp] = score
            used.add(actual_col)

    return mapping, scores


def auto_map_columns(
    expected: List[str],
    actual: List[str],
    synonyms: Dict[str, List[str]] | None = None,
) -> Dict[str, str]:
    mapping, _ = auto_map_columns_scored(expected, actual, synonyms)
    return mapping


def get_synonyms(demo_type: str, input_name: str) -> Dict[str, List[str]]:
    if demo_type == "ticket" and input_name == "tickets":
        return {
            "ticket_id": ["ticketid", "id", "caseid", "requestid", "talepid", "kayitid"],
            "created_at": [
                "created",
                "createdat",
                "date",
                "timestamp",
                "olusturmatarihi",
                "tarih",
                "createdtime",
            ],
            "channel": ["channel", "source", "platform", "kanal", "kaynak"],
            "customer_text": [
                "text",
                "message",
                "body",
                "description",
                "detail",
                "aciklama",
                "icerik",
                "musterimesaji",
            ],
            "amount": ["amount", "price", "total", "tutar", "ucret", "bedel"],
            "order_id": ["orderid", "orderno", "siparisid", "siparisno"],
            "category": ["category", "kategori", "tur", "type"],
        }
    if demo_type == "edoc" and input_name == "invoices":
        return {
            "invoice_id": ["invoiceid", "invoiceno", "faturano", "faturaid", "belgeno"],
            "vendor": ["vendor", "supplier", "satici", "tedarikci", "firma"],
            "date": ["date", "tarih", "invoice_date", "faturatarihi"],
            "subtotal": ["subtotal", "linetotal", "net", "satirtutari"],
            "vat_rate": ["vatrate", "kdv", "kdvorani", "taxrate"],
            "vat_amount": ["vatamount", "kdvtutari", "kdv_tutar"],
            "total": ["total", "tutar", "toplam", "grandtotal"],
            "po_id": ["poid", "purchaseorder", "siparisno", "satinalmasiparisno"],
            "dn_id": ["deliveryid", "irsaliyeno", "deliveryno", "dnid"],
        }
    if demo_type == "edoc" and input_name == "purchase_orders":
        return {
            "po_id": ["poid", "purchaseorder", "siparisno", "satinalmasiparisno"],
            "item_count": ["itemcount", "kalemsayisi", "satirsayisi"],
            "total_expected": ["totalexpected", "beklentoplam", "siparistoplami"],
        }
    if demo_type == "edoc" and input_name == "delivery_notes":
        return {
            "dn_id": ["deliveryid", "irsaliyeno", "deliveryno", "dnid"],
            "delivered_item_count": ["delivereditemcount", "teslimkalemsayisi", "teslimsayi"],
        }
    return {}


def apply_mapping(df: pd.DataFrame, mapping: Dict[str, str] | None) -> pd.DataFrame:
    if not mapping:
        return df
    rename_map = {
        actual: expected
        for expected, actual in mapping.items()
        if actual and actual in df.columns
    }
    if rename_map:
        return df.rename(columns=rename_map)
    return df


def _check_numeric(series: pd.Series) -> bool:
    converted = pd.to_numeric(series, errors="coerce")
    invalid = converted.isna() & series.notna() & series.astype(str).str.strip().ne("")
    return not invalid.any()


def _check_date(series: pd.Series) -> bool:
    converted = pd.to_datetime(series, errors="coerce")
    invalid = converted.isna() & series.notna() & series.astype(str).str.strip().ne("")
    return not invalid.any()


def validate_columns(
    columns: Iterable[str],
    schema: InputSchema,
    mapping: Dict[str, str] | None = None,
) -> None:
    messages: List[str] = []
    available = set(columns)

    missing = []
    for col in schema.required:
        actual = mapping.get(col) if mapping and mapping.get(col) else col
        if not actual or actual not in available:
            missing.append(col)

    if missing:
        messages.append("Şu kolon eksik: " + ", ".join(missing))

    if messages:
        raise SchemaValidationError(messages)


def validate_types(df: pd.DataFrame, schema: InputSchema) -> None:
    messages: List[str] = []
    for col, col_type in schema.all_columns().items():
        if col not in df.columns:
            continue
        if col_type == "number" and not _check_numeric(df[col]):
            messages.append(f"Şu kolonda sayı bekleniyordu: {col}")
        if col_type == "date" and not _check_date(df[col]):
            messages.append(f"Şu kolonda tarih bekleniyordu: {col}")

    if messages:
        raise SchemaValidationError(messages)


def _build_dtype_map(
    schema: InputSchema,
    mapping: Dict[str, str] | None,
    available: Iterable[str],
) -> Dict[str, str]:
    dtype_map: Dict[str, str] = {}
    available_set = set(available)
    for col, col_type in schema.all_columns().items():
        actual = mapping.get(col) if mapping and mapping.get(col) else col
        if not actual or actual not in available_set:
            continue
        dtype_map[actual] = "string"
    return dtype_map


def load_mapping(run_id: str) -> Dict[str, Dict[str, str]]:
    mapping_path = storage.ensure_run_dir(run_id) / "mapping.json"
    if not mapping_path.exists():
        return {}
    with mapping_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def load_csv_with_schema(
    path: Path,
    schema: InputSchema,
    mapping: Dict[str, str] | None = None,
    settings: Settings | None = None,
) -> pd.DataFrame:
    settings = settings or load_settings()
    if mapping == {}:
        mapping = None

    header = pd.read_csv(path, nrows=0)
    available_columns = list(header.columns)
    validate_columns(available_columns, schema, mapping)

    required_actual = []
    for col in schema.required:
        required_actual.append(mapping.get(col) if mapping and mapping.get(col) else col)
    optional_actual = []
    for col in schema.optional:
        actual = mapping.get(col) if mapping and mapping.get(col) else col
        if actual in available_columns:
            optional_actual.append(actual)

    usecols = [col for col in required_actual + optional_actual if col]
    usecols = list(dict.fromkeys(usecols))
    dtype_map = _build_dtype_map(schema, mapping, usecols)

    if settings.chunk_size:
        frames = []
        for chunk in io_utils.iter_csv_chunks(
            path,
            usecols=usecols,
            dtype=dtype_map,
            nrows=settings.max_rows,
            chunksize=settings.chunk_size,
        ):
            chunk = apply_mapping(chunk, mapping)
            validate_types(chunk, schema)
            for col, col_type in schema.all_columns().items():
                if col not in chunk.columns:
                    continue
                if col_type == "number":
                    chunk[col] = pd.to_numeric(chunk[col], errors="coerce")
                if col_type == "date":
                    chunk[col] = pd.to_datetime(chunk[col], errors="coerce")
            frames.append(chunk)
        if not frames:
            return pd.DataFrame(columns=schema.all_columns().keys())
        return pd.concat(frames, ignore_index=True)

    df = io_utils.read_csv_safely(
        path,
        usecols=usecols,
        dtype=dtype_map,
        nrows=settings.max_rows,
    )
    df = apply_mapping(df, mapping)
    validate_types(df, schema)
    for col, col_type in schema.all_columns().items():
        if col not in df.columns:
            continue
        if col_type == "number":
            df[col] = pd.to_numeric(df[col], errors="coerce")
        if col_type == "date":
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df
