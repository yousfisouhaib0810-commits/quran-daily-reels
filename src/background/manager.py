"""إدارة فيديوهات الخلفية."""
from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional


class BackgroundManager:
    """مدير الخلفيات مع دعم الذكاء الاصطناعي وفلترة الأشخاص."""

    def __init__(
        self,
        pexels_api,
        cache_dir: str = "data/backgrounds",
        used_file: str = "state/used_backgrounds.json",
        banned_file: str = "state/banned_backgrounds.json",
        advisor=None,
        person_detector=None,
        max_attempts: int = 5
    ) -> None:
        self.pexels = pexels_api
        self.advisor = advisor
        self.person_detector = person_detector
        self.max_attempts = max(1, max_attempts)

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.used_file = Path(used_file)
        self.banned_file = Path(banned_file)
        self.used_backgrounds = self._load_list(self.used_file)
        self.banned_backgrounds = set(self._load_list(self.banned_file))

    @staticmethod
    def _load_list(path: Path) -> List[int]:
        if path.exists():
            with open(path, "r", encoding="utf-8") as handler:
                try:
                    data = json.load(handler)
                    if isinstance(data, list):
                        return data
                except json.JSONDecodeError:
                    pass
        return []

    @staticmethod
    def _save_list(path: Path, values: List[int]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handler:
            json.dump(values, handler)

    def _remember_used(self, background_id: int) -> None:
        self.used_backgrounds.append(background_id)
        # لا نحتاج للاحتفاظ بسجل ضخم
        if len(self.used_backgrounds) > 200:
            self.used_backgrounds = self.used_backgrounds[-200:]
        self._save_list(self.used_file, self.used_backgrounds)

    def _ban_background(self, background_id: int) -> None:
        if background_id not in self.banned_backgrounds:
            self.banned_backgrounds.add(background_id)
            self._save_list(self.banned_file, sorted(self.banned_backgrounds))

    def get_random_background(
        self,
        duration_needed: float,
        search_queries: Optional[Iterable[str]] = None,
        context: Optional[dict] = None,
        orientation: str = "portrait",
        min_duration: Optional[int] = None
    ):
        """الحصول على خلفية مناسبة مع محاولات متعددة."""
        base_queries = list(search_queries or ["sky clouds", "nature calm", "sunset light"])
        ai_queries: List[str] = []

        if self.advisor and context:
            ai_queries = self.advisor.suggest_queries(context, base_queries)
            if ai_queries:
                print(f"   🤖 اقتراح الذكاء الاصطناعي: {ai_queries}")

        queries = self._merge_queries(ai_queries, base_queries)
        target_min_duration = max(10, int(round(duration_needed)))
        if min_duration:
            target_min_duration = max(target_min_duration, int(min_duration))

        attempts = 0

        for query in queries:
            videos = self.pexels.search_videos(
                query=query,
                orientation=orientation,
                min_duration=target_min_duration
            )
            random.shuffle(videos)

            for video in videos:
                if video["id"] in self.banned_backgrounds:
                    continue
                if video["id"] in self.used_backgrounds[-50:]:
                    continue
                if attempts >= self.max_attempts:
                    print("   ⚠️ تجاوزنا الحد الأقصى للمحاولات دون العثور على خلفية مناسبة.")
                    return None

                attempts += 1
                local_path = self.pexels.download_video(video["url"], video["id"])
                if not local_path:
                    continue

                if self.person_detector and self.person_detector.contains_person(local_path):
                    print(f"   ⏭️ تم استبعاد الفيديو {video['id']} لاحتوائه على أشخاص")
                    self._ban_background(video["id"])
                    continue

                self._remember_used(video["id"])
                return {
                    "id": video["id"],
                    "path": local_path,
                    "duration": video["duration"]
                }

        print("   ⚠️ لم يتم العثور على خلفية مطابقة للمعايير.")
        return None

    @staticmethod
    def _merge_queries(primary: Iterable[str], fallback: Iterable[str]) -> List[str]:
        seen = set()
        merged: List[str] = []
        for source in (primary, fallback):
            for query in source:
                key = query.strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                merged.append(query.strip())
        return merged

    def prepare_background(self, input_path, output_path, target_duration, width=1080, height=1920):
        """تحضير الخلفية: قص + scale مناسب للـ 9:16."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", str(input_path),
            "-t", str(target_duration),
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-an",
            str(output_path)
        ]

        subprocess.run(cmd, capture_output=True, check=True)

        return str(output_path)
