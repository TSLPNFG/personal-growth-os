"""Markdown storage boundary. No database, remote indexing or personal memory reads."""
from datetime import date, datetime
import hashlib
import os
from pathlib import Path
import re
import tempfile
import threading
import uuid

from scripts.pgos import safe_path, linked

KINDS = {
    "goals": ("目标", "goals"),
    "learning": ("学习", "learning"),
    "habits": ("习惯", "habit"),
    "knowledge": ("知识", "knowledge"),
    "journal": ("反思", "reflection"),
    "reflections": ("周复盘", "review"),
}
MAX_RECORD = 256 * 1024
MAX_SEARCH_FILES = 500
MAX_SEARCH_RESULTS = 100


class AppError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def valid_day(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise AppError("日期应为 YYYY-MM-DD。")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise AppError("日期无效。") from None
    return value


class Store:
    def __init__(self, project):
        self.project = Path(project).resolve()
        self.lock = threading.RLock()

    def workspace(self):
        # Validate from project root on every access, including private itself.
        return safe_path(self.project, "private/workspace", False)

    def path(self, relative, exists=True):
        if relative.split("/")[0] not in KINDS or not relative.endswith(".md"):
            raise AppError("记录类型或路径不受支持。")
        path = safe_path(self.workspace(), relative, exists)
        if path.exists() and path.stat().st_nlink > 1:
            raise ValueError("hard-linked records are forbidden")
        return path

    def _paths(self):
        workspace = self.workspace()
        if not workspace.exists():
            return
        for kind in KINDS:
            directory = safe_path(workspace, kind, False)
            if not directory.exists():
                continue
            for folder, dirs, names in os.walk(directory, followlinks=False):
                dirs[:] = [d for d in dirs if not linked(Path(folder) / d) and not d.startswith(".")]
                for name in sorted(names):
                    if name.endswith(".md") and not name.startswith("."):
                        file = Path(folder) / name
                        if not linked(file):
                            relative = file.relative_to(workspace).as_posix()
                            yield relative, self.path(relative)

    @staticmethod
    def identity(relative):
        return hashlib.sha256(relative.encode("utf-8")).hexdigest()[:24]

    def _read(self, relative, path):
        with path.open("rb") as source:
            raw = source.read(MAX_RECORD + 1)
        if len(raw) > MAX_RECORD:
            raise AppError("记录超过 256 KiB，请用文本编辑器拆分后再打开。")
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeError:
            raise AppError("记录不是 UTF-8 文本。") from None
        if "\x00" in content:
            raise AppError("记录包含非文本数据。")
        heading = re.search(r"^# (.+)$", content, re.M)
        stamp = re.search(r"^<!-- pgos-date: (\d{4}-\d{2}-\d{2}) -->$", content, re.M)
        filename_day = re.match(r"\d{4}-\d{2}-\d{2}", path.name)
        day = stamp[1] if stamp else filename_day[0] if filename_day else datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
        try:
            valid_day(day)
        except AppError:
            day = datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
        return {
            "id": self.identity(relative), "kind": relative.split("/")[0],
            "title": heading[1].strip() if heading else path.stem,
            "date": day, "modified": path.stat().st_mtime,
            "content": content, "revision": hashlib.sha256(raw).hexdigest(),
            "relative": relative,
        }

    def get(self, record_id):
        if not isinstance(record_id, str) or not re.fullmatch(r"[a-f0-9]{24}", record_id):
            raise AppError("记录标识无效。")
        with self.lock:
            for relative, path in self._paths():
                if self.identity(relative) == record_id:
                    return self._read(relative, path)
        raise AppError("记录不存在，可能已在外部移动。", 404)

    def list(self, kind="", query="", day="", order="date"):
        if kind and kind not in KINDS:
            raise AppError("未知记录类型。")
        if day:
            valid_day(day)
        if not isinstance(query, str) or len(query) > 200:
            raise AppError("搜索词过长。")
        if order not in {"date", "title"}:
            raise AppError("未知排序方式。")
        records, skipped = [], 0
        counts = {key: 0 for key in KINDS}
        with self.lock:
            for relative, path in self._paths():
                try:
                    record = self._read(relative, path)
                except (OSError, AppError):
                    skipped += 1
                    continue
                counts[record["kind"]] += 1
                if kind and record["kind"] != kind or day and record["date"] != day:
                    continue
                if query.casefold() not in (record["title"] + "\n" + record["content"]).casefold():
                    continue
                summary = {k: v for k, v in record.items() if k not in {"content", "relative", "revision"}}
                lines = [line.strip() for line in record["content"].splitlines()
                         if line.strip() and not line.startswith(("# ", "<!--"))]
                summary["preview"] = " ".join(lines)[:120]
                records.append(summary)
        records.sort(key=(lambda r: r["title"].casefold()) if order == "title" else (lambda r: (r["date"], r["modified"])), reverse=order == "date")
        return {"records": records, "counts": counts, "skipped": skipped}

    @staticmethod
    def _tags(content):
        tags = set()
        for line in content.splitlines():
            match = re.fullmatch(r"\s*标签\s*[:：]\s*(.*?)\s*", line)
            if match:
                tags.update(value.strip().lstrip("#").casefold()
                            for value in re.split(r"[,，]", match[1]) if value.strip())
        return tags

    @staticmethod
    def _snippet(record, query):
        body, title_skipped = [], False
        for line in record["content"].splitlines():
            if line.startswith("<!-- pgos-date:"):
                continue
            if not title_skipped and line.startswith("# "):
                title_skipped = True
                continue
            body.append(line)
        content = "\n".join(body)
        if query:
            match = re.search(re.escape(query), content, re.IGNORECASE)
            if match:
                start = max(0, match.start() - 55)
                end = min(len(content), match.end() + 80)
                return ("…" if start else "") + re.sub(r"\s+", " ", content[start:end]).strip() + ("…" if end < len(content) else "")
        lines = [line.strip() for line in content.splitlines()
                 if line.strip() and not line.startswith(("# ", "<!--"))]
        return " ".join(lines)[:140]

    def search(self, query="", kind="", date_from="", date_to="", tag="", order="date"):
        if not isinstance(query, str) or len(query) > 200:
            raise AppError("搜索词应不超过 200 字符。")
        if kind and kind not in KINDS:
            raise AppError("未知记录类型。")
        if date_from:
            valid_day(date_from)
        if date_to:
            valid_day(date_to)
        if date_from and date_to and date_from > date_to:
            raise AppError("起始日期不能晚于结束日期。")
        if not isinstance(tag, str) or len(tag) > 60:
            raise AppError("标签应不超过 60 字符。")
        if order not in {"date", "title"}:
            raise AppError("未知排序方式。")
        query = query.strip()
        tag = tag.strip().lstrip("#").casefold()
        records, skipped, scanned, truncated = [], 0, 0, False
        with self.lock:
            for relative, path in self._paths():
                if kind and relative.split("/", 1)[0] != kind:
                    continue
                if scanned >= MAX_SEARCH_FILES:
                    truncated = True
                    break
                scanned += 1
                try:
                    record = self._read(relative, path)
                except (OSError, AppError):
                    skipped += 1
                    continue
                if date_from and record["date"] < date_from or date_to and record["date"] > date_to:
                    continue
                if tag and tag not in self._tags(record["content"]):
                    continue
                if query.casefold() not in (record["title"] + "\n" + record["content"]).casefold():
                    continue
                summary = {key: value for key, value in record.items()
                           if key not in {"content", "relative", "revision"}}
                summary["preview"] = self._snippet(record, query)
                records.append(summary)
        records.sort(key=(lambda r: r["title"].casefold()) if order == "title" else (lambda r: (r["date"], r["modified"])), reverse=order == "date")
        total_matches = len(records)
        return {"records": records[:MAX_SEARCH_RESULTS], "matches": total_matches,
                "scanned": scanned, "scan_limited": truncated,
                "result_limited": total_matches > MAX_SEARCH_RESULTS, "skipped": skipped}

    def template(self, kind):
        if kind not in KINDS:
            raise AppError("未知记录类型。")
        template = safe_path(self.project, f"templates/{KINDS[kind][1]}-template.md")
        text = template.read_text(encoding="utf-8-sig")
        text = re.sub(r"^# [^\n]+\n+", "", text, count=1)
        return text.replace("复制到 private/workspace 后填写；不要在公共模板内填写真实信息。", "").lstrip()

    def _write(self, relative, content):
        if not isinstance(content, str) or "\x00" in content or len(content.encode("utf-8")) > MAX_RECORD:
            raise AppError("内容无效或超过 256 KiB。")
        path = self.path(relative, False)
        path.parent.mkdir(parents=True, exist_ok=True)
        path = self.path(relative, False)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=path.parent, prefix=".pgos-", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            self.path(relative, False)
            os.replace(temporary, path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
        return self._read(relative, path)

    def create(self, kind, title, day, body=None):
        if kind not in KINDS:
            raise AppError("未知记录类型。")
        if not isinstance(title, str) or not title.strip() or len(title) > 120 or any(ord(c) < 32 for c in title):
            raise AppError("请输入 1–120 字的单行标题。")
        valid_day(day)
        if body is None:
            body = self.template(kind)
        if not isinstance(body, str):
            raise AppError("内容必须为文本。")
        content = f"<!-- pgos-date: {day} -->\n# {title.strip()}\n\n{body}"
        relative = f"{kind}/{day}-{uuid.uuid4().hex[:12]}.md"
        with self.lock:
            return self._write(relative, content)

    def save(self, record_id, content, revision):
        with self.lock:
            previous = self.get(record_id)
            if not isinstance(revision, str) or previous["revision"] != revision:
                raise AppError("文件已被其他窗口或编辑器修改。请保留当前文本，重新打开后合并。", 409)
            return self._write(previous["relative"], content)

    def trash(self, record_id, revision):
        """Move bytes unchanged; the bucket preserves the original relative path."""
        with self.lock:
            previous = self.get(record_id)
            if not isinstance(revision, str) or previous["revision"] != revision:
                raise AppError("记录已被修改，请重新打开核对后再删除。", 409)
            source = self.path(previous["relative"])
            trash_id = uuid.uuid4().hex
            relative = f".trash/{trash_id}/{previous['relative']}"
            target = safe_path(self.workspace(), relative, False)
            target.parent.mkdir(parents=True, exist_ok=True)
            target = safe_path(self.workspace(), relative, False)
            if target.exists():
                raise AppError("回收站位置冲突，请重试。", 409)
            self.path(previous["relative"])
            os.rename(source, target)
            return {"id": record_id, "trash_id": trash_id, "deleted": True}

    def _trash_entry(self, trash_id):
        if not isinstance(trash_id, str) or not re.fullmatch(r"[a-f0-9]{32}", trash_id):
            raise AppError("回收站记录标识无效。")
        bucket = safe_path(self.workspace(), f".trash/{trash_id}", False)
        if not bucket.is_dir():
            raise AppError("回收站记录不存在或已恢复。", 404)
        found = []
        for folder, dirs, names in os.walk(bucket, followlinks=False):
            for name in dirs + names:
                candidate = Path(folder) / name
                safe_path(self.workspace(), candidate.relative_to(self.workspace()).as_posix(), False)
            for name in names:
                if name.endswith(".md"):
                    path = Path(folder) / name
                    relative = path.relative_to(bucket).as_posix()
                    self.path(relative, False)
                    if path.stat().st_nlink > 1:
                        raise ValueError("hard-linked trash records are forbidden")
                    found.append((relative, path))
        if len(found) != 1:
            raise AppError("回收站记录结构异常，请保留文件并手动检查。", 409)
        relative, source = found[0]
        return self._read(relative, source), source, bucket

    def list_trash(self):
        with self.lock:
            directory = safe_path(self.workspace(), ".trash", False)
            if not directory.exists():
                return {"records": [], "skipped": 0}
            records, skipped = [], 0
            for bucket in directory.iterdir():
                if not re.fullmatch(r"[a-f0-9]{32}", bucket.name):
                    skipped += 1
                    continue
                try:
                    record, _, valid_bucket = self._trash_entry(bucket.name)
                    records.append({"trash_id": bucket.name, "title": record["title"],
                                    "kind": record["kind"], "date": record["date"],
                                    "deleted_at": datetime.fromtimestamp(valid_bucket.stat().st_mtime).isoformat(timespec="seconds")})
                except (OSError, AppError, ValueError):
                    skipped += 1
            records.sort(key=lambda record: record["deleted_at"], reverse=True)
            return {"records": records, "skipped": skipped}

    def restore(self, trash_id):
        with self.lock:
            record, source, bucket = self._trash_entry(trash_id)
            target = self.path(record["relative"], False)
            if target.exists():
                raise AppError("原位置已有文件，未覆盖。请先处理重名文件，再恢复。", 409)
            target.parent.mkdir(parents=True, exist_ok=True)
            self.path(record["relative"], False)
            safe_path(self.workspace(), source.relative_to(self.workspace()).as_posix())
            os.rename(source, target)
            # Only remove empty containers; never recursively delete trash data.
            empty = source.parent
            while empty.is_relative_to(bucket):
                try:
                    empty.rmdir()
                except OSError:
                    break
                empty = empty.parent
            return self._read(record["relative"], target)
