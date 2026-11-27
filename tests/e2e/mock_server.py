"""Local stand-in for RSS feeds, an OpenAI-compatible LLM and the Telegram Bot API.
Every request is appended to requests.jsonl so the test can assert on it."""
import json, sys, threading
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG = sys.argv[2]
lock = threading.Lock()
state = {"updates": [], "msg_id": 100, "llm_mode": "normal"}


def rss():
    now = datetime.now(timezone.utc)
    items = ""
    stories = [
        ("Test story one", "First body & <b>tags</b>", "https://example.com/s0?param=1&amp;ref=news", 5),
        ("Second \"quoted\" story", "Second body", "https://example.com/s1", 6),
        ("Third story", "Third body", "https://example.com/s2", 7),
        ("Rejected story", "Rejected body", "https://example.com/s3?utm_medium=feed#top", 8),
    ]
    for t, d, link, mins in stories:
        items += (f"<item><title><![CDATA[{t}]]></title><link>{link}</link>"
                  f"<description><![CDATA[{d}]]></description><pubDate>{format_datetime(now - timedelta(minutes=mins))}</pubDate></item>")
    old = format_datetime(now - timedelta(days=3))
    items += f"<item><title>Old story</title><link>https://example.com/old</link><description>x</description><pubDate>{old}</pubDate></item>"
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>{items}</channel></rss>'


def rss_dup():
    now = datetime.now(timezone.utc)
    link = "https://example.com/s0/?utm_source=rss&amp;fbclid=123&amp;param=1#frag"
    pub = format_datetime(now - timedelta(minutes=5, seconds=10))
    item = (f"<item><title><![CDATA[Test story one (dup)]]></title><link>{link}</link>"
            f"<description><![CDATA[Dup body]]></description><pubDate>{pub}</pubDate></item>")
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>t2</title>{item}</channel></rss>'


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
        if self.path.startswith("/rss2"):
            return self._send(200, rss_dup(), "application/rss+xml")
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
        if self.path == "/_control/llm":
            with lock: state["llm_mode"] = body.get("mode", "normal") if isinstance(body, dict) else "normal"
            return self._send(200, {"ok": True})
        if self.path.endswith("/v1/chat/completions"):
            with lock: llm_mode = state["llm_mode"]
            if llm_mode == "error":
                return self._send(500, {"error": "mock llm failure"})
            if llm_mode == "garbage":
                return self._send(200, {"choices": [{"message": {"role": "assistant", "content": "<think>checking [0, 1]</think>Sorry, I cannot process JSON right now."}}]})
            msgs = body.get("messages", []) if isinstance(body, dict) else []
            text = " ".join(m.get("content", "") for m in msgs)
            if "translator" in text:
                n = json.loads(text[text.index("INPUT:") + 6:].strip())
                selected = [
                    {"id": str(x["id"]), "ru_title": "RU " + x["title"], "ru_text": "RU " + x["text"]}
                    for x in n
                    if x.get("title") != "Rejected story"
                ]
                out = json.dumps({"items": selected}, ensure_ascii=False)
                content = "<think>internal [99] thoughts</think>\n```json\n" + out + "\n```"
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
