from __future__ import annotations

from pathlib import Path

from core.llm import LLMClient
from plugins.ticket_triage.plugin import TicketTriagePlugin


def _write_ticket_csv(path: Path, rows: str) -> Path:
    content = (
        "ticket_id,created_at,channel,customer_text,category,order_id,amount\n"
        + rows
    )
    path.write_text(content, encoding="utf-8")
    return path


def test_ticket_missing_order_id_detected(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    csv_path = _write_ticket_csv(
        tmp_path / "tickets.csv",
        "T1,2024-01-01,email,Need refund,, ,\n",
    )
    plugin = TicketTriagePlugin()
    result = plugin.analyze(
        inputs={"tickets": csv_path},
        llm=LLMClient(None),
        run_id="run-missing",
    )
    missing_steps = [step for step in result.steps if step.action == "MISSING_INFO"]
    assert missing_steps
    assert "eksik" in (missing_steps[0].decision.lower())


def test_ticket_high_priority_detected(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    csv_path = _write_ticket_csv(
        tmp_path / "tickets.csv",
        "T2,2024-01-01,email,urgent refund payment,,ORD-1,1200\n",
    )
    plugin = TicketTriagePlugin()
    result = plugin.analyze(
        inputs={"tickets": csv_path},
        llm=LLMClient(None),
        run_id="run-priority",
    )
    priority_steps = [step for step in result.steps if step.action == "PRIORITY_SCORE"]
    assert priority_steps
    evidence = " ".join(priority_steps[0].evidence)
    assert "high_priority" in evidence


def test_ticket_outputs_created(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    csv_path = _write_ticket_csv(
        tmp_path / "tickets.csv",
        "T3,2024-01-01,email,return request,,ORD-2,200\n",
    )
    plugin = TicketTriagePlugin()
    result = plugin.analyze(
        inputs={"tickets": csv_path},
        llm=LLMClient(None),
        run_id="run-outputs",
    )
    paths = [Path(artifact.path) for artifact in result.artifacts]
    assert any(path.name == "report.pdf" and path.exists() for path in paths)
    assert any(path.name == "reply_email.txt" and path.exists() for path in paths)
