"""استشارة نموذج لغوي لاختيار خلفيات مناسبة للآيات."""
from __future__ import annotations

import json
import textwrap
from typing import Iterable, List, Optional

import openai


class BackgroundAdvisor:
    """يستدعي نموذج ChatGPT (OpenAI) لتوليد اقتراحات بحث.

    يحاول استخراج قائمة صالحة من عبارات البحث (JSON) بناءً على نص الآية.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_suggestions: int = 3,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_suggestions = max(1, max_suggestions)
        openai.api_key = api_key

    def suggest_queries(
        self,
        context: Optional[dict],
        fallback_queries: Optional[Iterable[str]] = None
    ) -> List[str]:
        """الحصول على قائمة اقتراحات بحوث منظمة."""
        if not self.api_key:
            return []

        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
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
                ],
                max_tokens=700
            )

            message = response["choices"][0]["message"]["content"]
            return self._parse_queries(message)
        except Exception as exc:
            print(f"⚠️ فشل طلب الذكاء الاصطناعي (OpenAI): {exc}")
            return []

    def _build_prompt(self, context: Optional[dict], fallback_queries: Optional[Iterable[str]]) -> str:
        """بناء النص المُرسل للنموذج."""
        surah = context.get("surah") if context else None
        ayah_range = context.get("ayah_range") if context else None
        english_text = context.get("english_preview") if context else ""
        arabic_text = context.get("arabic_preview") if context else ""

        prompt_parts = [
            "You are an expert in Quranic themes and visual storytelling.",
            "Analyze the meaning and emotional tone of these Quran verses.",
            "Return STRICT JSON: {\"queries\": [\"query1\", \"query2\", \"query3\"]}",
            "",
            f"Surah: {surah}" if surah else "",
            f"Ayahs: {ayah_range}" if ayah_range else "",
            "",
            "Arabic text (primary source):",
            arabic_text or "N/A",
            "",
            "English translation:",
            english_text or "N/A",
            "",
            "CRITICAL RULES:",
            "- If verses mention punishment/hell/fire → suggest dark clouds, storms, volcanic landscapes",
            "- If verses mention paradise/mercy/light → suggest sunrises, gardens, peaceful skies",
            "- If verses mention creation/nature → suggest mountains, oceans, forests matching the theme",
            "- If verses mention judgment/warning → suggest dramatic weather, lightning, dark skies",
            "- NEVER suggest people, faces, crowds, mosques interiors, or urban scenes",
            "- Focus on abstract nature: water, sky, mountains, clouds, light, darkness",
            "",
            "Base query ideas (you can adapt these):",
            ", ".join(fallback_queries or []),
            "",
            "Return exactly 3 search queries for Pexels portrait videos that capture the EMOTIONAL TONE and THEME of these verses.",
            "Each query must be 3-6 words in English, focusing on nature/weather/abstract visuals that match the verse meaning."
        ]

        return "\n".join([part for part in prompt_parts if part is not None])

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
