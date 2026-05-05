from telethon import TelegramClient, events
from telethon.tl.types import UpdateMessageReactions

from src.core.config import AccountConfig, AppConfig
from src.core.logging import get_logger
from src.db.repository import MappingRepository
from src.handlers.albums import handle_album
from src.handlers.deletions import handle_delete
from src.handlers.edits import handle_edit
from src.handlers.messages import handle_new_message
from src.handlers.reactions import handle_reaction

log = get_logger(__name__)


class UserbotWorker:
    """Wraps a single TelegramClient and registers all event handlers."""

    def __init__(
        self,
        account: AccountConfig,
        cfg: AppConfig,
        repo: MappingRepository,
        api_id: int,
        api_hash: str,
    ) -> None:
        self._account = account
        self._cfg = cfg
        self._repo = repo
        self._client = TelegramClient(account.session_file, api_id, api_hash)
        if cfg.test_mode:
            self._client.session.set_dc(2, "149.154.167.40", 80)
        self._handlers_registered = False

    @property
    def client(self) -> TelegramClient:
        return self._client

    async def start(self, catch_up: bool = False) -> None:
        log.info("worker.starting", session=self._account.session_file, catch_up=catch_up)

        if not self._handlers_registered:
            self._register_handlers()
            self._handlers_registered = True

        await self._client.connect()

        if catch_up:
            await self._client.catch_up()

        log.info("worker.started", session=self._account.session_file)

    async def stop(self) -> None:
        log.info("worker.stopping", session=self._account.session_file)
        await self._client.disconnect()
        log.info("worker.stopped", session=self._account.session_file)

    def _register_handlers(self) -> None:
        monitored = self._get_monitored_chats()

        async def on_new_message(event: events.NewMessage.Event) -> None:
            try:
                await handle_new_message(event, self._client, self._repo, self._cfg)
            except Exception:
                log.exception("handler.error", handler="new_message")

        self._client.add_event_handler(
            on_new_message,
            events.NewMessage(chats=monitored, incoming=True),
        )

        async def on_edit(event: events.MessageEdited.Event) -> None:
            try:
                await handle_edit(event, self._client, self._repo, self._cfg)
            except Exception:
                log.exception("handler.error", handler="edit")

        self._client.add_event_handler(
            on_edit,
            events.MessageEdited(chats=monitored, incoming=True),
        )

        async def on_delete(event: events.MessageDeleted.Event) -> None:
            try:
                await handle_delete(event, self._client, self._repo, self._cfg)
            except Exception:
                log.exception("handler.error", handler="delete")

        self._client.add_event_handler(
            on_delete,
            events.MessageDeleted(chats=monitored),
        )

        async def on_album(event: events.Album.Event) -> None:
            try:
                await handle_album(event, self._client, self._repo, self._cfg)
            except Exception:
                log.exception("handler.error", handler="album")

        self._client.add_event_handler(
            on_album,
            events.Album(chats=monitored, incoming=True),
        )

        async def on_reaction(update: UpdateMessageReactions) -> None:
            try:
                await handle_reaction(update, self._client, self._repo, self._cfg)
            except Exception:
                log.exception("handler.error", handler="reaction")

        self._client.add_event_handler(
            on_reaction,
            events.Raw(UpdateMessageReactions),
        )

    def _get_monitored_chats(self) -> list[int]:
        chats: list[int] = []
        for m in self._cfg.mappings:
            chats.append(m.merchant_chat)
            chats.append(m.support_chat)
        return chats
