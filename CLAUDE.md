# ai-newsroom-automation

## Старт сессии
1. Прочитай ROADMAP.md и GOTCHAS.md (они короткие).
2. DECISIONS.md целиком не читай — смотри индекс вверху и открывай нужную запись, когда трогаешь эту область.
3. CHANGELOG.md не читай, только дописывай.

## Конец задачи
- CHANGELOG.md: одна строка в начало раздела текущей даты.
- ROADMAP.md: обнови "Где сейчас" и "Следующий шаг".
- Принял неочевидное решение или отказался от варианта → запись в DECISIONS.md.
- Наступил на грабли (баг API, странность библиотеки) → запись в GOTCHAS.md.
- Не плоди новые md-файлы без просьбы.

## Стек и команды
- n8n@2.46.6 (нужен Node ≥ 24), воркфлоу — JSON в `workflows/`, запуск — Docker Compose.
- Проверки на этом сервере: `jq . workflows/*.json`, `python3 -m py_compile tests/e2e/*.py`, `bash -n tests/e2e/*.sh`. Полный e2e (`tests/e2e/run.sh`) здесь не запустится — его гоняет GitHub Actions на PR.

## Как работаем
- 1 PR = 1 issue: ветка от свежего `main`, коммиты по Conventional Commits, в PR `Closes #N`. Issue уже есть — новый не создавай.
- Не ломай совместимость с n8n@2.46.6: перед правкой JSON сверяй имена нод, `typeVersion` и `connections`.
- Правишь экранирование HTML, таймауты или статусы — проверь `workflows/03_queue_scheduled_publisher.json` и `workflows/04_ai_comment_generator.json`.
- Убирай локальный `meta.instanceId` из воркфлоу.
- Перед сменой URL фида проверь его через `curl`.
- Отчёт по PR: изменённые файлы, результаты проверок, текст PR с `Closes #N`.

## Запреты
- Не коммить .env, ключи, seed-фразы. Не передавай их в сторонние модели.
- Не хардкодь секреты и локальные данные.

## Agent skills
- Трекер задач: GitHub Issues этого репо (`gh`). Команды — `docs/agents/issue-tracker.md`.
- Метки: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. Нужной метки нет в репо — создай (`gh label create`).
- Решения — записи D### в DECISIONS.md, не `docs/adr/`. Термины — GLOSSARY.md (создаётся, когда согласован первый термин).
- ROADMAP — короткая карта: пункты ссылаются на issue или спеку, подробности туда не копируй.
