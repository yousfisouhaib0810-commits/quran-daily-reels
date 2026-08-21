"""Automatic timing for Qur'anic audio.

The audio provider remains EveryAyah.  This module deliberately keeps two
different concerns separate:

* pre-computed word timings, when a matching timing file is available; and
* a deterministic local aligner that always produces a usable result when it
  is not.

The local aligner is not a speech recognizer.  It uses the known ayah text,
adaptive speech boundaries, energy valleys, Arabic word complexity and a
monotonic dynamic-programming path.  That makes it a much safer fallback than
splitting an ayah into equal-duration words or treating every silence as a
word boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import unicodedata

from pydub import AudioSegment


_ARABIC_DIGITS = re.compile(r"^[\u0660-\u0669\u06F0-\u06F9]+$")
_QURAN_MARKS = set(
    "\u0610\u0611\u0612\u0613\u0614\u0615\u0616\u0617\u0618\u0619\u061A"
    "\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652\u0653\u0654\u0655"
    "\u0656\u0657\u0658\u0659\u065A\u065B\u065C\u065D\u065E\u065F\u0670"
    "\u06D6\u06D7\u06D8\u06D9\u06DA\u06DB\u06DC\u06DD\u06DE\u06DF\u06E0"
    "\u06E1\u06E2\u06E3\u06E4\u06E5\u06E6\u06E7\u06E8\u06E9\u06EA\u06EB\u06EC\u06ED"
)


@dataclass
class AlignmentGroup:
    """A visually displayable group of Arabic words."""

    start: float
    end: float
    word_indices: List[int]
    arabic: str
    confidence: float
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AlignmentResult:
    """Alignment output for one ayah audio file."""

    groups: List[AlignmentGroup]
    confidence: float
    mode: str
    speech_start: float
    speech_end: float
    duration: float
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "groups": [group.to_dict() for group in self.groups],
            "confidence": self.confidence,
            "mode": self.mode,
            "speech_start": self.speech_start,
            "speech_end": self.speech_end,
            "duration": self.duration,
            "source": self.source,
        }


class AlignmentValidator:
    """Hard safety checks before timing reaches the renderer."""

    @staticmethod
    def is_valid(result: AlignmentResult, duration: float, token_count: int) -> bool:
        if not result.groups or duration <= 0 or token_count <= 0:
            return False
        previous_end = -0.001
        seen = set()
        for group in result.groups:
            if group.start < -0.01 or group.end > duration + 0.01 or group.end <= group.start:
                return False
            if group.start + 0.05 < previous_end:
                return False
            previous_end = group.end
            seen.update(group.word_indices)
        if result.mode == "ayah":
            return True
        return bool(seen) and max(seen) < token_count


class ArabicTokenizer:
    """Tokenize display text while keeping a clean alignment representation."""

    @staticmethod
    def split(text: str) -> List[str]:
        tokens: List[str] = []
        for raw in (text or "").replace("\u0640", "").split():
            token = raw.strip("\u06DD\u06DE\u06DF\u06E0")
            if not token or _ARABIC_DIGITS.match(token):
                continue
            tokens.append(token)
        return tokens

    @staticmethod
    def normalize(token: str) -> str:
        chars: List[str] = []
        for char in token:
            if char in _QURAN_MARKS or unicodedata.category(char) in {"Mn", "Me"}:
                continue
            if char in "ٱأإآ":
                char = "ا"
            elif char == "ى":
                char = "ي"
            elif char == "ؤ":
                char = "و"
            elif char == "ئ":
                char = "ي"
            chars.append(char)
        return "".join(chars)

    @classmethod
    def weights(cls, tokens: Sequence[str]) -> List[float]:
        """Estimate relative spoken duration without assuming equal word speed."""

        weights: List[float] = []
        long_vowels = set("اويىٰ")
        for token in tokens:
            normalized = cls.normalize(token)
            letters = [c for c in normalized if "\u0600" <= c <= "\u06FF"]
            weight = 0.62 + (0.16 * max(1, len(letters)))
            weight += 0.18 * sum(1 for c in letters if c in long_vowels)
            weight += 0.22 * token.count("ّ")
            weight += 0.06 * sum(1 for c in token if c in "ًٌٍَُِْ")
            weights.append(max(0.7, weight))
        return weights


class TimingRepository:
    """Load and cache timing data without making it a required dependency."""

    def __init__(self, root: str = "data/timings", cache_root: str = "data/timing_cache"):
        self.root = Path(root)
        self.cache_root = Path(cache_root)
        self._loaded: Dict[str, Any] = {}

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)

    def _precomputed_candidates(self, reciter_id: str, surah: int, ayah: int) -> Iterable[Path]:
        reciter_dir = self.root / reciter_id
        safe_dir = self.root / self._safe_name(reciter_id)
        names = [f"{surah}.json", f"{surah:03d}.json", f"{surah:03d}{ayah:03d}.json"]
        for directory in (reciter_dir, safe_dir):
            for name in names:
                yield directory / name
        yield self.root / f"{reciter_id}.json"
        yield self.root / f"{self._safe_name(reciter_id)}.json"

    def _cache_path(self, reciter_id: str, surah: int, ayah: int, audio_path: str, text: str) -> Path:
        audio = Path(audio_path)
        audio_signature = f"{audio}:{audio.stat().st_size if audio.exists() else 0}:{audio.stat().st_mtime_ns if audio.exists() else 0}"
        key = hashlib.sha256(f"{audio_signature}\n{text}".encode("utf-8")).hexdigest()[:20]
        return self.cache_root / self._safe_name(reciter_id) / f"{surah:03d}{ayah:03d}_{key}.json"

    def load_cached(
        self,
        reciter_id: str,
        surah: int,
        ayah: int,
        audio_path: str,
        text: str,
    ) -> Optional[AlignmentResult]:
        path = self._cache_path(reciter_id, surah, ayah, audio_path, text)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return self._result_from_payload(payload)
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def save_cached(
        self,
        reciter_id: str,
        surah: int,
        ayah: int,
        audio_path: str,
        text: str,
        result: AlignmentResult,
    ) -> None:
        path = self._cache_path(reciter_id, surah, ayah, audio_path, text)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            print(f"⚠️ تعذر حفظ ذاكرة التوقيت: {exc}")

    @staticmethod
    def _result_from_payload(payload: Dict[str, Any]) -> AlignmentResult:
        groups = [AlignmentGroup(**group) for group in payload.get("groups", [])]
        return AlignmentResult(
            groups=groups,
            confidence=float(payload.get("confidence", 0.0)),
            mode=str(payload.get("mode", "cached")),
            speech_start=float(payload.get("speech_start", 0.0)),
            speech_end=float(payload.get("speech_end", 0.0)),
            duration=float(payload.get("duration", 0.0)),
            source=str(payload.get("source", "cache")),
        )

    @staticmethod
    def _read_json(path: Path) -> Any:
        key = str(path.resolve())
        if key not in TimingRepository._GLOBAL_JSON_CACHE:
            TimingRepository._GLOBAL_JSON_CACHE[key] = json.loads(path.read_text(encoding="utf-8"))
        return TimingRepository._GLOBAL_JSON_CACHE[key]

    _GLOBAL_JSON_CACHE: Dict[str, Any] = {}

    def load_precomputed(
        self,
        reciter_id: str,
        surah: int,
        ayah: int,
        text: str,
        audio_duration: float,
    ) -> Optional[AlignmentResult]:
        tokens = ArabicTokenizer.split(text)
        for path in self._precomputed_candidates(reciter_id, surah, ayah):
            if not path.exists():
                continue
            try:
                payload = self._read_json(path)
                entry = self._find_entry(payload, surah, ayah)
                if entry is None:
                    continue
                groups = self._entry_to_groups(entry, tokens, audio_duration)
                if not groups:
                    continue
                return AlignmentResult(
                    groups=groups,
                    confidence=self._entry_confidence(entry),
                    mode="precomputed",
                    speech_start=min(g.start for g in groups),
                    speech_end=max(g.end for g in groups),
                    duration=audio_duration,
                    source=str(path),
                )
            except (OSError, ValueError, TypeError, KeyError, IndexError):
                continue
        return None

    @staticmethod
    def _find_entry(payload: Any, surah: int, ayah: int) -> Optional[Dict[str, Any]]:
        if isinstance(payload, dict) and any(key in payload for key in ("groups", "segments", "words")):
            return payload
        entries: List[Any]
        if isinstance(payload, list):
            entries = payload
        elif isinstance(payload, dict):
            entries = payload.get("ayahs") or payload.get("entries") or []
        else:
            return None
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if int(entry.get("surah", surah)) == surah and int(entry.get("ayah", ayah)) == ayah:
                return entry
        if len(entries) == 1 and isinstance(entries[0], dict):
            return entries[0]
        return None

    @staticmethod
    def _entry_confidence(entry: Dict[str, Any]) -> float:
        stats = entry.get("stats") or {}
        errors = sum(float(stats.get(key, 0) or 0) for key in ("insertions", "deletions", "transpositions"))
        return max(0.65, min(0.99, 0.98 - (errors * 0.015)))

    @staticmethod
    def _entry_to_groups(
        entry: Dict[str, Any],
        tokens: Sequence[str],
        audio_duration: float,
    ) -> List[AlignmentGroup]:
        raw_segments = entry.get("segments") or entry.get("groups") or entry.get("words") or []
        if isinstance(raw_segments, dict):
            raw_segments = raw_segments.get("items") or list(raw_segments.values())
        groups: List[AlignmentGroup] = []
        for raw in raw_segments:
            if isinstance(raw, dict):
                start_ms = raw.get("start_msec", raw.get("start_ms", raw.get("start", 0)))
                end_ms = raw.get("end_msec", raw.get("end_ms", raw.get("end", 0)))
                indices = raw.get("word_indices")
                if indices is None:
                    index = int(raw.get("word_index", raw.get("index", 0)))
                    indices = [index]
            elif isinstance(raw, (list, tuple)) and len(raw) >= 4:
                start_index, end_index, start_ms, end_ms = raw[:4]
                indices = list(range(int(start_index), int(end_index)))
            elif isinstance(raw, (list, tuple)) and len(raw) == 3:
                index, start_ms, end_ms = raw
                indices = [int(index)]
            else:
                continue
            indices = [int(i) for i in indices if 0 <= int(i) < len(tokens)]
            start = max(0.0, float(start_ms) / 1000.0)
            end = min(audio_duration, float(end_ms) / 1000.0)
            if indices and end > start:
                groups.append(
                    AlignmentGroup(
                        start=start,
                        end=end,
                        word_indices=indices,
                        arabic=" ".join(tokens[i] for i in indices),
                        confidence=0.95 if len(indices) == 1 else 0.82,
                        source="precomputed",
                    )
                )
        return groups


class AutomaticAligner:
    """A deterministic adaptive aligner that never blocks video generation."""

    ANALYSIS_RATE = 16000
    FRAME_MS = 20
    HOP_MS = 10
    MIN_WORD_MS = 35

    def __init__(self, max_words: int = 3, analysis_rate: int = ANALYSIS_RATE):
        self.max_words = max(1, int(max_words))
        self.analysis_rate = max(8000, int(analysis_rate))

    def align(self, audio_path: str, text: str, known_duration: float = 0.0) -> AlignmentResult:
        tokens = ArabicTokenizer.split(text)
        if not tokens:
            return AlignmentResult([], 0.0, "empty", 0.0, 0.0, 0.0, "automatic")

        try:
            audio = AudioSegment.from_file(str(audio_path))
            duration = max(0.001, len(audio) / 1000.0)
            analysis = audio.set_channels(1).set_frame_rate(self.analysis_rate).set_sample_width(2)
            samples = list(analysis.get_array_of_samples())
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ تعذر تحليل الصوت تلقائيًا: {exc}")
            return self._ayah_fallback(tokens, known_duration)

        energies = self._energy_profile(samples)
        if not energies:
            return self._ayah_fallback(tokens, duration)

        speech_start_frame, speech_end_frame, runs, noise, peak = self._speech_bounds(energies)
        if speech_end_frame <= speech_start_frame:
            return self._ayah_fallback(tokens, duration)

        boundaries = self._dynamic_boundaries(
            len(tokens),
            ArabicTokenizer.weights(tokens),
            speech_start_frame,
            speech_end_frame,
            energies,
            runs,
            noise,
            peak,
        )

        if not boundaries or len(boundaries) != len(tokens) + 1:
            return self._ayah_fallback(
                tokens,
                duration,
                start=speech_start_frame * self.HOP_MS / 1000.0,
                end=min(duration, speech_end_frame * self.HOP_MS / 1000.0),
            )

        intervals = []
        for index in range(len(tokens)):
            start = max(0.0, boundaries[index] * self.HOP_MS / 1000.0)
            end = min(duration, boundaries[index + 1] * self.HOP_MS / 1000.0)
            if end <= start:
                return self._ayah_fallback(
                    tokens,
                    duration,
                    start=speech_start_frame * self.HOP_MS / 1000.0,
                    end=min(duration, speech_end_frame * self.HOP_MS / 1000.0),
                )
            intervals.append((start, end))

        groups = self._group_intervals(tokens, intervals)
        quality = self._quality_score(intervals, ArabicTokenizer.weights(tokens), energies, speech_start_frame, speech_end_frame)
        if quality < 0.64:
            return self._ayah_fallback(
                tokens,
                duration,
                start=speech_start_frame * self.HOP_MS / 1000.0,
                end=min(duration, speech_end_frame * self.HOP_MS / 1000.0),
            )
        mode = "word" if quality >= 0.72 else "phrase"
        return AlignmentResult(
            groups=groups,
            confidence=quality,
            mode=mode,
            speech_start=intervals[0][0],
            speech_end=intervals[-1][1],
            duration=duration,
            source="automatic-energy-dp",
        )

    def _ayah_fallback(
        self,
        tokens: Sequence[str],
        duration: float,
        start: float = 0.0,
        end: Optional[float] = None,
    ) -> AlignmentResult:
        start = max(0.0, min(float(start), max(0.001, duration)))
        end = max(start + 0.001, min(float(end if end is not None else duration), max(0.001, duration)))
        group = AlignmentGroup(
            start=start,
            end=end,
            word_indices=list(range(len(tokens))),
            arabic=" ".join(tokens),
            confidence=0.55 if duration > 0 else 0.0,
            source="automatic-ayah-fallback",
        )
        return AlignmentResult([group], group.confidence, "ayah", start, end, end, "automatic-ayah-fallback")

    def _energy_profile(self, samples: Sequence[int]) -> List[float]:
        frame_size = max(1, int(self.analysis_rate * self.FRAME_MS / 1000))
        hop = max(1, int(self.analysis_rate * self.HOP_MS / 1000))
        if not samples:
            return []
        energies: List[float] = []
        index = 0
        while index < len(samples):
            frame = samples[index : index + frame_size]
            if not frame:
                break
            mean_square = sum(sample * sample for sample in frame) / len(frame)
            rms = math.sqrt(mean_square)
            energies.append(20.0 * math.log10(max(rms, 1.0) / 32768.0))
            index += hop
        return energies

    def _speech_bounds(
        self,
        energies: Sequence[float],
    ) -> Tuple[int, int, List[Tuple[int, int]], float, float]:
        ordered = sorted(energies)
        noise = ordered[max(0, int(len(ordered) * 0.10))]
        peak = max(energies)
        dynamic_range = peak - noise
        threshold = noise + max(5.0, min(15.0, dynamic_range * 0.28))
        active = [energy >= threshold for energy in energies]

        # Close tiny holes, then remove isolated noise bursts. This is only
        # for finding the outer speech boundary and pause candidates.
        max_hole = max(1, int(120 / self.HOP_MS))
        for index in range(1, len(active) - 1):
            if active[index]:
                continue
            left = index - 1
            while left >= 0 and not active[left] and index - left <= max_hole:
                left -= 1
            right = index + 1
            while right < len(active) and not active[right] and right - index <= max_hole:
                right += 1
            if left >= 0 and right < len(active) and active[left] and active[right]:
                for fill in range(left + 1, right):
                    active[fill] = True

        runs: List[Tuple[int, int]] = []
        run_start: Optional[int] = None
        min_run = max(2, int(40 / self.HOP_MS))
        for index, value in enumerate(active + [False]):
            if value and run_start is None:
                run_start = index
            elif not value and run_start is not None:
                if index - run_start >= min_run:
                    runs.append((run_start, index))
                run_start = None

        if not runs:
            return 0, len(energies), [(0, len(energies))], noise, peak

        start = runs[0][0]
        end = runs[-1][1]
        return start, end, runs, noise, peak

    def _dynamic_boundaries(
        self,
        word_count: int,
        weights: Sequence[float],
        start: int,
        end: int,
        energies: Sequence[float],
        runs: Sequence[Tuple[int, int]],
        noise: float,
        peak: float,
    ) -> Optional[List[int]]:
        if word_count == 1:
            return [start, end]
        total = max(1, end - start)
        weight_sum = max(0.001, sum(weights))
        cumulative = []
        running = 0.0
        for weight in weights[:-1]:
            running += weight
            cumulative.append(running / weight_sum)

        pause_centers = [int((left + right) / 2) for (left, right), (next_left, next_right) in zip(runs, runs[1:]) if next_left - right >= 8]
        levels: List[List[int]] = [[start]]
        back_maps: List[Dict[int, int]] = []
        previous_costs: Dict[int, float] = {start: 0.0}
        previous_level = [start]

        for boundary_index, fraction in enumerate(cumulative, start=1):
            expected = start + int(round(total * fraction))
            expected_word = max(1.0, total * weights[boundary_index - 1] / weight_sum)
            window = max(18, int(round(expected_word * 1.55)), int(220 / self.HOP_MS))
            low = max(start + 2, expected - window)
            high = min(end - 2, expected + window)
            step = 1 if window < 40 else 2
            candidates = set(range(low, high + 1, step))
            candidates.update(center for center in pause_centers if low <= center <= high)
            candidates = sorted(candidates)
            if not candidates:
                return None

            current_costs: Dict[int, float] = {}
            current_back: Dict[int, int] = {}
            for current in candidates:
                best: Optional[Tuple[float, int]] = None
                for previous in previous_level:
                    if current - previous < 2:
                        continue
                    previous_cost = previous_costs.get(previous)
                    if previous_cost is None:
                        continue
                    actual = current - previous
                    duration_penalty = abs(actual - expected_word) / max(expected_word, 1.0)
                    boundary_penalty = self._boundary_penalty(current, energies, runs, noise, peak)
                    transition = previous_cost + (1.25 * duration_penalty) + boundary_penalty
                    if best is None or transition < best[0]:
                        best = (transition, previous)
                if best is not None:
                    current_costs[current] = best[0]
                    current_back[current] = best[1]

            if not current_costs:
                return None
            previous_level = sorted(current_costs)
            previous_costs = current_costs
            back_maps.append(current_back)

        # Connect the last internal boundary to the actual speech end.
        expected_last = total * weights[-1] / weight_sum
        best_end: Optional[Tuple[float, int]] = None
        for previous in previous_level:
            actual = end - previous
            if actual < 2:
                continue
            penalty = abs(actual - expected_last) / max(expected_last, 1.0)
            penalty += self._boundary_penalty(end, energies, runs, noise, peak)
            candidate = (previous_costs[previous] + 1.25 * penalty, previous)
            if best_end is None or candidate[0] < best_end[0]:
                best_end = candidate
        if best_end is None:
            return None

        boundaries = [end]
        current = best_end[1]
        for level_index in range(len(back_maps) - 1, -1, -1):
            boundaries.append(current)
            current = back_maps[level_index].get(current, start)
        boundaries.append(start)
        boundaries.reverse()
        return boundaries if len(boundaries) == word_count + 1 else None

    @staticmethod
    def _boundary_penalty(
        frame: int,
        energies: Sequence[float],
        runs: Sequence[Tuple[int, int]],
        noise: float,
        peak: float,
    ) -> float:
        if frame <= 0 or frame >= len(energies):
            return 0.1
        local = energies[frame]
        scale = max(1.0, peak - noise)
        valley = max(0.0, min(1.0, (peak - local) / scale))
        local_min = 1.0 if local <= energies[frame - 1] and local <= energies[min(frame + 1, len(energies) - 1)] else 0.0
        pause_bonus = 0.0
        for left, right in zip(runs, runs[1:]):
            if left[1] <= frame <= right[0] and right[0] - left[1] >= 8:
                pause_bonus = 0.55
                break
        return max(0.0, 0.85 - (0.60 * valley) - (0.18 * local_min) - pause_bonus)

    def _group_intervals(
        self,
        tokens: Sequence[str],
        intervals: Sequence[Tuple[float, float]],
    ) -> List[AlignmentGroup]:
        groups: List[AlignmentGroup] = []
        index = 0
        while index < len(tokens):
            end_index = min(len(tokens), index + self.max_words)
            # Very short groups are merged automatically, but never beyond
            # the configured visual word limit unless the final word itself
            # is shorter than one display frame.
            while end_index < len(tokens):
                duration = intervals[end_index - 1][1] - intervals[index][0]
                next_duration = intervals[end_index][1] - intervals[index][0]
                if duration >= 0.20 or next_duration > 2.20:
                    break
                end_index += 1
            start = intervals[index][0]
            end = intervals[end_index - 1][1]
            groups.append(
                AlignmentGroup(
                    start=start,
                    end=end,
                    word_indices=list(range(index, end_index)),
                    arabic=" ".join(tokens[index:end_index]),
                    confidence=0.78,
                    source="automatic-energy-dp",
                )
            )
            index = end_index
        return groups

    @staticmethod
    def _quality_score(
        intervals: Sequence[Tuple[float, float]],
        weights: Sequence[float],
        energies: Sequence[float],
        start: int,
        end: int,
    ) -> float:
        if not intervals:
            return 0.0
        expected_sum = sum(weights)
        expected = [(end - start) * weight / expected_sum for weight in weights]
        actual = [max(1.0, (right - left) / (end - start) * max(1, len(energies))) for left, right in intervals]
        duration_error = sum(abs(a - b) / max(b, 1.0) for a, b in zip(actual, expected)) / len(expected)
        return max(0.55, min(0.92, 0.90 - (0.16 * min(2.0, duration_error))))
