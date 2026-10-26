"""Decide which TaleWeaver roles a provider model can serve: text ("llm") and/or "image".

Provider model lists mix chat, image, audio, embedding and moderation models. Offering
an embedding model as a story model only produces runtime errors, so every list is
filtered by capability before it reaches the UI.
"""

from typing import Any, Literal

ModelKind = Literal["llm", "image"]
Kinds = frozenset[str]

LLM: Kinds = frozenset({"llm"})
IMAGE: Kinds = frozenset({"image"})
LLM_AND_IMAGE: Kinds = frozenset({"llm", "image"})
NONE: Kinds = frozenset()

_OPENAI_IMAGE_PREFIXES = ("gpt-image", "chatgpt-image", "dall-e")
_OPENAI_TEXT_PREFIXES = ("gpt-", "chatgpt-", "o1", "o3", "o4")
# Text-family ids that are not chat-completion models.
_OPENAI_NON_CHAT_MARKERS = (
    "audio",
    "realtime",
    "transcribe",
    "tts",
    "search",
    "embedding",
    "instruct",
    "codex",
    "moderation",
)
_GOOGLE_SKIP_MARKERS = ("tts", "embedding")


def classify_openai(model_id: str) -> Kinds:
    """OpenAI exposes no capability metadata, so ids are matched by family."""
    if model_id.startswith(_OPENAI_IMAGE_PREFIXES):
        return IMAGE
    if not model_id.startswith(_OPENAI_TEXT_PREFIXES):
        return NONE
    if any(marker in model_id for marker in _OPENAI_NON_CHAT_MARKERS):
        return NONE
    return LLM


def classify_google(model_id: str, methods: list[str]) -> Kinds:
    """Gemini image models carry "image" in the id; Imagen models start with "imagen"."""
    if any(marker in model_id for marker in _GOOGLE_SKIP_MARKERS):
        return NONE
    if model_id.startswith("imagen") or "image" in model_id:
        return IMAGE
    if "generateContent" in methods:
        return LLM
    return NONE


def classify_openrouter(item: dict[str, Any]) -> Kinds:
    """OpenRouter reports output modalities; models that output images are image models."""
    architecture = item.get("architecture") or {}
    outputs = architecture.get("output_modalities") or ["text"]
    if "image" in outputs:
        return IMAGE
    if "text" in outputs:
        return LLM
    return NONE
