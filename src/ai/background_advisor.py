"""استشارة نموذج لغوي لاختيار خلفيات مناسبة للآيات."""
from __future__ import annotations

import json
import textwrap
from typing import Iterable, List, Optional

import requests


class BackgroundAdvisor:
    """يستدعي نموذج ذكاء اصطناعي (OpenRouter) لتوليد اقتراحات بحث."""

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.3,
        max_suggestions: int = 3,
        provider: str = "openrouter"
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_suggestions = max(1, max_suggestions)
        self.provider = provider
        self.endpoint = self._resolve_endpoint(provider)

    @staticmethod
    def _resolve_endpoint(provider: str) -> str:
        if provider == "openrouter":
            return "https://openrouter.ai/api/v1/chat/completions"
        raise ValueError(f"مزود غير مدعوم: {provider}")

    def suggest_queries(
        self,
        context: Optional[dict],
        fallback_queries: Optional[Iterable[str]] = None
    ) -> List[str]:
        """الحصول على قائمة اقتراحات بحوث منظمة."""
        if not self.api_key:
            return []

        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a cinematic director choosing stock video backgrounds "
                        "for short-form Quran recitations. Always avoid humans, faces, "
                        "silhouettes, crowds, text overlays, mosques interiors, and anything "
                        "that could distract. Prefer nature, skies, light, water, abstract particles, "
                        "or atmospheric shots that evoke the emotions of the verses."
                    )
                },
                {
                    "role": "user",
                    "content": self._build_prompt(context, fallback_queries)
                }
            ]
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/",
            "X-Title": "Quran Daily Reels Bot"
        }

        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                data=json.dumps(payload),
                timeout=45
            )
            response.raise_for_status()
            data = response.json()
            message = data["choices"][0]["message"]["content"]
            return self._parse_queries(message)
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ فشل طلب الذكاء الاصطناعي: {exc}")
            return []

    def _build_prompt(self, context: Optional[dict], fallback_queries: Optional[Iterable[str]]) -> str:
        """بناء النص المُرسل للنموذج."""
        surah = context.get("surah") if context else None
        ayah_range = context.get("ayah_range") if context else None
        english_text = context.get("english_preview") if context else ""
        arabic_text = context.get("arabic_preview") if context else ""

        prompt_parts = [
            "You must return STRICT JSON with the schema: {\n  \"queries\": [\"query\"]\n}.",
            f"Surah: {surah}" if surah else "",
            f"Ayahs: {ayah_range}" if ayah_range else "",
            "Arabic excerpt:",
            textwrap.shorten(arabic_text or "", width=280, placeholder="…"),
            "English excerpt:",
            textwrap.shorten(english_text or "", width=480, placeholder="…"),
            "Base queries you can remix:",
            ", ".join(fallback_queries or [])
        ]

        prompt_parts.append(
            "Return maximum of 3 distinct English search queries suited for Pexels portrait videos."
        )
        prompt_parts.append(
            "All suggestions must implicitly exclude humans. You can mention the time of day, camera style,"
            " and weather."
        )

        return "\n".join([part for part in prompt_parts if part])

    def _parse_queries(self, message: str) -> List[str]:
        """استخراج قائمة الاستعلامات من استجابة النموذج."""
        if not message:
            return []

        content = message.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if "```" in content:
                content = content.split("```", 1)[0]

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            # محاولة استخراج أول JSON صالح داخل النص
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                snippet = content[start:end + 1]
                try:
                    parsed = json.loads(snippet)
                except json.JSONDecodeError:
                    return []
            else:
                return []

        queries = parsed.get("queries", []) if isinstance(parsed, dict) else []
        cleaned = []
        for query in queries:
            if not isinstance(query, str):
                continue
            q = query.strip()
            if q and q.lower() not in (s.lower() for s in cleaned):
                cleaned.append(q)
            if len(cleaned) >= self.max_suggestions:
                break
        return cleaned
