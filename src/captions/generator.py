"""Generate Arabic-only ASS captions from automatic audio alignment."""

from pathlib import Path
import subprocess
from typing import Any, Dict, List

from ..timing.aligner import (
    AlignmentGroup,
    AlignmentResult,
    AlignmentValidator,
    ArabicTokenizer,
    AutomaticAligner,
    TimingRepository,
)


class CaptionGenerator:
    """Create Arabic captions using one shared audio timeline."""

    MAX_WORDS = 3

    def __init__(self, config, timing_root="data/timings", cache_root="data/timing_cache"):
        self.config = config
        self.video_width = config["video"]["width"]
        self.video_height = config["video"]["height"]
        self.arabic_size = config["fonts"]["arabic"]["size"]
        self.arabic_font = self._resolve_arabic_font(
            config["fonts"]["arabic"].get("name", "Amiri")
        )
        self.arabic_y = int(self.video_height * config["layout"]["arabic_y_percent"] / 100)
        alignment_config = config.get("timing", {}).get("alignment", {})
        self.max_words = int(alignment_config.get("max_words_per_caption", self.MAX_WORDS))
        self.repository = TimingRepository(
            root=alignment_config.get("timings_dir", timing_root),
            cache_root=alignment_config.get("cache_dir", cache_root),
        )
        self.aligner = AutomaticAligner(
            max_words=self.max_words,
            analysis_rate=alignment_config.get("analysis_sample_rate", 16000),
        )
        self.validator = AlignmentValidator()

    @staticmethod
    def _resolve_arabic_font(requested: str) -> str:
        """Resolve an installed font family for FFmpeg/libass.

        The workflow installs Amiri and Noto fonts, but the requested family
        may differ between Windows and Ubuntu. Using ``fc-match`` prevents
        libass from silently selecting a font with missing Quranic glyphs.
        """
        candidates = []
        for candidate in (requested, "Amiri", "Noto Naskh Arabic", "Noto Sans Arabic"):
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        for candidate in candidates:
            try:
                result = subprocess.run(
                    ["fc-match", "-f", "%{family}", candidate],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                family = (result.stdout or "").split(",", 1)[0].strip()
                if family and family.lower() not in {"dejavu sans", "sans"}:
                    print(f"   🔤 الخط العربي المستخدم: {family}")
                    return family
            except (OSError, subprocess.SubprocessError):
                break

        print(f"   🔤 الخط العربي المستخدم (fallback): {requested or 'Amiri'}")
        return requested or "Amiri"

    def _format_time(self, seconds):
        """Convert seconds to ASS centisecond time."""
        seconds = max(0.0, float(seconds))
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"

    def _create_header(self):
        return f"""[Script Info]
Title: Quran Daily Reel - Arabic Synchronized Captions
ScriptType: v4.00+
PlayResX: {self.video_width}
PlayResY: {self.video_height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Arabic,{self.arabic_font},{self.arabic_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,6,4,5,50,50,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    @staticmethod
    def _escape_ass_text(text: str) -> str:
        return (text or "").replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

    def generate_ass(self, segments, output_path, **kwargs):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = self._create_header()

        for segment in segments:
            start = self._format_time(segment["start"])
            end = self._format_time(max(segment["end"], segment["start"] + 0.01))
            text = self._escape_ass_text(segment["arabic"])
            content += (
                f"Dialogue: 0,{start},{end},Arabic,,0,0,0,,"
                f"{{\\pos({self.video_width // 2},{self.arabic_y})}}{text}\n"
            )

        with output_path.open("w", encoding="utf-8") as handle:
            handle.write(content)
        return str(output_path)

    def create_segments_from_ayahs(
        self,
        ayahs_data,
        padding_before=0.2,
        reciter_id=None,
        timeline=None,
    ):
        """Align Arabic ayahs and always return usable caption segments."""
        segments: List[Dict[str, Any]] = []
        timeline_items = (timeline or {}).get("items", [])
        current_time = float(padding_before)

        for index, ayah in enumerate(ayahs_data):
            arabic = ayah.get("arabic") or ""
            audio_path = ayah.get("audio_path")
            duration = max(0.001, float(ayah.get("duration") or 0.001))

            if index < len(timeline_items):
                timeline_item = timeline_items[index]
                ayah_start = float(timeline_item.get("start", current_time))
                duration = max(0.001, float(timeline_item.get("duration", duration)))
            else:
                ayah_start = current_time

            alignment = self._get_alignment(
                ayah=ayah,
                arabic=arabic,
                audio_path=audio_path,
                duration=duration,
                reciter_id=reciter_id,
            )

            print(
                f"   📝 الآية {ayah.get('surah')}:{ayah.get('ayah')} - "
                f"{alignment.mode} / {alignment.source} / "
                f"ثقة {alignment.confidence:.2f} / {len(alignment.groups)} مقطع"
            )

            previous_end = ayah_start
            for group in self._fit_groups_to_display(alignment, arabic):
                start = max(ayah_start, ayah_start + group.start)
                end = min(ayah_start + duration, ayah_start + group.end)
                if end <= start:
                    continue
                start = max(start, previous_end)
                if end <= start:
                    continue
                segments.append({
                    "start": start,
                    "end": end,
                    "arabic": group.arabic,
                    "surah": ayah.get("surah"),
                    "ayah": ayah.get("ayah"),
                    "confidence": group.confidence,
                    "alignment_source": group.source,
                })
                previous_end = end

            current_time = ayah_start + duration

        print(f"   ✅ إجمالي {len(segments)} مقطع عربي متزامن تلقائيًا")
        return segments

    def _get_alignment(self, ayah, arabic, audio_path, duration, reciter_id):
        tokens = ArabicTokenizer.split(arabic)
        surah = int(ayah.get("surah") or 0)
        ayah_number = int(ayah.get("ayah") or 0)

        if reciter_id and surah and ayah_number and audio_path:
            precomputed = self.repository.load_precomputed(
                reciter_id, surah, ayah_number, arabic, duration
            )
            if precomputed:
                return precomputed

            cached = self.repository.load_cached(
                reciter_id, surah, ayah_number, audio_path, arabic
            )
            if cached:
                return cached

        if audio_path:
            alignment = self.aligner.align(audio_path, arabic, known_duration=duration)
        else:
            alignment = self.aligner._ayah_fallback(tokens, duration)

        alignment = self._clamp_alignment(alignment, duration, tokens)
        if not self.validator.is_valid(alignment, duration, len(tokens)):
            alignment = self.aligner._ayah_fallback(tokens, duration)
        if reciter_id and surah and ayah_number and audio_path:
            self.repository.save_cached(
                reciter_id, surah, ayah_number, audio_path, arabic, alignment
            )
        return alignment

    @staticmethod
    def _clamp_alignment(alignment, duration, tokens):
        groups = []
        for group in alignment.groups:
            start = max(0.0, min(float(group.start), duration))
            end = max(start, min(float(group.end), duration))
            if end <= start:
                continue
            groups.append(
                AlignmentGroup(
                    start=start,
                    end=end,
                    word_indices=[i for i in group.word_indices if 0 <= i < len(tokens)],
                    arabic=group.arabic or " ".join(tokens),
                    confidence=group.confidence,
                    source=group.source,
                )
            )
        if not groups:
            return AutomaticAligner()._ayah_fallback(tokens, duration)
        return AlignmentResult(
            groups=groups,
            confidence=alignment.confidence,
            mode=alignment.mode,
            speech_start=groups[0].start,
            speech_end=groups[-1].end,
            duration=duration,
            source=alignment.source,
        )

    def _fit_groups_to_display(self, alignment, arabic):
        """Keep timing groups readable without inventing a new clock."""
        tokens = ArabicTokenizer.split(arabic)
        output: List[AlignmentGroup] = []
        for group in alignment.groups:
            indices = group.word_indices or list(range(len(tokens)))
            if len(indices) <= self.max_words:
                output.append(group)
                continue

            selected = [tokens[i] for i in indices if i < len(tokens)]
            weights = ArabicTokenizer.weights(selected)
            total_weight = max(0.001, sum(weights))
            running = 0.0
            for offset in range(0, len(selected), self.max_words):
                part = selected[offset : offset + self.max_words]
                part_weight = sum(weights[offset : offset + len(part)])
                part_start = group.start + (group.end - group.start) * (running / total_weight)
                running += part_weight
                part_end = group.start + (group.end - group.start) * (running / total_weight)
                output.append(
                    AlignmentGroup(
                        start=part_start,
                        end=part_end,
                        word_indices=indices[offset : offset + len(part)],
                        arabic=" ".join(part),
                        confidence=min(group.confidence, 0.72),
                        source=f"{group.source}:display-split",
                    )
                )
        return output
