from __future__ import annotations

import json
from typing import Any

from anthropic import Anthropic
from openai import OpenAI


class LlmExtractor:
    def __init__(
        self,
        *,
        anthropic_api_key: str | None,
        openai_api_key: str | None,
        preferred: str = "claude",
    ) -> None:
        self._anthropic_api_key = anthropic_api_key
        self._openai_api_key = openai_api_key
        self._preferred = preferred

        self._anthropic: Anthropic | None = (
            Anthropic(api_key=anthropic_api_key) if anthropic_api_key else None
        )
        self._openai: OpenAI | None = OpenAI(api_key=openai_api_key) if openai_api_key else None

    def _ensure_provider(self) -> str:
        if self._preferred == "claude" and self._anthropic:
            return "claude"
        if self._preferred == "openai" and self._openai:
            return "openai"
        if self._anthropic:
            return "claude"
        if self._openai:
            return "openai"
        raise RuntimeError("No LLM provider configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.")

    def extract_food_invoice_json(
        self,
        *,
        base64_png_images: list[str],
        system_prompt: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        provider = self._ensure_provider()
        if provider == "claude":
            return self._extract_with_claude(
                base64_png_images=base64_png_images,
                system_prompt=system_prompt,
                model=model or "claude-3-5-sonnet-20241022",
            )
        return self._extract_with_openai(
            base64_png_images=base64_png_images,
            system_prompt=system_prompt,
            model=model or "gpt-4o",
        )

    def _extract_with_claude(
        self,
        *,
        base64_png_images: list[str],
        system_prompt: str,
        model: str,
    ) -> dict[str, Any]:
        assert self._anthropic is not None

        content: list[dict[str, Any]] = []
        for img in base64_png_images[:3]:
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": img},
                }
            )
        content.append({"type": "text", "text": "Extract the invoice into the required JSON schema."})

        msg = self._anthropic.messages.create(
            model=model,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
        )

        text = "".join(block.text for block in msg.content if getattr(block, "text", None))
        return json.loads(text)

    def _extract_with_openai(
        self,
        *,
        base64_png_images: list[str],
        system_prompt: str,
        model: str,
    ) -> dict[str, Any]:
        assert self._openai is not None

        user_content: list[dict[str, Any]] = []
        for img in base64_png_images[:3]:
            user_content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}
            )

        resp = self._openai.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
        )
        return json.loads(resp.choices[0].message.content or "{}")

