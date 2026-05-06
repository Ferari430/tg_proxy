import os
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, model_validator


class TelegramConfig(BaseModel):
    api_id: int
    api_hash: str


class ActiveHours(BaseModel):
    start: str  # "HH:MM"
    end: str    # "HH:MM"

    @property
    def start_minutes(self) -> int:
        h, m = map(int, self.start.split(":"))
        return h * 60 + m

    @property
    def end_minutes(self) -> int:
        h, m = map(int, self.end.split(":"))
        return h * 60 + m


class AccountConfig(BaseModel):
    session_file: str
    active_hours: ActiveHours | None = None  # None → 24/7


class GroupMapping(BaseModel):
    merchant_chat: int
    support_chat: int


class HumanDelay(BaseModel):
    min_seconds: float = 1.0
    max_seconds: float = 4.0


class AppConfig(BaseModel):
    telegram: TelegramConfig
    accounts: list[AccountConfig]
    mappings: list[GroupMapping]
    human_delay: HumanDelay = HumanDelay()
    timezone: str = "Europe/Moscow"
    test_mode: bool = False

    @model_validator(mode="after")
    def validate_accounts(self) -> "AppConfig":
        if len(self.accounts) > 2:
            raise ValueError("at most 2 accounts supported")
        return self

    def find_mirror(self, chat_id: int) -> int | None:
        """Return the mirror chat_id for the given chat, or None if not mapped."""
        for m in self.mappings:
            if m.merchant_chat == chat_id:
                return m.support_chat
            if m.support_chat == chat_id:
                return m.merchant_chat
        return None

    def is_monitored(self, chat_id: int) -> bool:
        return self.find_mirror(chat_id) is not None


_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def _expand_env(value: object) -> object:
    """Recursively expand ${VAR} placeholders in strings."""
    if isinstance(value, str):
        return _ENV_VAR_RE.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)
    expanded = _expand_env(raw)
    return AppConfig.model_validate(expanded)
