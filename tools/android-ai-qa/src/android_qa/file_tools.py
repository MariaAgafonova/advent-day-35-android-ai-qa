"""Python port of day 34's bounded file policy and hash/diff staging."""
from pathlib import Path
import difflib
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import pathspec
from .models import QAError

EXCLUDED = {".git", ".env", ".tools", ".cache", ".venv", "build", "dist", "target", "node_modules", "vendor", ".gradle", ".kotlin", ".idea", ".aws", ".ssh", ".codex", ".agents", "artifacts", "__pycache__"}
EXT = {".md", ".txt", ".kt", ".kts", ".java", ".xml", ".py", ".toml", ".yaml", ".yml", ".json", ".properties"}
def digest(raw): return hashlib.sha256(raw).hexdigest()

class Files:
    def __init__(self, root: Path, report=None):
        self.root = root.resolve()
        self.report = report
        self.reads = {}
        rules = []
        for name in (".gitignore", ".assistantignore"):
            p = self.root / name
            if p.is_file() and not p.is_symlink(): rules += p.read_text(encoding="utf-8").splitlines()
        self.ignore = pathspec.PathSpec.from_lines("gitwildmatch", rules)

    def checked(self, relative, write=False):
        p = Path(relative)
        if p.is_absolute() or ".." in p.parts or ":" in str(p) or "\\" in str(relative): raise QAError("files", "Only normalized relative paths allowed")
        lower = [s.lower() for s in p.parts]
        if any(s in EXCLUDED for s in lower) or any(re.search(r"(^\.env|secret|credential|password|token|\.pem$|\.key$|keystore|\.jks$)",s) for s in lower) or p.name == "local.properties": raise QAError("files", "Excluded file")
        if p.suffix.lower() not in EXT or self.ignore.match_file(p.as_posix()): raise QAError("files", "Ignored/non-text file")
        target = self.root / p
        for part in [target, *target.parents]:
            if part == self.root: break
            if part.is_symlink() or getattr(part, "is_junction", lambda: False)(): raise QAError("files", "Links/junctions denied")
        if not target.resolve().is_relative_to(self.root): raise QAError("files", "Outside project")
        if write and (not p.parts or p.parts[0] != "qa" or p.suffix not in {".md", ".yaml", ".yml"}): raise QAError("files", "Writes restricted to qa/")
        if target.exists() and target.stat().st_nlink > 1: raise QAError("files", "Hardlinks denied")
        return target

    def list(self):
        result = []
        for directory, dirs, files in os.walk(self.root, followlinks=False):
            dirs[:] = [d for d in dirs if d.lower() not in EXCLUDED and not (Path(directory)/d).is_symlink() and not getattr(Path(directory)/d,"is_junction",lambda:False)()]
            for name in files:
                relative = (Path(directory)/name).relative_to(self.root).as_posix()
                try: self.checked(relative)
                except QAError: continue
                result.append(relative)
                if len(result) >= 3000: return sorted(result)
        return sorted(result)

    def read(self, relative, start=1, end=180):
        path = self.checked(relative)
        if path.stat().st_size > 256000: raise QAError("files", "File exceeds 256 KB")
        raw = path.read_bytes()
        if b"\0" in raw: raise QAError("files", "Binary file")
        lines = raw.decode("utf-8-sig").splitlines()
        if start < 1 or end < start or end-start > 250: raise QAError("files", "Invalid line range")
        result = {"path": relative, "sha256": digest(raw), "start": start, "end": min(end,len(lines)), "total_lines": len(lines), "text": "\n".join(lines[start-1:end])}
        self.reads[relative] = {k:v for k,v in result.items() if k != "text"}
        if self.report: self.report.event("file_read", **result)
        return result

    def search(self, query):
        words = re.findall(r"[\w]{2,40}",query.lower())[:16]
        if not words: return []
        # Day 33 FTS retrieval ported to stdlib SQLite, no external embedding service.
        db = sqlite3.connect(":memory:")
        try:
            db.execute("CREATE VIRTUAL TABLE docs USING fts5(path UNINDEXED, text, tokenize='unicode61')")
            for rel in self.list():
                path = self.checked(rel)
                if path.stat().st_size > 256000: continue
                try: text = path.read_text(encoding="utf-8-sig")
                except UnicodeError: continue
                db.execute("INSERT INTO docs VALUES (?,?)", (rel,text))
            expression = " OR ".join('"'+w+'"*' for w in words)
            rows = db.execute("SELECT path,snippet(docs,1,'[',']','...',32) FROM docs WHERE docs MATCH ? ORDER BY bm25(docs) LIMIT 8",(expression,)).fetchall()
            return [{"path":p,"excerpt":t} for p,t in rows]
        finally: db.close()

    def stage(self, relative, content, directory):
        path = self.checked(relative, write=True)
        original = path.read_bytes() if path.exists() else None
        item = {"path":relative, "original_hash":digest(original) if original is not None else None, "new_hash":digest(content.encode()), "content":content}
        directory.mkdir(parents=True,exist_ok=True)
        (directory/"proposal.json").write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding="utf-8")
        patch = "".join(difflib.unified_diff((original.decode("utf-8") if original else "").splitlines(True),content.splitlines(True),fromfile="a/"+relative,tofile="b/"+relative))
        (directory/"changes.patch").write_text(patch,encoding="utf-8")
        return patch

    def apply(self, directory):
        item = json.loads((directory/"proposal.json").read_text(encoding="utf-8"))
        path = self.checked(item["path"],write=True)
        original = path.read_bytes() if path.exists() else None
        if (digest(original) if original is not None else None) != item["original_hash"]: raise QAError("conflict","File changed since proposal")
        if digest(item["content"].encode()) != item["new_hash"]: raise QAError("conflict","Proposal hash mismatch")
        dirty = subprocess.run(["git","-C",str(self.root),"status","--porcelain","--",item["path"]],capture_output=True,text=True)
        if dirty.stdout.strip(): raise QAError("conflict","User changes present; not overwriting")
        path.parent.mkdir(parents=True,exist_ok=True)
        temp = path.with_suffix(path.suffix+".qa-tmp")
        if temp.exists(): raise QAError("conflict","Temporary file already exists")
        temp.write_text(item["content"],encoding="utf-8")
        if (digest(path.read_bytes()) if path.exists() else None) != item["original_hash"]:
            temp.unlink(); raise QAError("conflict","Concurrent file change")
        temp.replace(path)
        return item["path"]
