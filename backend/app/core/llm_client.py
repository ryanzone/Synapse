"""
LLM Client for Synapse backend.

Wraps the LM Studio OpenAI-compatible REST API using the official openai
Python SDK.  Provides a clean, reusable interface for:
- Text generation (single-turn)
- Chat completion (multi-turn)
- Streaming chat
- Vision (image + text) inference
- Runtime model switching
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import AsyncGenerator, Optional

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.core.config import Settings, get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """
    Async client for LM Studio's OpenAI-compatible API.

    All methods are coroutines and must be awaited.  The client is
    stateless and thread-safe; it can be shared across the application.

    Args:
        settings: Application settings.  Defaults to the global singleton.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._client = AsyncOpenAI(
            base_url=self._settings.lmstudio_base_url,
            api_key=self._settings.lmstudio_api_key,
        )
        logger.info(
            "LLMClient initialised — base_url={}",
            self._settings.lmstudio_base_url,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        Single-turn text generation.

        Args:
            prompt:      The user prompt.
            model:       Model identifier override.
            temperature: Sampling temperature.
            max_tokens:  Maximum tokens to generate.

        Returns:
            The generated text string.
        """
        resolved_model = model or self._settings.default_model
        logger.debug("generate() — model={} prompt_len={}", resolved_model, len(prompt))

        response = await self._client.chat.completions.create(
            model=resolved_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        logger.debug("generate() — output_len={}", len(content))
        return content

    async def chat(
        self,
        messages: list[ChatCompletionMessageParam],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        Multi-turn chat completion.

        Args:
            messages:    Full conversation history in OpenAI message format.
            model:       Model identifier override.
            temperature: Sampling temperature.
            max_tokens:  Maximum tokens to generate.

        Returns:
            The assistant's reply as a string.
        """
        resolved_model = model or self._settings.default_model
        logger.debug("chat() — model={} turns={}", resolved_model, len(messages))

        response = await self._client.chat.completions.create(
            model=resolved_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        logger.debug("chat() — output_len={}", len(content))
        return content

    async def stream(
        self,
        messages: list[ChatCompletionMessageParam],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming multi-turn chat completion.

        Yields text delta strings as they arrive from the API.

        Args:
            messages:    Full conversation history.
            model:       Model identifier override.
            temperature: Sampling temperature.
            max_tokens:  Maximum tokens to generate.

        Yields:
            Incremental text chunks.
        """
        resolved_model = model or self._settings.default_model
        logger.debug("stream() — model={} turns={}", resolved_model, len(messages))

        async with await self._client.chat.completions.create(
            model=resolved_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        ) as stream_response:
            async for chunk in stream_response:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

    async def vision(
        self,
        prompt: str,
        image_source: str | Path,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        Vision inference — analyse an image with an accompanying text prompt.

        Args:
            prompt:       Instruction or question about the image.
            image_source: Either a URL string or a local file Path.
            model:        Model identifier override (defaults to vision model).
            temperature:  Sampling temperature.
            max_tokens:   Maximum tokens to generate.

        Returns:
            The model's textual response about the image.
        """
        resolved_model = model or self._settings.vision_model
        logger.debug("vision() — model={} source={}", resolved_model, image_source)

        image_content: dict
        if isinstance(image_source, Path) or (
            isinstance(image_source, str) and not image_source.startswith("http")
        ):
            image_content = self._encode_local_image(Path(image_source))
        else:
            image_content = {
                "type": "image_url",
                "image_url": {"url": str(image_source)},
            }

        response = await self._client.chat.completions.create(
            model=resolved_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        image_content,
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        logger.debug("vision() — output_len={}", len(content))
        return content
    async def generate_json(
        self,
        prompt: str,
        system: str = "",
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> dict:

        resolved_model = model or self._settings.default_model

        messages = []

        if system:
            messages.append(
                {
                    "role": "system",
                    "content": system,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        response = await self._client.chat.completions.create(
            model=resolved_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content or "{}"

        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(content[start:end])
            return json.loads(content)
        except Exception:
            logger.warning("Model did not return valid JSON.")
            return {
                "summary": content,
                "success": True,
                "goal_complete": False,
                "importance": 0.5,
                "confidence": 0.5,
                "lessons": [],
                "steps": [],
                "reasoning": content,
            }
    
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _encode_local_image(path: Path) -> dict:
        """
        Base64-encode a local image file for the vision API.

        Args:
            path: Filesystem path to the image.

        Returns:
            OpenAI-compatible image_url content block.

        Raises:
            FileNotFoundError: If the path does not exist.
            ValueError: If the file extension is not a recognised image type.
        """
        suffix_to_mime = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        suffix = path.suffix.lower()
        mime_type = suffix_to_mime.get(suffix)
        if mime_type is None:
            raise ValueError(
                f"Unsupported image extension '{suffix}'. "
                f"Supported: {list(suffix_to_mime.keys())}"
            )
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {path}")

        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
        }
    
    