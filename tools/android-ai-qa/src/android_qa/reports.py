from pathlib import Path
import json
import re
import uuid
from datetime import datetime, timezone
from .models import Check, now

def redact(value):
    if isinstance(value, dict):
        return {k: redact(v) for k,v in value.items() if k.lower() not in {"api_key", "authorization", "reasoning_content", "reasoning", "password"}}
    if isinstance(value, list): return [redact(v) for v in value]
    if isinstance(value, str): return re.sub(r"\bsk-[A-Za-z0-9_-]{10,}", "[REDACTED]", value)
    return value

class Report:
    def __init__(self, base: Path, goal: str, settings, scenario="run"):
        self.id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
        self.path = base / self.id
        self.path.mkdir(parents=True, exist_ok=False)
        for d in ("screenshots", "hierarchy", "logs", "generated-flows", "proposals"):
            (self.path / d).mkdir()
        self.checks: list[Check] = []
        self.actions = []
        self.metadata = {"run_id": self.id, "started": now(), "goal": goal, "scenario": scenario, "settings": settings.public(), "status": "running", "real_mcp": False, "real_deepseek": False}
        self.save()

    def json(self, name, value):
        target = self.path / name
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(redact(value), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        tmp.replace(target)

    def event(self, kind, **data):
        if kind=="action": self.actions.append(data)
        with (self.path / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(redact({"timestamp": now(), "kind": kind, **data}), ensure_ascii=False, default=str) + "\n")

    def add(self, check):
        self.checks.append(check)
        self.event("check", **check.model_dump())
        self.save()

    def save(self):
        self.json("run.json", self.metadata)
        self.json("checks.json", [c.model_dump() for c in self.checks])
        lines = ["# Android AI QA", "", f"Цель: {self.metadata['goal']}", "", f"Результат: **{self.metadata['status']}**", "", f"Запуск: `{self.id}`", "", "| Проверка | Статус | Ожидалось | Получено |", "|---|---|---|---|"]
        for c in self.checks:
            clean = lambda s: str(s).replace("|", "\\|").replace("\n", " ")
            lines.append("| " + " | ".join(map(clean, [c.name, c.status, c.expected, c.actual])) + " |")
        if self.actions:
            lines += ["", "## Шаги воспроизведения", "", "| Шаг | Действие | Элемент / значение |", "|---|---|---|"]
            for action in self.actions:
                a=action["action"]
                lines.append(f"| {action['step']} | {a['kind']} | {str(action.get('target') or a.get('text') or '').replace('|','/')} |")
        for c in self.checks:
            if c.evidence:
                lines += ["", f"**{c.name}**: " + ", ".join(f"[{p}]({p.replace(chr(92), '/')})" for p in c.evidence)]
        lines += ["", "## Достоверность", "", "passed означает проверенный предикат после действия. Сбой инструмента не является багом приложения. Визуальные подозрения требуют подтверждения.", "", "Метаданные и ограничения: [run.json](run.json). Последовательность действий: [events.jsonl](events.jsonl)."]
        if self.metadata.get("error"): lines += ["", "Причина остановки: " + self.metadata["error"]]
        flow=self.metadata.get("flow")
        if isinstance(flow,dict): lines += ["", "## Повторяемый тест", "", "Статус replay: **"+flow["status"]+"**. "+str(flow.get("reason") or ""), "", "Файл: `"+flow["path"]+"`."]
        if self.metadata.get("cleanup"): lines += ["", "Очистка: "+self.metadata["cleanup"]]
        lines += ["", "## Причина и степень подтверждения", "", "Нарушение ожидаемого результата и его причина оцениваются отдельно. Автоматическое исправление Android-кода не выполняется. Прочитанные исходники и хеши доступны в research.json, если исходники предоставлены."]
        (self.path / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def finish(self, status, **extra):
        self.metadata.update(status=status, finished=now(), **extra)
        self.save()
