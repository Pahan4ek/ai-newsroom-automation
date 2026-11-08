"""Local stand-in for RSS feeds, an OpenAI-compatible LLM and the Telegram Bot API.
Every request is appended to requests.jsonl so the test can assert on it."""
import json, sys, threading
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG = sys.argv[2]
lock = threading.Lock()
state = {"updates": [], "msg_id": 100}


def rss():
    now = datetime.now(timezone.utc)
    items = ""
    for i, (t, d) in enumerate([("Test story one", "First body & <b>tags</b>"), ("Second \"quoted\" story", "Second body"), ("Third story", "Third body")]):
        items += (f"<item><title><![CDATA[{t}]]></title><link>https://example.com/s{i}</link>"
                  f"<description><![CDATA[{d}]]></description><pubDate>{format_datetime(now - timedelta(minutes=5 + i))}</pubDate></item>")
    old = format_datetime(now - timedelta(days=3))
    items += f"<item><title>Old story</title><link>https://example.com/old</link><description>x</description><pubDate>{old}</pubDate></item>"
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>{items}</channel></rss>'


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _log(self, body):
        with lock, open(LOG, "a") as f:
            f.write(json.dumps({"method": self.command, "path": self.path, "auth": self.headers.get("Authorization"), "body": body}, ensure_ascii=False) + "\n")

    def do_GET(self):
        self._log(None)
        if self.path.startswith("/rss"):
            return self._send(200, rss(), "application/rss+xml")
        if "/getUpdates" in self.path:
            with lock:
                ups, state["updates"] = state["updates"], []
            return self._send(200, {"ok": True, "result": ups})
        self._send(404, {"ok": False})

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0)
        try: body = json.loads(raw or b"{}")
        except Exception: body = raw.decode(errors="replace")
        self._log(body)
        if self.path == "/_control/updates":
            with lock: state["updates"] = body
            return self._send(200, {"ok": True})
        if self.path.endswith("/v1/chat/completions"):
            msgs = body.get("messages", []) if isinstance(body, dict) else []
            text = " ".join(m.get("content", "") for m in msgs)
            if "translator" in text:
                n = json.loads(text[text.index("INPUT:") + 6:].strip())
                out = json.dumps([{"id": x["id"], "ru_title": "RU " + x["title"], "ru_text": "RU " + x["text"], "sum": "s"} for x in n])
                content = "Here you go:\n" + out
            else:
                content = "Короткий комментарий <без> разметки."
            return self._send(200, {"choices": [{"message": {"role": "assistant", "content": content}}]})
        if "/bot" in self.path:
            with lock:
                state["msg_id"] += 1
                mid = state["msg_id"]
            return self._send(200, {"ok": True, "result": {"message_id": mid} if self.path.endswith("sendMessage") else True})
        self._send(404, {"ok": False})


ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
