"""Configuration read from environment variables.

Model IDs and the base URL are set through environment variables so they can be
changed without code edits, matching the README's "Environment variables"
section.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Resolved configuration for the AI layer."""

    meta_api_base_url: str
    model_api_key: str
    chat_model: str
    transcribe_model: str
    embedding_model: str
    ollama_base_url: str
    no_match_threshold: float

    @property
    def has_api_key(self) -> bool:
        return bool(self.model_api_key)


def load_config(env: dict | None = None) -> Config:
    """Build a Config from the process environment (or an injected mapping)."""

    env = os.environ if env is None else env
    return Config(
        meta_api_base_url=env.get("META_API_BASE_URL", "https://api.meta.ai/v1"),
        model_api_key=env.get("MODEL_API_KEY", ""),
        chat_model=env.get("META_CHAT_MODEL", "muse-spark"),
        transcribe_model=env.get("META_TRANSCRIBE_MODEL", "muse-voice-transcribe"),
        embedding_model=env.get("EMBEDDING_MODEL", "nomic-embed-text"),
        ollama_base_url=env.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        no_match_threshold=float(env.get("NO_MATCH_THRESHOLD", "0.55")),
    )
