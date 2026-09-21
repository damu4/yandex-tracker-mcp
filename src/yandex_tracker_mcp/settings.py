from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / '.env',
        extra='ignore',
    )

    yandex_tracker_token: str = ''
    yandex_tracker_org_id: str = ''
    yandex_tracker_queue: str = 'LGS'

    @classmethod
    def load(cls) -> Settings:
        return cls()
