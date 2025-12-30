from __future__ import annotations

import os
import re
from typing import Optional

from core.settings import load_settings


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _mask_pii(text: str) -> str:
    return _EMAIL_RE.sub("[EMAIL_MASKED]", text)


def _heuristic_category(text: str) -> str:
    lowered = text.lower()
    if "iade" in lowered or "refund" in lowered or "return" in lowered:
        return "return"
    if "kargo" in lowered or "delivery" in lowered or "shipping" in lowered:
        return "delivery"
    if "odeme" in lowered or "payment" in lowered or "charge" in lowered:
        return "payment"
    return "general"


class LLMClient:
    def __init__(self, api_key: Optional[str] = None, use_openai: bool = False) -> None:
        self.api_key = api_key
        self.use_openai = use_openai

    def categorize(self, text: str) -> str:
        if not self.api_key or not self.use_openai:
            return _heuristic_category(text)
        try:
            return self._openai_categorize(text)
        except Exception:
            return _heuristic_category(text)

    def improve_email(self, draft: str) -> str:
        if not self.api_key or not self.use_openai:
            return draft
        try:
            return self._openai_improve_email(draft)
        except Exception:
            return draft

    def _openai_categorize(self, text: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        prompt = (
            "Categorize this customer message into: return, delivery, payment, general. "
            "Return only the label.\nMessage: "
        )
        masked = _mask_pii(text)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a classifier."},
                {"role": "user", "content": f"{prompt}{masked}"},
            ],
            temperature=0,
        )
        label = response.choices[0].message.content.strip().lower()
        return label if label in {"return", "delivery", "payment", "general"} else "general"

    def _openai_improve_email(self, draft: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        masked = _mask_pii(draft)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You improve support emails."},
                {"role": "user", "content": masked},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()


def get_default_llm() -> LLMClient:
    settings = load_settings()
    return LLMClient(api_key=os.getenv("OPENAI_API_KEY"), use_openai=settings.use_openai)
