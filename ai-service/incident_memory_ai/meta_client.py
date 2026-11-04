"""Story 3 — Meta Model API client for Muse Spark.

Acceptance criteria: Python client reads base URL, key and model ID from env
vars; a test call to Muse Spark returns text and supports a JSON response.

The client speaks the OpenAI-compatible ``/chat/completions`` shape that the
Meta Model API exposes. HTTP is done with the standard library so the package
has no third-party runtime dependency; a ``transport`` callable can be injected
to make calls fully offline and testable.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable, Optional

from .config import Config, load_config

# A transport takes (url, headers, body_bytes) and returns the decoded JSON
# response. Injectable so tests never touch the network.
Transport = Callable[[str, dict, bytes], dict]


class MetaModelError(RuntimeError):
    """Raised when the Meta Model API cannot be reached or returns an error."""


def _urllib_transport(url: str, headers: dict, body: bytes, timeout: float = 60.0) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - network path
        detail = exc.read().decode("utf-8", "replace")
        raise MetaModelError(f"Meta Model API returned {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network path
        raise MetaModelError(f"Could not reach Meta Model API: {exc.reason}") from exc


class MetaModelClient:
    """Thin client for Muse Spark chat completions."""

    def __init__(self, config: Optional[Config] = None, transport: Optional[Transport] = None):
        self.config = config or load_config()
        self._transport = transport or _urllib_transport

    def _post(self, payload: dict) -> dict:
        url = f"{self.config.meta_api_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.model_api_key}",
        }
        body = json.dumps(payload).encode("utf-8")
        return self._transport(url, headers, body)

    @staticmethod
    def _extract_text(response: dict) -> str:
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise MetaModelError(f"Unexpected response shape: {response!r}") from exc

    def complete(self, prompt: str, *, system: Optional[str] = None, temperature: float = 0.2) -> str:
        """Return Muse Spark's text answer for a single prompt."""

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = self._post(
            {
                "model": self.config.chat_model,
                "messages": messages,
                "temperature": temperature,
            }
        )
        return self._extract_text(response)

    def complete_json(self, prompt: str, *, system: Optional[str] = None, temperature: float = 0.0) -> dict:
        """Return a parsed JSON object from Muse Spark.

        Requests the API's JSON response mode and parses the returned content.
        Raises MetaModelError if the content is not valid JSON.
        """

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = self._post(
            {
                "model": self.config.chat_model,
                "messages": messages,
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            }
        )
        text = self._extract_text(response)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise MetaModelError(f"Muse Spark did not return valid JSON: {text!r}") from exc
