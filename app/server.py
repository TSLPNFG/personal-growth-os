"""Loopback-only HTTP shell. Run: python -B -m app.server"""
import argparse
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import threading
from urllib.parse import parse_qs, urlsplit
import webbrowser

from .ai import Drafts
from .storage import AppError, KINDS, Store

PROJECT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "ui"
ASSETS = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/styles.css": ("styles.css", "text/css")}


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, project, port=0, demo=False, ollama=None):
        self.store = Store(project)
        self.drafts = Drafts(self.store, ollama)
        self.session = secrets.token_urlsafe(32)
        self.demo = demo
        super().__init__(("127.0.0.1", port), Handler)
        self.origin = f"http://127.0.0.1:{self.server_port}"

    def handle_error(self, request, client_address):
        # Never log exceptions, request data or local filesystem paths.
        pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def reply(self, status, data, content_type="application/json"):
        raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def guard(self, api=False):
        if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
            raise AppError("访问来源不受支持。", 403)
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise AppError("已拒绝跨站访问。", 403)
        origin = self.headers.get("Origin")
        if origin is not None and origin != self.server.origin:
            raise AppError("已拒绝跨站访问。", 403)
        if api and not secrets.compare_digest(self.headers.get("X-PGOS-Session", ""), self.server.session):
            raise AppError("应用会话已失效，请重新打开应用地址。", 403)
        if self.command == "POST" and origin != self.server.origin:
            raise AppError("写入请求必须来自应用窗口。", 403)

    def do_GET(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch()

    def dispatch(self):
        try:
            parsed = urlsplit(self.path)
            path = parsed.path
            self.guard(path.startswith("/api/"))
            if self.command == "GET":
                result = self.get(path, parse_qs(parsed.query))
            else:
                if self.headers.get_content_type() != "application/json":
                    raise AppError("请求必须使用 JSON。", 415)
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1024 * 1024:
                    raise AppError("请求长度无效或过大。", 413)
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise AppError("请求格式无效。")
                result = self.post(path, data)
            if result is not None:
                self.reply(200, result)
        except AppError as error:
            self.reply(error.status, {"error": str(error)})
        except (ValueError, OSError, UnicodeError, TypeError):
            self.reply(400, {"error": "无法完成操作。请检查输入、目录权限或文件链接；记录未被自动覆盖。"})
        except Exception:
            self.reply(500, {"error": "本地操作失败。请保留编辑内容并重试。"})

    def get(self, path, query):
        if path in ASSETS:
            file, mime = ASSETS[path]
            raw = (STATIC / file).read_bytes()
            if path == "/":
                raw = raw.replace(b"__SESSION__", self.server.session.encode("ascii"))
            self.reply(200, raw, mime)
            return None
        if path == "/api/info":
            return {"kinds": {key: value[0] for key, value in KINDS.items()}, "demo": self.server.demo}
        if path == "/api/records":
            return self.server.store.list(**{key: query.get(key, [default])[0] for key, default in [("kind", ""), ("query", ""), ("day", ""), ("order", "date")]})
        if path == "/api/record":
            return self.server.store.get(query.get("id", [""])[0])
        if path == "/api/trash":
            return self.server.store.list_trash()
        if path == "/api/models":
            return {"models": self.server.drafts.ollama.models()}
        raise AppError("未找到此入口。", 404)

    def post(self, path, data):
        store, drafts = self.server.store, self.server.drafts
        if path == "/api/create":
            return store.create(data.get("kind"), data.get("title"), data.get("date"))
        if path == "/api/save":
            return store.save(data.get("id"), data.get("content"), data.get("revision"))
        if path == "/api/delete":
            if data.get("confirmed") is not True:
                raise AppError("请先确认将记录移到回收站。")
            result = store.trash(data.get("id"), data.get("revision"))
            drafts.invalidate_record(data.get("id"))
            return result
        if path == "/api/restore":
            return store.restore(data.get("trash_id"))
        if path == "/api/ai/prepare":
            return drafts.prepare(data.get("ids"))
        if path == "/api/ai/generate":
            return drafts.generate(data.get("id"), data.get("model"), data.get("custom_prompt", ""))
        if path == "/api/ai/confirm":
            return drafts.confirm(data.get("id"), data.get("confirmed"), data.get("text"))
        if path == "/api/shutdown":
            threading.Timer(0.2, self.server.shutdown).start()
            return {"stopped": True}
        raise AppError("未找到此入口。", 404)


def launch(url):
    if os.name == "nt":
        candidates = [shutil.which("msedge")]
        for variable in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
            base = os.environ.get(variable)
            if base:
                candidates.append(str(Path(base) / "Microsoft/Edge/Application/msedge.exe"))
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                subprocess.Popen([candidate, "--app=" + url, "--inprivate", "--no-first-run"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
    webbrowser.open(url)


def seed_demo(project):
    (project / "templates").mkdir(parents=True)
    for path in (PROJECT / "templates").glob("*.md"):
        shutil.copyfile(path, project / "templates" / path.name)
    store = Store(project)
    day = date.today().isoformat()
    store.create("goals", "虚构示例 · 完成一张植物观察卡", day, "完成证据：一页观察卡。\n下一步：记录叶片变化。\n行动状态：Suggested。\n")
    store.create("learning", "虚构示例 · 一次观察练习", day, "实际产出：三条观察。\n卡点：描述还不够具体。\n掌握程度：待验证。\n")
    store.create("journal", "虚构示例 · 从一个小行动开始", day, "## 事件\n整理观察材料。\n\n## 事实（用户自述）\n完成了三条记录。\n\n## 解释（待验证）\n较小的任务可能更容易启动。\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0, help="0 chooses a free local port")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--demo", action="store_true", help="isolated, disposable synthetic workspace")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("Port must be between 0 and 65535")
    temporary = tempfile.TemporaryDirectory(prefix="pgos-demo-") if args.demo else None
    project = Path(temporary.name) if temporary else PROJECT
    server = None
    try:
        if args.demo:
            seed_demo(project)
        server = LocalServer(project, args.port, args.demo)
        print(f"Personal Growth OS: {server.origin}", flush=True)
        print("DEMO: synthetic records only." if args.demo else "Local workspace mode.", flush=True)
        print("Use the Exit button or Ctrl+C to stop the local service.", flush=True)
        if not args.no_browser:
            try:
                launch(server.origin)
            except OSError:
                print("Open the local address above in your browser.", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    except OSError:
        print("Cannot start local service; check the port and directory permissions.")
        return 1
    finally:
        if server:
            server.server_close()
        if temporary:
            temporary.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
