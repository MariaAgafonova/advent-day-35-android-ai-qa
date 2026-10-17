"""Loopback-only browser UI for running and inspecting QA scenarios."""
from __future__ import annotations

import asyncio
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .agent import run_scenario
from .cli import capabilities
from .config import Settings
from .diagnostics import ensure_web_device

SCENARIOS = {
    "create": ("Создание задачи", "Создать одну задачу на сегодня и проверить значения и сохранение."),
    "move": ("Перенос на другой день", "Перенести собственную задачу на завтра, проверить обе даты и сохранение."),
    "status": ("Изменение статуса", "Отметить собственную задачу выполненной и проверить статус после перезапуска."),
    "delete": ("Удаление задачи", "Удалить собственную задачу и проверить отсутствие после перезапуска."),
    "lifecycle": ("Полный цикл", "Создание, перенос, изменение статуса и удаление одной тестовой задачи."),
    "undo": ("Отмена удаления", "Проверить отмену удаления задачи, если приложение показывает Undo."),
    "empty-title": ("Пустое название", "Проверить валидацию задачи без названия."),
    "long-title": ("Длинное название", "Проверить отображение длинного названия задачи."),
    "keyboard": ("Открытая клавиатура", "Проверить сохранение задачи при открытой экранной клавиатуре."),
}
PRIMARY = {"create", "move", "status", "delete"}
RUN_ID = re.compile(r"^[A-Za-z0-9-]{1,80}$")
IMAGE_NAME = re.compile(r"^obs-\d{4}\.png$")
WEB_DIR = Path(__file__).parent


def _read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def report_view(report_dir: Path, base_url=""):
    """Return the user-facing, non-secret subset of one local report."""
    meta = _read_json(report_dir / "run.json", {})
    if not meta:
        return None
    checks = _read_json(report_dir / "checks.json", [])
    events = []
    try:
        lines = (report_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()[-100:]
        events = [json.loads(line) for line in lines]
    except (OSError, ValueError):
        pass
    checkpoints = meta.get("checkpoints") or []
    check_by_name = {c.get("name"): c for c in checks if isinstance(c, dict)}
    complete = sum(1 for point in checkpoints if point.get("name") in check_by_name)
    last_action = next((e for e in reversed(events) if e.get("kind") == "action"), None)
    active = meta.get("status") == "running"

    def image_urls(check):
        urls = []
        for path in check.get("evidence", []):
            parts = Path(str(path).replace("\\", "/")).parts
            if len(parts) == 2 and parts[0] == "screenshots" and IMAGE_NAME.fullmatch(parts[1]):
                urls.append(f"{base_url}/api/runs/{report_dir.name}/screenshots/{parts[1]}")
        return urls

    visible_checks = [{
        "name": c.get("name", "Проверка"), "status": c.get("status", "not_checked"),
        "expected": c.get("expected", ""), "actual": c.get("actual", ""),
        "category": c.get("category", "functional"), "confidence": c.get("confidence", "confirmed"),
        "screenshots": image_urls(c),
    } for c in checks if isinstance(c, dict)]
    errors = [{"name": c["name"], "status": c["status"], "actual": c["actual"],
               "screenshots": c["screenshots"]}
              for c in visible_checks if c["status"] in {"failed", "blocked"}]
    if meta.get("error"):
        last_shots = next((c["screenshots"] for c in reversed(visible_checks) if c["screenshots"]), [])
        errors.insert(0, {"name": "Остановка сценария", "status": "blocked",
                          "actual": str(meta["error"]), "screenshots": last_shots})
    if meta.get("cleanup_error"):
        errors.append({"name": "Очистка тестовых данных", "status": "blocked", "actual": str(meta["cleanup_error"])})
    points = [{"name": point.get("name", ""), "done": point.get("name") in check_by_name,
               "status": check_by_name.get(point.get("name"), {}).get("status", "pending")}
              for point in checkpoints]
    return {
        "id": report_dir.name, "scenario": meta.get("scenario", ""), "goal": meta.get("goal", ""),
        "status": meta.get("status", "unknown"), "started": meta.get("started"),
        "finished": meta.get("finished"), "active": active,
        "flow_status": (meta.get("flow") or {}).get("status"),
        "progress": {"done": complete, "total": len(checkpoints),
                     "current": last_action.get("milestone") if last_action else None,
                     "action": last_action.get("action", {}).get("kind") if last_action else None,
                     "target": last_action.get("target") if last_action else None},
        "checkpoints": points, "checks": visible_checks, "errors": errors,
    }


class RunManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.lock = threading.Lock()
        self.current = None

    def start(self, scenario: str):
        with self.lock:
            if self.current and self.current["status"] in {"queued", "running"}:
                return None
            job = {"id": "web-" + uuid.uuid4().hex[:12], "scenario": scenario,
                   "status": "queued", "report_id": None, "error": None}
            self.current = job
            threading.Thread(target=self._worker, args=(job,), daemon=True, name="android-qa-run").start()
            return dict(job)

    def _worker(self, job):
        def set_stage(stage):
            with self.lock:
                if self.current and self.current["id"] == job["id"]:
                    self.current.update(stage=stage)
        def report_created(report):
            with self.lock:
                if self.current and self.current["id"] == job["id"]:
                    self.current.update(report_id=report.id, status="running")
        try:
            ensure_web_device(self.settings, on_status=set_stage)
            title, goal = SCENARIOS[job["scenario"]]
            report = asyncio.run(run_scenario(self.settings, goal, job["scenario"],
                                              capabilities(self.settings), on_report=report_created))
            status = report.metadata.get("status", "blocked")
            with self.lock:
                if self.current and self.current["id"] == job["id"]:
                    self.current.update(status=status, report_id=report.id,
                                        flow_status=(report.metadata.get("flow") or {}).get("status"))
        except BaseException as exc:
            with self.lock:
                if self.current and self.current["id"] == job["id"]:
                    self.current.update(status="blocked", error=f"{type(exc).__name__}: {exc}"[:1000])

    def snapshot(self):
        with self.lock:
            return dict(self.current) if self.current else None


def create_handler(settings: Settings, manager: RunManager, public_url: str):
    root = settings.artifacts.resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "AndroidQAWeb/1.0"

        def log_message(self, _format, *args):
            return

        def send_bytes(self, body: bytes, content_type: str, status=200):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, value, status=200):
            self.send_bytes(json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

        def report_dirs(self):
            if not root.is_dir():
                return []
            found = []
            for path in root.iterdir():
                if path.is_dir() and RUN_ID.fullmatch(path.name):
                    meta = _read_json(path / "run.json", {})
                    if meta.get("scenario") in SCENARIOS:
                        found.append((path, meta))
            return sorted(found, key=lambda pair: pair[1].get("started", ""), reverse=True)

        def do_GET(self):
            route = urlparse(self.path).path
            if route == "/":
                return self.send_bytes((WEB_DIR / "web_index.html").read_bytes(), "text/html; charset=utf-8")
            if route in {"/app.js", "/style.css"}:
                filename = "web_app.js" if route == "/app.js" else "web_style.css"
                mime = "text/javascript; charset=utf-8" if filename.endswith(".js") else "text/css; charset=utf-8"
                return self.send_bytes((WEB_DIR / filename).read_bytes(), mime)
            if route == "/api/state":
                latest = {}
                for path, meta in self.report_dirs():
                    latest.setdefault(meta["scenario"], report_view(path, public_url))
                active = manager.snapshot()
                active_report = None
                if active and active.get("report_id"):
                    active_dir = root / active["report_id"]
                    active_report = report_view(active_dir, public_url)
                return self.send_json({
                    "device": settings.device, "app_id": settings.app_id,
                    "scenarios": [{"id": key, "title": title, "description": description,
                                   "primary": key in PRIMARY, "latest": latest.get(key)}
                                  for key, (title, description) in SCENARIOS.items()],
                    "active": active, "active_report": active_report,
                })
            match = re.fullmatch(r"/api/runs/([A-Za-z0-9-]{1,80})", route)
            if match:
                report_dir = root / match.group(1)
                view = report_view(report_dir, public_url) if report_dir.parent == root else None
                return self.send_json(view or {"error": "Отчёт не найден"}, 200 if view else 404)
            report_match = re.fullmatch(r"/api/runs/([A-Za-z0-9-]{1,80})/report", route)
            if report_match:
                report_dir = root / report_match.group(1)
                try:
                    report_path = (report_dir / "report.md").resolve()
                    report_path.relative_to(report_dir.resolve())
                    if report_dir.parent != root or not report_path.is_file():
                        raise ValueError
                    return self.send_bytes(report_path.read_bytes(), "text/markdown; charset=utf-8")
                except (ValueError, OSError):
                    return self.send_json({"error": "Отчёт не найден"}, 404)
            image = re.fullmatch(r"/api/runs/([A-Za-z0-9-]{1,80})/screenshots/(obs-\d{4}\.png)", route)
            if image:
                report_dir = (root / image.group(1)).resolve()
                file_path = (report_dir / "screenshots" / image.group(2)).resolve()
                try:
                    file_path.relative_to(report_dir / "screenshots")
                    if report_dir.parent != root or not file_path.is_file():
                        raise ValueError
                    return self.send_bytes(file_path.read_bytes(), "image/png")
                except (ValueError, OSError):
                    return self.send_json({"error": "Скриншот не найден"}, 404)
            return self.send_json({"error": "Не найдено"}, 404)

        def do_POST(self):
            if urlparse(self.path).path != "/api/runs":
                return self.send_json({"error": "Не найдено"}, 404)
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 1 or size > 4096:
                    return self.send_json({"error": "Некорректный размер запроса"}, 400)
                body = json.loads(self.rfile.read(size))
                scenario = body.get("scenario") if isinstance(body, dict) else None
                if scenario not in SCENARIOS:
                    return self.send_json({"error": "Неизвестный сценарий"}, 400)
                if not settings.api_key.get_secret_value():
                    return self.send_json({"error": "Задайте DEEPSEEK_API_KEY в .env и перезапустите сервер"}, 400)
                job = manager.start(scenario)
                if job is None:
                    return self.send_json({"error": "На устройстве уже выполняется сценарий"}, 409)
                return self.send_json(job, 202)
            except (ValueError, UnicodeDecodeError):
                return self.send_json({"error": "Ожидался JSON с полем scenario"}, 400)

    return Handler


def serve(settings: Settings, port: int = 8765):
    if not settings.device:
        raise ValueError("Укажите устройство явно: android-qa web --device emulator-5554")
    if not 1 <= port <= 65535:
        raise ValueError("Port must be from 1 to 65535")
    settings.artifacts.mkdir(parents=True, exist_ok=True)
    url = f"http://127.0.0.1:{port}"
    server = ThreadingHTTPServer(("127.0.0.1", port), create_handler(settings, RunManager(settings), url))
    server.daemon_threads = True
    print(f"Android AI QA web: {url}", flush=True)
    print("Only this computer can connect; press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
