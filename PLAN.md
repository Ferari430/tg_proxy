# План допиливания tg-proxy

## Статус

| # | Задача | Сложность | Статус |
|---|--------|-----------|--------|
| 1 | Редактирование сообщений | Низкая | ✅ готово |
| 2 | Удаление сообщений | Средняя | ✅ готово |
| 3 | Одиночные медиа | Низкая | ✅ готово |
| 4 | Реакции | Средняя | ✅ готово |
| 5 | Альбомы (медиагруппы) | Высокая | ⬜ не начато |

---

## Шаг 1 — Редактирование сообщений

**Файлы:** `src/handlers/edits.py`, `src/worker.py`
**Сложность: Низкая**

### Как это работает

`events.MessageEdited` устроен точно как `events.NewMessage` — в событии уже лежит **полное обновлённое сообщение**. Старое значение недоступно и не нужно.

Алгоритм:
1. Получить `src_chat_id` и `msg.id` из события
2. Найти зеркальное сообщение в БД через `repo.get_mirror(src_chat_id, msg.id)`
3. Вызвать `client.edit_message(mirror_chat_id, mirror_msg_id, msg.text)`

Если у сообщения медиа — `msg.text` это подпись (caption). `edit_message` обрабатывает оба случая одинаково.

```
EditEvent → get_mirror(chat_id, msg_id) → client.edit_message(mirror_chat, mirror_id, new_text)
```

### Что добавляем в worker.py

Регистрируем новый хендлер рядом с `on_new_message`:

```python
self._client.add_event_handler(
    on_edit,
    events.MessageEdited(chats=monitored, incoming=True),
)
```

---

## Шаг 2 — Удаление сообщений

**Файлы:** `src/handlers/deletions.py`, `src/worker.py`
**Сложность: Средняя**

### Как это работает

`events.MessageDeleted.Event` содержит **список** `deleted_ids` — одним событием могут удалить несколько сообщений сразу.

Алгоритм:
1. Для каждого `msg_id` из `event.deleted_ids`:
   - Найти зеркало в БД
   - Удалить его через `client.delete_messages(mirror_chat_id, [mirror_msg_id])`

```
DeleteEvent(deleted_ids=[101, 102, 103])
  → для каждого id: get_mirror(chat_id, id)
  → delete_messages(mirror_chat, mirror_id)
```

### Важный подводный камень

В обычных группах (не supergroup) Telegram **не передаёт** `chat_id` в событии удаления — ограничение протокола. В supergroup/channel `chat_id` есть всегда.

Большинство рабочих групп — supergroup'ы, поэтому для ТЗ это приемлемо. Но `chat_id is None` нужно явно обработать (пропустить с логом).

---

## Шаг 3 — Одиночные медиа

**Файлы:** `src/handlers/messages.py`
**Сложность: Низкая**

### Как это работает

Сейчас в `messages.py` есть строка:
```python
if not msg.text or msg.media is not None:
    return
```
Она выбрасывает **все** медиа-сообщения. Нужно убрать этот запрет.

Вместо этого добавляем фильтр для альбомов (шаг 5 — отдельная история):
```python
if msg.grouped_id is not None:
    return  # альбом — обрабатывается отдельно
```

Для отправки используем `send_file` вместо `send_message`:
```python
# медиа
sent = await client.send_file(
    target_chat_id,
    file=msg.media,
    caption=msg.text,
    formatting_entities=msg.entities,
    reply_to=reply_to,
)

# текст — как было
sent = await client.send_message(...)
```

Telethon автоматически передаёт существующую ссылку на файл — повторной загрузки нет.

```
NewMessage(media, grouped_id=None)
  → send_file(target, msg.media, caption=msg.text)
```

---

## Шаг 4 — Реакции

**Файлы:** `src/handlers/reactions.py`, `src/worker.py`
**Сложность: Средняя**

### Почему events.Raw

У Telethon нет встроенного события для реакций. Нужно подписаться на «сырые» апдейты и фильтровать по типу:

```python
from telethon.tl.types import UpdateMessageReactions

self._client.add_event_handler(
    on_reaction,
    events.Raw(UpdateMessageReactions),
)
```

### Архитектурное ограничение (важно)

Userbot может поставить только **свою** реакцию. Нельзя воспроизвести, что 5 разных людей поставили 5 разных эмодзи.

Поэтому логика такая:
- Берём из апдейта актуальный список реакций (`update.reactions.results`)
- Берём реакцию с наибольшим `count`
- Ставим её на зеркальное сообщение
- Если реакций не осталось — снимаем нашу

### Сложности реализации

1. **Извлечь `chat_id` из peer**: `update.peer_id` — это объект `PeerChannel` / `PeerChat`, нужно вытащить из него `int`
2. **Проверить что чат в конфиге** — через `cfg.is_monitored(chat_id)`
3. **Разобрать тип реакции**: `ReactionEmoji` (обычный эмодзи) vs `ReactionCustomEmoji` (Premium) — кастомные пропускаем

```
Raw(UpdateMessageReactions)
  → извлечь chat_id из peer_id
  → проверить monitored
  → get_mirror(chat_id, msg_id)
  → найти top-реакцию из results
  → send_reaction(mirror_chat, mirror_id, emoji)
```

---

## Шаг 5 — Альбомы (медиагруппы)

**Файлы:** `src/handlers/messages.py`, `src/worker.py`
**Сложность: Высокая**

### Почему сложно

Telegram присылает альбом (несколько фото/видео вместе) как **отдельные** `NewMessage` события с одинаковым `grouped_id`. Telethon не собирает их сам.

Нужно:
1. Подождать ~0.8 сек пока придут все части
2. Отправить как один альбом через `send_file(files=[...])`
3. Сохранить маппинги для **каждого** сообщения альбома — они все получают отдельные IDs в зеркальном чате

### Архитектура буфера

Буфер живёт в `UserbotWorker` — у каждого воркера свой:

```python
self._album_buffer: dict[int, list[Message]] = {}  # grouped_id → сообщения
self._album_tasks: dict[int, asyncio.Task] = {}     # grouped_id → таймер-задача
```

Алгоритм при получении сообщения с `grouped_id`:
1. Добавить в `_album_buffer[grouped_id]`
2. Отменить старый таймер `_album_tasks[grouped_id]` если был
3. Запустить новый `asyncio.Task` — через 0.8 сек отправить всё накопленное

После срабатывания таймера:
1. Отсортировать сообщения по `msg.id` (могут прийти не по порядку)
2. Отправить: `client.send_file(target, files=[m.media for m in msgs], caption=первая_подпись)`
3. Сохранить маппинги для каждой пары `(src_msg_id, dst_msg_id)`
4. Очистить буфер

```
NewMessage(grouped_id=42, media=фото1)  → buffer[42]=[фото1], запустить таймер(0.8s)
NewMessage(grouped_id=42, media=фото2)  → buffer[42]=[фото1,фото2], перезапустить таймер
NewMessage(grouped_id=42, media=фото3)  → buffer[42]=[фото1,фото2,фото3], перезапустить таймер
--- 0.8 сек тишины ---
Таймер: send_file(files=[фото1,фото2,фото3]) → save 3 маппинга
```

Буфер передаётся в хендлер как параметр (или хендлер живёт внутри воркера как метод).
