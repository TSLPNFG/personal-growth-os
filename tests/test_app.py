"""Synthetic-only application tests. No real workspace or Ollama needed."""
from datetime import date
import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from app.ai import Drafts, Ollama
from app.server import LocalServer
from app.storage import AppError, KINDS, Store
from scripts.pgos import export as export_public

PROJECT = Path(__file__).resolve().parents[1]


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pgos-test-")
        self.root = Path(self.tmp.name)
        shutil.copytree(PROJECT / "templates", self.root / "templates")
        self.store = Store(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def record(self, kind="learning", title="虚构练习", day="2025-01-02", body="观察纸飞机折痕。"):
        return self.store.create(kind, title, day, body)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob("*.md")}


class StoreTests(Fixture):
    def test_public_export_contains_app_without_private_data_or_history(self):
        candidate = self.root / "candidate"
        manifest = json.loads((PROJECT / "config/public-files.json").read_text(encoding="utf-8"))
        for relative in manifest:
            target = candidate / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PROJECT / relative, target)
        Store(candidate).create("journal", "虚构私有记录", "2025-01-02", "private synthetic content")
        (candidate / ".git").mkdir()
        (candidate / ".git/config").write_text("synthetic history", encoding="utf-8")
        target, count = export_public(candidate)
        actual = sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())
        self.assertEqual(actual, sorted(manifest))
        self.assertEqual(count, len(manifest))
        self.assertTrue((target / "app/server.py").is_file())
        self.assertFalse((target / "private").exists())
        self.assertFalse((target / ".git").exists())

    def test_create_all_templates_reopen_and_save(self):
        for kind in KINDS:
            record = self.store.create(kind, "虚构标题", "2025-01-02")
            self.assertIn(self.store.template(kind), record["content"])
            reopened = Store(self.root).get(record["id"])
            self.assertEqual(record, reopened)
            updated = self.store.save(record["id"], record["content"] + "\n补充观察。", record["revision"])
            self.assertIn("补充观察", Store(self.root).get(record["id"])["content"])
            self.assertNotEqual(record["revision"], updated["revision"])
        self.assertEqual(len(self.store.list()["records"]), 6)

    def test_search_type_date_title_and_counts(self):
        self.record(title="Beta", body="观察折痕")
        self.record("goals", "Alpha", "2025-01-03", "虚构目标")
        self.assertEqual(len(self.store.list(query="折痕")["records"]), 1)
        self.assertEqual(len(self.store.list(query="ALPHA", kind="goals", day="2025-01-03")["records"]), 1)
        self.assertEqual([r["title"] for r in self.store.list(order="title")["records"]], ["Alpha", "Beta"])
        self.assertEqual(self.store.list()["records"][0]["date"], "2025-01-03")
        self.assertEqual(self.store.list()["counts"]["learning"], 1)

    def test_on_demand_search_combines_filters_and_preserves_markdown(self):
        target = self.record("learning", "虚构纸飞机", "2025-01-03",
                             "标签：练习，纸艺\n观察 <img src=x onerror=alert(1)> 折痕。")
        self.record("learning", "较早纸飞机", "2025-01-01", "标签：练习\n观察折痕。")
        self.record("goals", "另一种纸飞机", "2025-01-03", "标签：练习\n观察折痕。")
        before = self.snapshot()
        found = self.store.search(query="折痕", kind="learning", date_from="2025-01-02",
                                  date_to="2025-01-04", tag="纸艺")
        self.assertEqual(found["matches"], 1)
        self.assertEqual(found["records"][0]["id"], target["id"])
        self.assertEqual(found["records"][0]["date"], "2025-01-03")
        self.assertIn("<img src=x onerror=alert(1)>", found["records"][0]["preview"])
        self.assertNotIn("pgos-date", found["records"][0]["preview"])
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.store.search(tag="#纸艺")["matches"], 1)
        self.assertEqual(self.store.search(query="不存在")["matches"], 0)
        self.record("learning", "另一条虚构记录", "2025-01-04", "# 正文一级标题\n内容")
        self.assertIn("正文一级标题", self.store.search(query="正文一级标题")["records"][0]["preview"])
        with self.assertRaises(AppError):
            self.store.search(date_from="2025-02-01", date_to="2025-01-01")
        with self.assertRaises(AppError):
            self.store.search(tag="x" * 61)

    def test_search_scan_limit_is_reported(self):
        for index in range(3):
            self.record(title=f"虚构记录 {index}")
        with patch("app.storage.MAX_SEARCH_FILES", 2):
            result = self.store.search()
        self.assertEqual(result["scanned"], 2)
        self.assertTrue(result["scan_limited"])
        self.assertEqual(result["matches"], 2)
        with patch("app.storage.MAX_SEARCH_RESULTS", 1):
            result = self.store.search()
        self.assertEqual(result["matches"], 3)
        self.assertEqual(len(result["records"]), 1)
        self.assertTrue(result["result_limited"])

    def test_external_legacy_markdown_and_private_memory_scope(self):
        root = self.root / "private/workspace"
        (root / "journal").mkdir(parents=True)
        (root / "journal/current.md").write_text("# 虚构旧记录\n已有内容。", encoding="utf-8")
        (root / "memory").mkdir()
        (root / "memory/current-model.md").write_text("不得读取的虚构记忆", encoding="utf-8")
        listed = self.store.list()
        self.assertEqual(len(listed["records"]), 1)
        self.assertEqual(self.store.list(query="虚构记忆")["records"], [])
        record = self.store.get(listed["records"][0]["id"])
        self.assertEqual(record["content"], (root / "journal/current.md").read_bytes().decode("utf-8"))

    def test_external_conflict_does_not_overwrite(self):
        record = self.record()
        path = self.root / "private/workspace" / record["relative"]
        path.write_text("# 外部虚构编辑\n新内容", encoding="utf-8")
        with self.assertRaises(AppError) as error:
            self.store.save(record["id"], "overwrite", record["revision"])
        self.assertEqual(error.exception.status, 409)
        self.assertIn("新内容", path.read_text(encoding="utf-8"))

    def test_failed_atomic_replace_preserves_original(self):
        record = self.record()
        before = self.snapshot()
        with patch("app.storage.os.replace", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError):
                self.store.save(record["id"], "new text", record["revision"])
        self.assertEqual(before, self.snapshot())
        self.assertEqual(list(self.root.rglob("*.tmp")), [])

    def test_paths_ids_dates_and_disallowed_types(self):
        for candidate in ["../outside.md", "journal/../../outside.md", "journal/../outside.md", "/outside.md", "journal/a:stream.md", "journal\\outside.md", "memory/current-model.md"]:
            with self.subTest(candidate=candidate), self.assertRaises((AppError, ValueError)):
                self.store.path(candidate, False)
        for identity in ["../outside", "journal/current.md", None]:
            with self.assertRaises(AppError):
                self.store.get(identity)
        with self.assertRaises(AppError):
            self.record(day="2025-02-30")
        with self.assertRaises(AppError):
            self.record(kind="memory")

    def test_title_is_never_a_filename(self):
        record = self.record(title="../虚构标题")
        self.assertNotIn("..", record["relative"])
        self.assertIn("../虚构标题", record["content"])

    def test_hardlink_rejected(self):
        outside = self.root / "outside.md"
        outside.write_text("synthetic outside", encoding="utf-8")
        target = self.root / "private/workspace/journal/linked.md"
        target.parent.mkdir(parents=True)
        os.link(outside, target)
        with self.assertRaises(ValueError):
            self.store.path("journal/linked.md")

    @unittest.skipUnless(os.name == "nt", "Windows-only junction boundary")
    def test_private_junction_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(self.root / "private"), str(outside)], capture_output=True)
        self.assertEqual(result.returncode, 0)
        with self.assertRaises(ValueError):
            self.record()
        self.assertEqual(list(outside.iterdir()), [])


class FakeOllama:
    def __init__(self):
        self.calls = []

    def models(self):
        return ["synthetic-local"]

    def generate(self, model, messages):
        self.calls.append((model, messages))
        return "## 解释（待验证）\n小任务可能更容易开始。\n下一步：Suggested。"


class DraftTests(Fixture):
    def test_preview_selected_snapshot_and_confirmation_only(self):
        first = self.record(body="已选择的虚构材料")
        second = self.record(title="不应读取", body="未选择的虚构材料")
        backend = FakeOllama()
        drafts = Drafts(self.store, backend)
        before = self.snapshot()
        prepared = drafts.prepare([first["id"]])
        self.assertEqual(backend.calls, [])
        self.assertIn("已选择的虚构材料", prepared["input"])
        self.assertNotIn("未选择的虚构材料", prepared["input"])
        self.assertEqual(before, self.snapshot())
        self.store.save(first["id"], "# 已变化\n较晚内容", first["revision"])
        before = self.snapshot()
        result = drafts.generate(prepared["id"], "synthetic-local")
        self.assertFalse(result["saved"])
        self.assertEqual(before, self.snapshot())
        self.assertIn("已选择的虚构材料", backend.calls[0][1][1]["content"])
        self.assertNotIn("较晚内容", backend.calls[0][1][1]["content"])
        with self.assertRaises(AppError):
            drafts.confirm(prepared["id"], False, result["draft"])
        self.assertEqual(before, self.snapshot())
        saved = drafts.confirm(prepared["id"], True, result["draft"])
        self.assertEqual(saved["kind"], "journal")
        self.assertIn("来源：助手推断", saved["content"])
        self.assertIn("> ## 解释", saved["content"])
        self.assertEqual(self.store.get(second["id"])["content"], second["content"])
        self.assertFalse((self.root / "private/workspace/memory").exists())
        with self.assertRaises(AppError):
            drafts.confirm(prepared["id"], True, result["draft"])

    def test_invalid_scope_and_expiry(self):
        draft = Drafts(self.store, FakeOllama())
        for ids in [[], ["x"] * 6, None]:
            with self.assertRaises(AppError):
                draft.prepare(ids)
        record = self.record()
        prepared = draft.prepare([record["id"]])
        draft.items[prepared["id"]]["expires"] = 0
        with self.assertRaises(AppError):
            draft.generate(prepared["id"], "synthetic-local")

    def test_failed_generation_writes_nothing(self):
        backend = FakeOllama()
        backend.generate = lambda *args: (_ for _ in ()).throw(AppError("offline", 503))
        draft = Drafts(self.store, backend)
        prepared = draft.prepare([self.record()["id"]])
        before = self.snapshot()
        with self.assertRaises(AppError):
            draft.generate(prepared["id"], "synthetic-local")
        self.assertEqual(before, self.snapshot())


class OllamaTests(unittest.TestCase):
    def test_cloud_tags_filtered_and_remote_show_blocks_content(self):
        client = Ollama()
        with patch.object(client, "request", return_value={"models": [
            {"name": "local", "size": 100}, {"name": "remote", "size": 100, "remote_host": "upstream"},
            {"name": "model:cloud", "size": 100}]}):
            self.assertEqual(client.models(), ["local"])
        with patch.object(client, "models", return_value=["local"]), patch.object(client, "request", return_value={"remote_host": "upstream", "model_info": {"general.architecture": "x"}}) as request:
            with self.assertRaises(AppError):
                client.generate("local", [{"role": "user", "content": "synthetic"}])
            self.assertEqual(request.call_count, 1)
            self.assertEqual(request.call_args.args[0], "/api/show")

    def test_unavailable_ollama_returns_safe_error(self):
        with patch("app.ai.http.client.HTTPConnection", side_effect=OSError("unavailable")):
            with self.assertRaises(AppError) as error:
                Ollama().models()
            self.assertEqual(error.exception.status, 503)

    def test_fixed_loopback_transport_no_redirect(self):
        with patch("app.ai.http.client.HTTPConnection") as connection:
            response = connection.return_value.getresponse.return_value
            response.status = 302
            response.read.return_value = b""
            with self.assertRaises(AppError):
                Ollama().request("/api/tags")
            connection.assert_called_once_with("127.0.0.1", 11434, timeout=5)
            self.assertEqual(connection.return_value.request.call_count, 1)


class HTTPTests(Fixture):
    def test_custom_prompt_reaches_model_without_changing_snapshot_or_saving(self):
        record = self.record()
        status, raw, _ = self.request("POST", "/api/ai/prepare", {"ids": [record["id"]]})
        self.assertEqual(status, 200)
        prepared = json.loads(raw)
        before = self.snapshot()
        payload = {"id": prepared["id"], "model": "synthetic-local"}
        self.assertEqual(self.request("POST", "/api/ai/generate", payload)[0], 200)
        original = self.fake.calls[-1][1]
        for prompt in ["", " \n\t", "重点分析折纸练习中的阻碍。\n给出一个可验证的下一步。", "改为分析练习节奏。", ""]:
            with self.subTest(prompt=prompt):
                payload["custom_prompt"] = prompt
                status, raw, _ = self.request("POST", "/api/ai/generate", payload)
                self.assertEqual(status, 200)
                self.assertFalse(json.loads(raw)["saved"])
                expected = original + ([{"role": "user", "content": "额外分析要求：\n" + prompt}] if prompt.strip() else [])
                self.assertEqual(self.fake.calls[-1][1], expected)
                self.assertEqual(before, self.snapshot())

    def test_invalid_custom_prompt_is_rejected_before_model_call(self):
        record = self.record()
        _, raw, _ = self.request("POST", "/api/ai/prepare", {"ids": [record["id"]]})
        prepared = json.loads(raw)
        for prompt in [None, [], 123, "x" * 24001]:
            with self.subTest(prompt_type=type(prompt).__name__):
                status, _, _ = self.request("POST", "/api/ai/generate", {
                    "id": prepared["id"], "model": "synthetic-local", "custom_prompt": prompt})
                self.assertEqual(status, 400)
        self.assertEqual(self.fake.calls, [])

    def setUp(self):
        super().setUp()
        self.fake = FakeOllama()
        self.server = LocalServer(self.root, ollama=self.fake)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        super().tearDown()

    def request(self, method, path, data=None, authorized=True, origin=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        headers = {"Content-Type": "application/json", "Origin": origin or self.server.origin}
        if authorized:
            headers["X-PGOS-Session"] = self.server.session
        connection.request(method, path, body=json.dumps(data) if data is not None else None, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        status = response.status
        cache = response.getheader("Cache-Control")
        connection.close()
        return status, raw, cache

    def test_http_create_save_reopen_search_without_ollama(self):
        self.fake.models = lambda: (_ for _ in ()).throw(AppError("unavailable", 503))
        self.assertEqual(self.request("GET", "/api/models")[0], 503)
        status, raw, cache = self.request("POST", "/api/create", {"kind": "learning", "title": "虚构风筝练习", "date": "2025-01-02"})
        self.assertEqual((status, cache), (200, "no-store"))
        record = json.loads(raw)
        record["content"] += "\n风筝尾翼观察"
        self.assertEqual(self.request("POST", "/api/save", record)[0], 200)
        status, raw, _ = self.request("GET", "/api/record?id=" + record["id"])
        self.assertEqual(status, 200)
        self.assertIn("风筝尾翼", json.loads(raw)["content"])
        status, raw, _ = self.request("GET", "/api/records?kind=learning&day=2025-01-02")
        self.assertEqual(len(json.loads(raw)["records"]), 1)

    def test_http_search_combines_filters(self):
        self.record("learning", "虚构练习", "2025-01-02", "标签：观察\n纸飞机折痕")
        self.record("goals", "虚构目标", "2025-01-02", "标签：观察\n纸飞机折痕")
        status, raw, _ = self.request("GET", "/api/search?query=%E6%8A%98%E7%97%95&kind=learning&date_from=2025-01-01&date_to=2025-01-03&tag=%E8%A7%82%E5%AF%9F")
        self.assertEqual(status, 200)
        result = json.loads(raw)
        self.assertEqual(result["matches"], 1)
        self.assertEqual(result["records"][0]["kind"], "learning")
        self.assertEqual(self.request("GET", "/api/search?date_from=2025-02-01&date_to=2025-01-01")[0], 400)

    def test_api_auth_origin_and_private_files(self):
        self.assertEqual(self.request("GET", "/api/records", authorized=False)[0], 403)
        self.assertEqual(self.request("POST", "/api/create", {}, origin="http://untrusted.invalid")[0], 403)
        self.assertEqual(self.request("GET", "/private/workspace/journal/current.md")[0], 404)
        self.assertEqual(self.request("GET", "/api/record?id=../../outside")[0], 400)

    def test_http_draft_confirm_roundtrip(self):
        record = self.record()
        status, raw, _ = self.request("POST", "/api/ai/prepare", {"ids": [record["id"]]})
        prepared = json.loads(raw)
        before = self.snapshot()
        status, raw, _ = self.request("POST", "/api/ai/generate", {"id": prepared["id"], "model": "synthetic-local"})
        self.assertEqual(status, 200)
        self.assertEqual(before, self.snapshot())
        payload = {"id": prepared["id"], "confirmed": False, "text": json.loads(raw)["draft"]}
        self.assertEqual(self.request("POST", "/api/ai/confirm", payload)[0], 400)
        payload["confirmed"] = True
        self.assertEqual(self.request("POST", "/api/ai/confirm", payload)[0], 200)


if __name__ == "__main__":
    unittest.main()
