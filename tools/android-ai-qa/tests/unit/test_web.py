import asyncio
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import android_qa.web as web
from android_qa.config import Settings


def test_report_view_exposes_check_result_and_local_screenshot(tmp_path):
    report = tmp_path / "20261017T183000-ab12cd"
    (report / "screenshots").mkdir(parents=True)
    (report / "run.json").write_text(json.dumps({
        "scenario": "move", "goal": "Перенести задачу", "status": "blocked",
        "started": "2026-10-17T18:30:00Z", "checkpoints": [{"name": "move_target_present"}],
        "error": "Задача не появилась на целевой дате",
    }), encoding="utf-8")
    (report / "checks.json").write_text(json.dumps([{
        "name": "move_target_present", "status": "failed", "expected": "Задача на завтра",
        "actual": "Задача отсутствует", "category": "app_suspected", "confidence": "confirmed",
        "evidence": ["hierarchy/obs-0002.json", "screenshots/obs-0002.png", "../../secret.png"],
    }]), encoding="utf-8")
    view = web.report_view(report, "http://127.0.0.1:8765")
    assert view["status"] == "blocked"
    assert view["progress"] == {"done": 1, "total": 1, "current": None, "action": None, "target": None}
    assert view["checks"][0]["screenshots"] == ["http://127.0.0.1:8765/api/runs/20261017T183000-ab12cd/screenshots/obs-0002.png"]
    assert len(view["errors"]) == 2
    check_error = next(error for error in view["errors"] if error["name"] == "move_target_present")
    assert check_error["screenshots"] == view["checks"][0]["screenshots"]


def test_run_manager_rejects_parallel_scenarios(monkeypatch, tmp_path):
    started = threading.Event()
    release = threading.Event()

    async def fake_run(_settings, _goal, _scenario, _capabilities, on_report=None):
        started.set()
        await asyncio.to_thread(release.wait, 2)
        if on_report:
            on_report(SimpleNamespace(id="report-123"))
        return SimpleNamespace(id="report-123", metadata={"status": "passed", "flow": {"status": "verified"}})

    monkeypatch.setattr(web, "run_scenario", fake_run)
    manager = web.RunManager(Settings(artifacts=tmp_path, device="emulator-test"))
    first = manager.start("create")
    assert first and started.wait(1)
    assert manager.start("delete") is None
    release.set()
    deadline = time.monotonic() + 2
    while manager.snapshot()["status"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.01)
    assert manager.snapshot()["status"] == "passed", manager.snapshot().get("error")
    assert manager.snapshot()["scenario"] == "create"
