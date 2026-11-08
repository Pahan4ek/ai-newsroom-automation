#!/usr/bin/env bash
# End-to-end run of all four workflows on a real n8n with a local mock for RSS, the LLM and the Telegram Bot API.
#
#   npm i -g n8n@2.46.6      # needs Node.js >= 24
#   tests/e2e/run.sh         # or N8N=/path/to/n8n tests/e2e/run.sh
#
# What it changes in its private copy of the workflows (the repo files are not touched):
#   - https://api.telegram.org/ -> the mock, and the feed list -> one mock feed
#   - a test-only webhook next to the schedule triggers of 01 and 03, so a run can be started on demand
set -euo pipefail
cd "$(dirname "$0")/../.."
N8N=${N8N:-n8n}
PORT=5690 MOCK_PORT=8999
T=$(mktemp -d)
mkdir -p "$T/workflows" "$T/home"
: > "$T/requests.jsonl"
echo "workdir $T"

python3 - workflows "$T/workflows" "$MOCK_PORT" <<'EOF'
import json, sys, pathlib
src, dst, port = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
for f in src.glob("*.json"):
    d = json.loads(f.read_text(encoding="utf-8").replace("https://api.telegram.org/", f"http://127.0.0.1:{port}/"))
    for n in d["nodes"]:
        if n["name"] == "Источники":
            n["parameters"]["jsCode"] = f"return [{{ json: {{ url: 'http://127.0.0.1:{port}/rss', name: 'Mock' }} }}];"
    sched = [n for n in d["nodes"] if n["type"] == "n8n-nodes-base.scheduleTrigger"]
    hook = {"01": "t01", "03": "t03"}.get(f.name[:2])
    if sched and hook:
        d["nodes"].append({"parameters": {"path": hook, "httpMethod": "GET", "responseMode": "onReceived", "options": {}},
                           "id": "00000000-0000-4000-8000-0000000000" + f.name[:2], "name": "Kick (test)",
                           "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [0, 0],
                           "webhookId": "00000000-0000-4000-9000-0000000000" + f.name[:2]})
        d["connections"]["Kick (test)"] = d["connections"][sched[0]["name"]]
    (dst / f.name).write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
EOF

export N8N_USER_FOLDER=$T/home N8N_PORT=$PORT N8N_LISTEN_ADDRESS=127.0.0.1 N8N_RUNNERS_BROKER_PORT=5691 \
  N8N_SECURE_COOKIE=false N8N_DIAGNOSTICS_ENABLED=false N8N_PERSONALIZATION_ENABLED=false \
  N8N_VERSION_NOTIFICATIONS_ENABLED=false GENERIC_TIMEZONE=Europe/Kyiv N8N_BLOCK_ENV_ACCESS_IN_NODE=false \
  TELEGRAM_BOT_TOKEN=123:TEST TELEGRAM_MODERATION_CHAT_ID=-1001 TELEGRAM_CHANNEL_ID=@testchan \
  LLM_API_URL=http://127.0.0.1:$MOCK_PORT/v1/chat/completions LLM_API_KEY=sk-test LLM_MODEL=test-model \
  NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost

python3 tests/e2e/mock_server.py "$MOCK_PORT" "$T/requests.jsonl" > "$T/mock.log" 2>&1 &
MOCK=$!
"$N8N" start > "$T/n8n.log" 2>&1 &
SERVER=$!
trap 'kill $MOCK $SERVER 2>/dev/null || true' EXIT
for _ in $(seq 1 90); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/healthz/readiness)" = 200 ] && break; sleep 2
done

C="curl -sf -b $T/cj -c $T/cj -H Content-Type:application/json"
B=http://127.0.0.1:$PORT/rest
json() { python3 -c "import json,sys;d=json.load(sys.stdin);print($1)"; }
$C -X POST $B/owner/setup -d '{"email":"t@example.com","firstName":"T","lastName":"T","password":"Passw0rd!Test"}' > /dev/null
$C -X POST $B/login -d '{"emailOrLdapLoginId":"t@example.com","password":"Passw0rd!Test"}' > /dev/null
PID=$($C $B/projects/personal | json 'd["data"]["id"]')
$C -X POST $B/projects/$PID/data-tables -d '{"name":"seen_urls","columns":[{"name":"url","type":"string"}]}' > /dev/null
QID=$($C -X POST $B/projects/$PID/data-tables \
  -d '{"name":"news_queue","columns":[{"name":"title","type":"string"},{"name":"content","type":"string"},{"name":"url","type":"string"},{"name":"status","type":"string"}]}' \
  | json 'd["data"]["id"]')

N8N_RUNNERS_BROKER_PORT=5692 "$N8N" import:workflow --separate --input="$T/workflows" | tail -1

publish() {
  local v; v=$($C $B/workflows/$1 | json 'd["data"]["versionId"]')
  $C -X POST $B/workflows/$1/activate -d "{\"versionId\":\"$v\"}" > /dev/null
}
kick() { curl -sf "http://127.0.0.1:$PORT/webhook/$1" > /dev/null; sleep 8; }
statuses() { $C "$B/projects/$PID/data-tables/$QID/rows?take=50&skip=0" | json '" ".join(r["status"] for r in sorted(d["data"]["data"], key=lambda r: r["id"]))'; }
expect() { local got; got=$(statuses); if [ "$got" = "$2" ]; then echo "ok   $1: $got"; else echo "FAIL $1: got '$got', want '$2'"; exit 1; fi; }

# 04 first: n8n refuses to publish a workflow whose sub-workflow isn't published
publish 7O3LhmBvuweE5JWY; publish JQWPBC2gXvYrgvIW; publish m9W5tEdtoRyCvCUr

kick t01; expect "01 collects 3 fresh stories, skips the old one" "pending pending pending"
kick t01; expect "01 again: nothing new (dedup)" "pending pending pending"

# three different buttons pressed within one poll
curl -sf -X POST http://127.0.0.1:$MOCK_PORT/_control/updates -d '[
 {"update_id":1,"callback_query":{"id":"cb1","data":"urgent|1","from":{"first_name":"Ed \"Q\""},"message":{"chat":{"id":-1001},"message_id":7}}},
 {"update_id":2,"callback_query":{"id":"cb2","data":"queue|2","from":{"first_name":"Ed"},"message":{"chat":{"id":-1001},"message_id":8}}},
 {"update_id":3,"callback_query":{"id":"cb3","data":"skip|3","from":{"first_name":"Ed"},"message":{"chat":{"id":-1001},"message_id":9}}}]' > /dev/null
publish CK3U2hY0x5bWWc6H; sleep 25
expect "02 urgent / queue / skip in one poll" "published queued published"
kick t03; expect "03 publishes the queued story" "published published published"

python3 - "$T/requests.jsonl" <<'EOF'
import json, sys
reqs = [json.loads(l) for l in open(sys.argv[1])]
tg = lambda m: [r["body"] for r in reqs if r["path"].endswith("/" + m)]
llm = [r for r in reqs if r["path"].endswith("/chat/completions")]
cards = [b for b in tg("sendMessage") if b["chat_id"] == "-1001"]
posts = [b for b in tg("sendMessage") if b["chat_id"] == "@testchan"]
checks = {
    "3 moderation cards with row ids in buttons": len(cards) == 3 and all("reply_markup" in c for c in cards),
    "2 posts in the channel, each with the AI comment": len(posts) == 2 and all("<i>" in p["text"] for p in posts),
    "all 3 cards deleted": sorted(b["message_id"] for b in tg("deleteMessage")) == [7, 8, 9],
    "LLM gets Bearer key and model override": bool(llm) and all(r["auth"] == "Bearer sk-test" and r["body"]["model"] == "test-model" for r in llm),
    "HTML in the comment is escaped": all("&lt;" in p["text"] for p in posts),
}
for k, v in checks.items(): print(("ok  " if v else "FAIL"), k)
sys.exit(0 if all(checks.values()) else 1)
EOF
echo "all good"
