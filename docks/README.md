# tg-proxy — Telegram proxy userbot

Telethon-userbot, который прозрачно проксирует сообщения, реакции, редактирования и удаления между парами Telegram-групп. Саппорт-агенты работают в зеркальных группах, не раскрывая свои профили мерчантам.

## Как это работает

Каждая настроенная пара связывает группу мерчанта с группой саппорта. Активный userbot-аккаунт состоит во всех группах одновременно. Когда сообщение приходит в любой отслеживаемый чат, бот копирует его в зеркальный чат от своего имени — не как пересылку, без атрибуции исходного автора.

Связность реплаев, реакции, редактирования и удаления синхронизируются в обе стороны. Маппинг message ID хранится в PostgreSQL — бот корректно работает после рестартов и пересменок.

Можно настроить два аккаунта с расписанием смен по московскому времени. Оркестратор отключает уходящий аккаунт и подключает заступающий, который через `catch_up` подхватывает сообщения, пришедшие в промежуток 5–15 секунд.

## Требования

- Python 3.11+
- PostgreSQL 14+
- Docker и Docker Compose (для контейнерного деплоя)
- Telegram API-ключи (`api_id`, `api_hash`) с https://my.telegram.org
- Один или два предварительно авторизованных Telethon session-файла

## Быстрый старт через Docker Compose

```bash
git clone https://github.com/Ferari430/tg_proxy.git
cd tg_proxy
```

Скопируй файл с переменными окружения и заполни свои данные:

```bash
cp .env.example .env
```

Отредактируй `config.yaml` — укажи ID групп и пути к session-файлам (см. раздел «Конфигурация»).

Положи session-файлы в папку `sessions/`. Если авторизация ещё не пройдена — сначала см. раздел «Авторизация».

Запусти приложение:

```bash
docker compose up --build
```

Миграции применяются автоматически при старте. Приложение готово к работе когда в логах появится строка `orchestrator.started`.

## Авторизация

Userbot-аккаунты нужно авторизовать один раз перед запуском приложения. В результате создаётся `.session`-файл, который используется при всех последующих запусках.

```bash
pip install -e .
cp .env.example .env  # заполни API_ID и API_HASH

# Авторизовать первый аккаунт
python scripts/authorize.py account1.session

# Авторизовать второй аккаунт (если используются два)
python scripts/authorize.py account2.session
```

Скрипт запросит номер телефона, код подтверждения и пароль двухфакторной аутентификации (если установлен). Session-файлы сохраняются в папку `sessions/`.

Оба userbot-аккаунта должны быть участниками всех настроенных групп до запуска приложения.

## Конфигурация

### `.env`

```dotenv
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890
DATABASE_URL=postgresql://tgproxy:tgproxy@localhost:5432/tgproxy
LOG_LEVEL=INFO
```

В переменной `DATABASE_URL` используй имя сервиса `postgres` как хост внутри Docker Compose и `localhost` при локальном запуске.

### `config.yaml`

```yaml
telegram:
  api_id: "${API_ID}"
  api_hash: "${API_HASH}"

accounts:
  # Один аккаунт, работает 24/7
  - session_file: "sessions/account1.session"

  # Два аккаунта с расписанием смен (московское время)
  # - session_file: "sessions/account1.session"
  #   active_hours: {start: "08:00", end: "20:00"}
  # - session_file: "sessions/account2.session"
  #   active_hours: {start: "20:00", end: "08:00"}

mappings:
  - merchant_chat: -1001234567890
    support_chat:  -1009876543210
  - merchant_chat: -1001111111111
    support_chat:  -1002222222222

human_delay:
  min_seconds: 1
  max_seconds: 4

timezone: "Europe/Moscow"
```

ID супергрупп начинается с `-100`. Чтобы узнать ID группы, добавь userbot в группу и проверь логи при старте — при резолвинге entity ID выводится в лог.

Поле `active_hours` принимает время в формате `HH:MM`. Если поле не указано — аккаунт работает круглосуточно. Проверка расписания выполняется каждые 30 секунд.

## Локальный запуск без Docker

Запусти PostgreSQL отдельно (или через `docker compose up -d postgres`).

```bash
pip install -e .

export DATABASE_URL=postgresql://tgproxy:tgproxy@localhost:5432/tgproxy
export CONFIG_PATH=config.yaml

alembic upgrade head
python -m src.main
```

## Миграции

Миграции управляются через Alembic. `entrypoint.sh` автоматически выполняет `alembic upgrade head` перед запуском приложения, поэтому в обычном режиме запускать миграции вручную не нужно.

Запустить вручную:

```bash
alembic upgrade head
```

Создать новую миграцию после изменения схемы:

```bash
alembic revision --autogenerate -m "описание"
```

Скрипты миграций находятся в `migrations/versions/`.

## Структура проекта

```
src/
  core/
    config.py       — Pydantic-модели конфига, загрузка YAML
    flood.py        — утилита повтора при FloodWaitError
    logging.py      — настройка structlog (JSON в stdout)
  db/
    pool.py         — пул соединений asyncpg
    repository.py   — CRUD маппинга сообщений
  handlers/
    messages.py     — пересылка новых сообщений
    albums.py       — пересылка медиагрупп
    edits.py        — зеркалирование редактирований
    deletions.py    — зеркалирование удалений
    reactions.py    — зеркалирование реакций
  orchestrator.py   — управление жизненным циклом аккаунтов и расписанием смен
  worker.py         — обёртка TelegramClient, регистрация хендлеров событий
  main.py           — точка входа
migrations/         — скрипты миграций Alembic
scripts/
  authorize.py      — одноразовая авторизация сессии
```

## Известные ограничения

- Снятие реакции мерчантом с сообщения, отправленного userbot'ом, не зеркалируется. Telegram не присылает апдейт userbot'у когда реакция снимается с чужого сообщения. Ограничение MTProto API.
- Кастомные Premium emoji-реакции игнорируются; зеркалируются только стандартные emoji-реакции.
- При обрыве сети внутри сессии Telethon переподключается автоматически, но `catch_up` не вызывается. Сообщения, пришедшие во время обрыва, будут подхвачены при следующем рестарте или пересменке.
