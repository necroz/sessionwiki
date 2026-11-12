#!/usr/bin/env python3
"""Build .metrics/memorytax-questions.json from mined, grep-verified facts.

Aliases map to real raw/sessions files. Each question carries a short gold
answer and the evidence files. Categories follow MemoryTax / LoCoMo:
single, multi, temporal, open. Run once; the JSON is the artifact.
"""
import json
from pathlib import Path

F = {
    "L0901": "2026-09-01T09-28-larisa-ngdu-sess_47b08131-9804-4940-9f88-a0cb006302b9.md",
    "L0908": "2026-09-08T15-00-larisa-ngdu-sess_fbbf4aac-e723-4248-a419-4fe99b211714.md",
    "L0915": "2026-09-15T15-00-larisa-ngdu-sess_b0084103-9664-4802-b395-f71a9b27b442.md",
    "L0918": "2026-09-18T11-36-larisa-ngdu-sess_f2fe2eec-0219-4245-9a39-c707cb6a4bd5.md",
    "L0930": "2026-09-30T10-00-larisa-ngdu-sess_030edc50-6e81-4cdc-89d0-e1c242173518.md",
    "L1008": "2026-10-08T14-05-larisa-ngdu-sess_8b023291-b09f-4496-b2b1-a44cb4c13826.md",
    "N0717": "2026-07-17T13-51-neuromerch_project-sess_041c287a-4178-487a-9af8-e888b65582b3.md",
    "N0727": "2026-07-27T15-46-neuromerch_project-sess_dbbf95cd-2e1f-4848-8b36-f59224b7b8a1.md",
    "N0805": "2026-08-05T11-11-neuromerch_project-sess_6ba0cf8c-8bb7-4beb-abb5-a5e8a86ecdde.md",
    "N0819": "2026-08-19T14-08-neuromerch_project-sess_a7f5ba31-0bb1-47c1-987f-8c8b57cc067d.md",
    "N0821": "2026-08-21T14-51-neuromerch_project-sess_e25ceb69-9d9b-41d5-9790-6653576e6681.md",
    "A0924": "2026-09-24T16-27-audio-transcript-sess_6b2c60a8-78f4-45a5-bac0-789ccea6f369.md",
    "A0925": "2026-09-25T14-49-audio-transcript-sess_37bf2518-4da4-45d0-8a77-b13422c4e005.md",
    "A1005": "2026-10-05T15-20-audio-transcript-sess_bd171d38-ba5d-4aa6-ae67-782c90a173bd.md",
    "A1013": "2026-10-13T15-16-audio-transcript-sess_fa1a8522-d1ca-48bb-b4e3-a24931ea6de9.md",
    "A1105": "2026-11-05T12-08-audio-transcript-sess_3bbe7899-dd6a-4606-b6e1-7e0ebf8af56d.md",
    "W1102": "2026-11-02T10-32-llm-wiki-sess_f6c25d86-c924-4794-84be-39b03dd1fbf4.md",
    "W1105": "2026-11-05T08-17-llm-wiki-sess_7b592ac5-11ed-45bf-90d5-99d5cb0109f5.md",
    "W1106": "2026-11-06T08-20-llm-wiki-sess_31bc1856-f12b-4984-99ae-fead5536e8f7.md",
    "D0723": "2026-07-23T14-34-workspace_default-sess_627abcd1-6844-42e7-8bb2-1ae2c4141657.md",
    "D0825": "2026-08-25T13-28-workspace_default-sess_bfafcd1b-4da7-4127-ae98-a137987d2607.md",
    "D0902": "2026-09-02T10-26-workspace_default-sess_57c90e93-aa3a-403c-a346-59d1898f5419.md",
    "D0929": "2026-09-29T10-29-workspace_default-sess_bb458dbe-571a-451b-88e5-24736cd1e086.md",
    "D1009": "2026-10-09T14-44-workspace_default-sess_a954866c-6db4-4b28-8417-84f57ccb488c.md",
}

# (id, kind, project, question, gold, [aliases])
Q = [
    # ---- single (35) ----
    ("s01", "single", "larisa-ngdu", "Сколько строк было в ARCHITECTURE.md после завершения Стадии 1 в larisa-ngdu?", "3240 строк", ["L0901"]),
    ("s02", "single", "larisa-ngdu", "Сколько методов и в скольких репозиториях покрывали 66 вопросов заказчика в каталоге Phase 1 larisa-ngdu?", "65 методов в 6 репозиториях", ["L0901"]),
    ("s03", "single", "larisa-ngdu", "К скольким каноническим представлениям обращается код larisa-ngdu?", "31 каноническое представление", ["L0901"]),
    ("s04", "single", "larisa-ngdu", "Какая ошибка PostgreSQL возникала из-за вербатим-SQL карточки L-94 с :min_value IS NULL?", "AmbiguousParameter $5", ["L0908"]),
    ("s05", "single", "larisa-ngdu", "Какой период выдумывала LLM в живом смоке A32 по скважине 3 в larisa-ngdu?", "2023-11-15…2023-12-15", ["L0908"]),
    ("s06", "single", "larisa-ngdu", "Какой endpoint и таблица появились для feedback по ответам в карточке L-125 larisa-ngdu?", "POST /chat/feedback, таблица journal_feedback", ["L0915"]),
    ("s07", "single", "larisa-ngdu", "Какой код ошибки возвращает /chat/feedback при выключенном журнале в larisa-ngdu?", "503 LAR-903", ["L0915"]),
    ("s08", "single", "larisa-ngdu", "Какой DSN app-pg записан в .env корня репо larisa-ngdu?", "плейсхолдер 127.0.0.1:1/x", ["L0915"]),
    ("s09", "single", "larisa-ngdu", "Какие значения classify_temperature и compose_temperature задали в карточке L-142 larisa-ngdu?", "classify_temperature=0.0, compose_temperature=0.2", ["L0918"]),
    ("s10", "single", "larisa-ngdu", "Какие длина хода и число качаний для скважины 341 в живом смоке L-174 larisa-ngdu?", "250 см, 14.6 кач/мин", ["L0930"]),
    ("s11", "single", "larisa-ngdu", "В каком формате иконка копирования таблицы в веб-чате larisa-ngdu кладёт таблицу в буфер обмена?", "TSV", ["L1008"]),
    ("s12", "single", "neuromerch_project", "К какой базе данных и какой версии PostgreSQL подключался MCP-сервер postgres в neuromerch_project 17 июля?", "neuromerch_test, PostgreSQL 18.4", ["N0717"]),
    ("s13", "single", "neuromerch_project", "Сколько строк было в KisNomenclature в staging-базе neuromerch_project 17 июля?", "2067 строк", ["N0717"]),
    ("s14", "single", "neuromerch_project", "Какой провайдер и модель добавили в ~/.zcode/v2/config.json 27 июля в neuromerch_project?", "dashscope-qwen, qwen3.8-max-preview", ["N0727"]),
    ("s15", "single", "neuromerch_project", "Почему vLLM-сервер qwen3.8 отклонял запросы с tool_choice=auto в neuromerch_project?", "запущен без --enable-auto-tool-choice и --tool-call-parser", ["N0819"]),
    ("s16", "single", "neuromerch_project", "Сколько планограмм «в работе» (isWork=TRUE) в таблице KisPlanogramWarehouse базы neuromerch_short?", "2384", ["N0821"]),
    ("s17", "single", "neuromerch_project", "Для каких баз ПОН зеркало neuromerch_short содержит номенклатуру?", "ПОН 03 и 07", ["N0821"]),
    ("s18", "single", "neuromerch_project", "Сколько категорий и сколько дубликатов названий стало после исправления display_name в neuromerch_project?", "849 категорий, дубликаты с 59 до 9", ["N0821"]),
    ("s19", "single", "neuromerch_project", "Какое сообщение возвращает MSSQL MCP-сервер neuromerch_project при попытке записи в read-only режиме?", "Write operations disabled in read-only mode", ["N0717"]),
    ("s20", "single", "audio-transcript", "Какой формат даты встречи добавили в карточку джоба audio-transcript 24 сентября?", "dd.mm.yyyy HH:MM:SS", ["A0924"]),
    ("s21", "single", "audio-transcript", "Почему проваленная файловая джоба audio-transcript всегда выходила с кодом 0?", "shutdown(..., e.exitCode || 0): у обычного Error нет exitCode", ["A1005"]),
    ("s22", "single", "audio-transcript", "Почему загрузка файла с кириллическим именем падала в audio-transcript?", "заголовок X-Filename — ByteString, символы выше U+00FF бросают InvalidCharacterError", ["A1005"]),
    ("s23", "single", "audio-transcript", "Какой звук пишет Python-рекордер audio-transcript на Windows и Linux?", "WASAPI loopback на Windows, monitor-источник на Linux", ["A1005"]),
    ("s24", "single", "audio-transcript", "Какой фирменный зелёный цвет (hex и Pantone) сняли с брендбука Белоруснефти для audio-transcript?", "#009E44, Pantone 354 C", ["A1013"]),
    ("s25", "single", "audio-transcript", "Какой контраст белого текста на зелёном #009E44 и какой цвет выбрали для мелкого текста?", "3.52:1; тёмно-зелёный #00733A (5.98:1)", ["A1013"]),
    ("s26", "single", "audio-transcript", "Сколько карточек ревью live-стриминга audio-transcript закрыты в коде к 5 ноября?", "24 карточки", ["A1105"]),
    ("s27", "single", "llm-wiki", "Какие зависимости добавили в graph и all extras в карточке 05 llm-wiki?", "matplotlib>=3.8 и scipy>=1.11", ["W1102"]),
    ("s28", "single", "llm-wiki", "Какой новый дом проекта на GitHub после ребрендинга 5 ноября?", "necroz/sessionwiki (standalone, не форк)", ["W1105"]),
    ("s29", "single", "llm-wiki", "Почему создавались дубликаты issue #16 и #17 в link-check llm-wiki?", "update_existing: true — несуществующий input, action молча игнорирует", ["W1105"]),
    ("s30", "single", "llm-wiki", "Какой per-file cap и aggregate budget задали для MCP wiki_search/wiki_query в фиксе #483?", "4 MiB per-file, 50 MiB aggregate", ["W1106"]),
    ("s31", "single", "workspace_default", "Какая версия code-review-graph была в MCP handshake и какая в CLI --version?", "3.4.4 в handshake, 2.3.7 в CLI", ["D0723"]),
    ("s32", "single", "workspace_default", "Какой потолок скорости дают 100-Мбит Ethernet-порты роутера Keenetic Carrier?", "~94 Мбит/с", ["D0825"]),
    ("s33", "single", "workspace_default", "Какой RSRP и антенна были в LTE-сетапе модема 850GL?", "RSRP около -105 dBm, MIMO антенна 17 дБ", ["D0825"]),
    ("s34", "single", "workspace_default", "Какая GPU и версия драйвера на рабочей станции workspace_default?", "RTX 5080, драйвер 595.91.07", ["D1009"]),
    ("s35", "single", "workspace_default", "Какие EAS-аддоны Thunderbird удалены из каталога (404)?", "TbSync и Provider for Exchange ActiveSync", ["D0929"]),
    # ---- multi (20) ----
    ("m01", "multi", "larisa-ngdu", "Что произошло с неподтверждённым термином КВЧ из Стадии 1 к 8 сентября в larisa-ngdu?", "подтверждён владельцем 2026-09-07; well.get_chem_analysis поднят до v6", ["L0901", "L0908"]),
    ("m02", "multi", "larisa-ngdu", "Сохранился ли перевод вопроса B-26 на get_production_for_period к 30 сентября в larisa-ngdu?", "да, дрейф O49 (бывш. O36) сохранён, Q3 всё ещё на get_production_for_period", ["L0918", "L0930"]),
    ("m03", "multi", "larisa-ngdu", "Как выросла декомпозиция карточек larisa-ngdu от исходного плана Стадии 1 к 8 октября?", "с 70 карточек L-01…L-70 до L-210 (Блок 101)", ["L0901", "L1008"]),
    ("m04", "multi", "larisa-ngdu", "Как менялся статус автостопа MVP-7 и очередь карточек между 14 и 18 сентября в larisa-ngdu?", "автостоп снят 2026-09-14, работа возобновлена; к 2026-09-18 очередь исчерпана на L-143", ["L0915", "L0918"]),
    ("m05", "multi", "larisa-ngdu", "Как менялось число eval-тестов между карточкой L-125 (15 сентября) и дежурным прогоном 18 сентября в larisa-ngdu?", "97/97 на L-125, 87/87 на дежурном прогоне", ["L0915", "L0918"]),
    ("m06", "multi", "neuromerch_project", "Как изменилась целевая база MCP-сервера postgres в neuromerch_project с июля по август?", "с neuromerch_test (17 июля) на neuromerch_short (21 августа)", ["N0717", "N0821"]),
    ("m07", "multi", "neuromerch_project", "Почему в staging neuromerch_project было мало номенклатуры (2067 строк)?", "зеркало содержит номенклатуру только ПОН 03 и 07", ["N0717", "N0821"]),
    ("m08", "multi", "neuromerch_project", "Какой скилл поставили вместо common-debugging 5 августа и использовали ли его позже?", "superpowers; 19 августа применён systematic-debugging для ошибки vLLM", ["N0805", "N0819"]),
    ("m09", "multi", "neuromerch_project", "Что заменило Mermaid erDiagram в docs/research и в какой базе позже считали планограммы «в работе»?", "интерактивный холст db_schema_diagram.html; база neuromerch_short", ["N0717", "N0821"]),
    ("m10", "multi", "neuromerch_project", "Какой флаг автообновления ZCode включили 28 июля и какой скилл поставили 5 августа?", "autoDownloadAndInstallUpdates: true; superpowers", ["N0727", "N0805"]),
    ("m11", "multi", "audio-transcript", "Внедрили ли транскрипцию Google Meet после сентябрьского исследования к 5 ноября?", "нет, решение отложено; коммит 6bcc920 «статус У1 — отложено»", ["A0925", "A1105"]),
    ("m12", "multi", "audio-transcript", "Откуда в live-стриме audio-transcript микширование и атрибуция каналов?", "переиспользует mixMicSystem/ChannelVad из lib/audio/file-source.js (октябрьские коммиты)", ["A1005", "A1105"]),
    ("m13", "multi", "audio-transcript", "Что добавили в карточку джоба 24 сентября и какой модуль записи появился в октябрьских коммитах audio-transcript?", "дату встречи dd.mm.yyyy HH:MM:SS; Python-рекордер recorder/recorder.py", ["A0924", "A1005"]),
    ("m14", "multi", "llm-wiki", "Как назывался пакет до ребрендинга и был ли sessionwiki на PyPI 5 ноября?", "llm-notebook 1.3.82; sessionwiki ещё не на PyPI (404)", ["W1102", "W1105"]),
    ("m15", "multi", "llm-wiki", "Что произошло после подготовки релиза v2.0.0 к 6 ноября в llm-wiki?", "PR #20 v2.0.0 смёржен 5 ноября; к 6 ноября в CHANGELOG датированный 2.0.4", ["W1105", "W1106"]),
    ("m16", "multi", "workspace_default", "Почему web/MCP fetch падал с «resolves to non-public address 198.18.0.x» в сессии модема?", "VPN с fake-IP DNS (tun0 → резолвер 10.0.0.1, диапазон 198.18.0.0/15) перехватывает DNS", ["D0825", "D0929"]),
    ("m17", "multi", "workspace_default", "Какой GPU обслуживает локальный LLM-инференс и что запускают локально?", "RTX 5080; локально llama.cpp на GGUF, vLLM на удалённом сервере", ["D0902", "D1009"]),
    ("m18", "multi", "workspace_default", "В какой корпоративной среде работает пользователь и как аутентифицируется в Exchange?", "Belorusneft (beloil.by), belarusneft\\I.Lashkevich", ["D0825", "D0929"]),
    ("m19", "multi", "workspace_default", "Какой коммит llama.cpp был 2 сентября и какая ОС на рабочей станции 9 октября?", "llama.cpp 4fc4ec554 от 2026-07-01; Ubuntu 26.04.1 LTS", ["D0902", "D1009"]),
    ("m20", "multi", "llm-wiki", "Какие карточки были готовы 2 ноября и какой релиз смёржен 5 ноября в llm-wiki?", "карточки 01–04 готовы, внедрена 05; PR #20 release v2.0.0", ["W1102", "W1105"]),
    # ---- temporal (15) ----
    ("t01", "temporal", "larisa-ngdu", "Когда и до какой версии подняли well.get_chem_analysis в larisa-ngdu?", "2026-09-08, version 6 (решение бизнеса 2026-09-07)", ["L0908"]),
    ("t02", "temporal", "larisa-ngdu", "Когда был снят статус «MVP-7 ПРИОСТАНОВЛЕН» в larisa-ngdu?", "2026-09-14", ["L0915"]),
    ("t03", "temporal", "larisa-ngdu", "Какая карточка была последней в очереди раздела 14 на 2026-09-18 в larisa-ngdu?", "L-143 (Блок 43)", ["L0918"]),
    ("t04", "temporal", "larisa-ngdu", "Какая карточка и когда намеренно перевела B-26 на get_production_for_period?", "L-134, M7-41, 2026-09-16", ["L0918"]),
    ("t05", "temporal", "larisa-ngdu", "Когда equipment.get_stroke подняли до version 4 и что заменили?", "2026-09-30, swing_period_s → swings_per_min = 60/период", ["L0930"]),
    ("t06", "temporal", "larisa-ngdu", "Какой шаг оставался в очереди larisa-ngdu на 2026-10-08?", "M7-117 (L-210, фильтр скважины по main_pump.number)", ["L1008"]),
    ("t07", "temporal", "neuromerch_project", "Какая версия ZCode была установлена 28 июля и какая была последней?", "установлена 3.4.2-3624, последняя 3.5.3", ["N0727"]),
    ("t08", "temporal", "neuromerch_project", "Какой флаг автообновления ZCode изменили 28 июля и как?", "autoDownloadAndInstallUpdates: false → true", ["N0727"]),
    ("t09", "temporal", "neuromerch_project", "Что принёс коммит 57260fb в neuromerch_project 17 июля?", "модуль kis_unified_import: 34 файла, +4811 строк", ["N0717"]),
    ("t10", "temporal", "audio-transcript", "Когда закоммитили фирменный стиль Белоруснефти в audio-transcript и каким коммитом?", "13.10.2026, a6b686f", ["A1013"]),
    ("t11", "temporal", "audio-transcript", "Как изменили cron автотаски по карточкам audio-transcript 5 ноября?", "с 30 * * * * (раз в час) на каждые 30 минут", ["A1105"]),
    ("t12", "temporal", "audio-transcript", "С какого года Meet Media API в Developer Preview по данным на сентябрь?", "с февраля 2025", ["A0925"]),
    ("t13", "temporal", "llm-wiki", "Когда и каким коммитом проект ребрендился в sessionwiki?", "2026-11-05 09:22:51 +0300, 908e516", ["W1105"]),
    ("t14", "temporal", "llm-wiki", "Как изменились дефолты chunk_chars и max_body_chars 6 ноября в llm-wiki?", "chunk_chars 48000→40000, max_body_chars 12000→40000", ["W1106"]),
    ("t15", "temporal", "workspace_default", "Как изменился статус HDMI-порта второго монитора в сессии 9 октября?", "с disconnected на connected", ["D1009"]),
    # ---- open (10) ----
    ("o01", "open", "larisa-ngdu", "Какие подходы к контролю качества ответов применялись в larisa-ngdu?", "golden-вопросы, живые смоки, eval-наборы, feedback-кнопки, дежурные прогоны", ["L0915", "L0930", "L1008"]),
    ("o02", "open", "larisa-ngdu", "Как в larisa-ngdu решали проблему неподтверждённых данных заказчика?", "термины со статусом «ожидает подтверждения», уточняющие вопросы, гейты; подтверждение владельцем", ["L0901", "L0908"]),
    ("o03", "open", "neuromerch_project", "Какие источники данных и MCP-серверы использовал neuromerch_project?", "Postgres (neuromerch_test/short), MSSQL КИС, code-review-graph", ["N0717", "N0821"]),
    ("o04", "open", "neuromerch_project", "Какие проблемы с LLM-провайдерами и инструментами диагностировали в neuromerch_project?", "vLLM без tool-call-parser, GitHub auth, установка скиллов", ["N0727", "N0805", "N0819"]),
    ("o05", "open", "audio-transcript", "Какие баги высокой критичности нашло ревью audio-transcript 5 октября?", "выход с кодом 0 при провале, кириллическое имя файла ломает загрузку", ["A1005"]),
    ("o06", "open", "audio-transcript", "Как audio-transcript пришёл к фирменному стилю Белоруснефти?", "разбор брендбука, снятие цветов с рендера, проверка WCAG, вариант Минимал", ["A1013"]),
    ("o07", "open", "llm-wiki", "Какие ограничения чтения сессий ввели в llm-wiki для больших файлов?", "чанкование по Turn-маркерам, per-file cap 4 MiB, aggregate 50 MiB, пропуск oversize", ["W1106"]),
    ("o08", "open", "llm-wiki", "Что вошло в релизы sessionwiki 2.0.0–2.0.4?", "ребрендинг, публикация на PyPI, интеграция с агентом, recall при старте сессии", ["W1105", "W1106"]),
    ("o09", "open", "workspace_default", "Какие сетевые и DNS-проблемы диагностировали в workspace_default?", "потолок 100-Мбит портов, VPN fake-IP DNS, отказ fetch из-за 198.18.0.x", ["D0825", "D0929"]),
    ("o10", "open", "workspace_default", "Как настроили локальный и удалённый LLM-инференс в workspace_default?", "llama.cpp локально на GGUF, vLLM на удалённом сервере, chat-templates Qwen", ["D0902", "D1009"]),
]


def main():
    out = []
    for qid, kind, proj, question, gold, aliases in Q:
        out.append({
            "id": qid, "kind": kind, "project": proj,
            "question": question, "answer": gold,
            "evidence": [f"raw/sessions/{F[a]}" for a in aliases],
        })
    counts = {}
    for q in out:
        counts[q["kind"]] = counts.get(q["kind"], 0) + 1
    path = Path(".metrics/memorytax-questions.json")
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(out)} questions to {path}: {counts}")
    # sanity: every evidence file exists
    missing = [e for q in out for e in q["evidence"] if not Path(e).exists()]
    print("missing evidence files:", missing or "none")


if __name__ == "__main__":
    main()