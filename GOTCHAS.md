# Gotchas — грабли, на которые уже наступили. Коротко: симптом → причина → как обходить.

- CNN RSS по https не отвечает → оставлять `http://rss.cnn.com/rss/edition.rss` (#8, #9).
- e2e не запускается на сервере → n8n@2.46.6 требует Node ≥ 24, а тут Node 22 и нет docker/shellcheck → полный e2e только в GitHub Actions.
