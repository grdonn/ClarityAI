from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from core.audit import AuditTrailReader, AuditTrailWriter
from core.engine import Engine
from plugins.edocument_audit.plugin import EDocumentAuditPlugin


def _write_edoc_inputs(tmp_path: Path) -> dict[str, Path]:
    invoices = tmp_path / "invoices.csv"
    purchase_orders = tmp_path / "purchase_orders.csv"
    delivery_notes = tmp_path / "delivery_notes.csv"

    invoices.write_text(
        "invoice_id,vendor,date,subtotal,vat_rate,vat_amount,total,po_id,dn_id\n"
        "INV-001,Vendor A,2024-01-01,100,0.18,18,118,PO-001,DN-001\n"
        "INV-002,Vendor B,2024-01-02,200,0.18,36,240,PO-002,DN-002\n"
        "INV-002,Vendor B,2024-01-02,200,0.18,36,240,PO-002,DN-002\n"
        "INV-003,Vendor C,2024-01-03,150,0.18,30,170,PO-003,DN-003\n",
        encoding="utf-8",
    )
    purchase_orders.write_text(
        "po_id,item_count,total_expected\n"
        "PO-001,2,118\n"
        "PO-002,3,236\n"
        "PO-003,1,177\n",
        encoding="utf-8",
    )
    delivery_notes.write_text(
        "dn_id,delivered_item_count\n"
        "DN-001,2\n"
        "DN-002,3\n"
        "DN-003,2\n",
        encoding="utf-8",
    )

    return {
        "invoices": invoices,
        "purchase_orders": purchase_orders,
        "delivery_notes": delivery_notes,
    }


def test_edoc_duplicate_detected(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    inputs = _write_edoc_inputs(tmp_path)
    plugin = EDocumentAuditPlugin()
    result = plugin.analyze(inputs=inputs, llm=None, run_id="run-edoc")
    duplicate_steps = [step for step in result.steps if step.action == "DUPLICATE_CHECK"]
    assert duplicate_steps
    assert duplicate_steps[0].severity == "high"


def test_edoc_total_mismatch_detected(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    inputs = _write_edoc_inputs(tmp_path)
    plugin = EDocumentAuditPlugin()
    result = plugin.analyze(inputs=inputs, llm=None, run_id="run-edoc")
    total_steps = [step for step in result.steps if step.action == "TOTAL_CHECK"]
    assert total_steps
    assert total_steps[0].status == "needs_approval"


def test_edoc_vat_mismatch_detected(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    inputs = _write_edoc_inputs(tmp_path)
    plugin = EDocumentAuditPlugin()
    result = plugin.analyze(inputs=inputs, llm=None, run_id="run-edoc")
    vat_steps = [step for step in result.steps if step.action == "VAT_CHECK"]
    assert vat_steps
    assert vat_steps[0].status == "needs_approval"


def test_edoc_apply_creates_corrected_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    inputs = _write_edoc_inputs(tmp_path)
    plugin = EDocumentAuditPlugin()
    result = plugin.analyze(inputs=inputs, llm=None, run_id="run-edoc")
    artifacts = plugin.apply(inputs, result.recommendations, run_id="run-edoc")
    paths = [Path(artifact.path) for artifact in artifacts]
    assert any(path.name == "corrected_invoices.csv" and path.exists() for path in paths)


def test_edoc_audit_status_applied(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    inputs = _write_edoc_inputs(tmp_path)
    engine = Engine()
    result = engine.run("edoc", inputs)
    writer = AuditTrailWriter()
    reader = AuditTrailReader()
    audit = reader.load_run(result.run_id)
    assert any(step.status == "needs_approval" for step in audit.steps)

    rec_path = Path("runs") / result.run_id / "recommendations.json"
    with rec_path.open("r", encoding="utf-8") as handle:
        recommendations = json.load(handle)

    plugin = engine.registry["edoc"]
    plugin.apply(inputs, recommendations, result.run_id)
    writer.mark_applied(result.run_id)
    writer.finalize_run(result.run_id, audit.final_summary or "", audit.artifacts)

    updated = reader.load_run(result.run_id)
    assert all(
        step.status != "needs_approval" for step in updated.steps if step.requires_approval
    )


def test_edoc_reference_checks(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    inputs = _write_edoc_inputs(tmp_path)
    vendors = tmp_path / "vendors.csv"
    vendors.write_text("vendor\nVendor A\n", encoding="utf-8")
    rates = tmp_path / "allowed_vat_rates.json"
    rates.write_text("[0.08]", encoding="utf-8")
    inputs["vendors"] = vendors
    inputs["allowed_vat_rates"] = rates

    plugin = EDocumentAuditPlugin()
    result = plugin.analyze(inputs=inputs, llm=None, run_id="run-edoc-ref")
    issues_path = Path(result.artifacts[1].path)
    issues_df = pd.read_csv(issues_path)
    rules = set(issues_df["rule"].tolist())
    assert "VENDOR_NOT_ALLOWED" in rules
    assert "VAT_RATE_NOT_ALLOWED" in rules
