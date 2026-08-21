"""
معالجة الصوت - دمج ملفات الآيات وإضافة padding
"""
import json
import subprocess
from pathlib import Path

from pydub import AudioSegment


class AudioProcessor:
    """معالج الصوت"""
    
    def __init__(self, output_dir="temp"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.last_timeline = None
    
    def concatenate_audio(
        self,
        audio_files,
        output_path,
        padding_before=0.2,
        padding_after=0.2,
        timeline_items=None,
        timeline_path=None,
    ):
        """
        دمج ملفات الآيات مع خط زمني sample-accurate.
        
        audio_files: قائمة مسارات ملفات MP3
        timeline_items: بيانات الآيات الموافقة لمسارات الصوت
        timeline_path: مسار اختياري لحفظ خط الزمن بصيغة JSON

        يتم فك كل ملف مرة واحدة إلى PCM موحد ثم دمجه. هذا يمنع تراكم
        فروق MP3/ffprobe التي كانت تجعل توقيت الترجمة يختلف عن الصوت النهائي.
        """
        if not audio_files:
            raise ValueError("لا توجد ملفات صوت للدمج!")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        target_rate = 48000
        target_channels = 2
        target_width = 2

        def sample_count(segment):
            bytes_per_frame = target_channels * target_width
            return len(segment.raw_data) // bytes_per_frame

        combined = AudioSegment.silent(duration=0, frame_rate=target_rate)
        combined = combined.set_channels(target_channels).set_sample_width(target_width)
        before = AudioSegment.silent(
            duration=max(0, int(round(padding_before * 1000))),
            frame_rate=target_rate,
        ).set_channels(target_channels).set_sample_width(target_width)
        combined += before

        timeline = []
        item_data = timeline_items or []
        for index, audio_file in enumerate(audio_files):
            segment = AudioSegment.from_file(str(audio_file))
            segment = (
                segment.set_frame_rate(target_rate)
                .set_channels(target_channels)
                .set_sample_width(target_width)
            )

            start_sample = sample_count(combined)
            combined += segment
            end_sample = sample_count(combined)

            metadata = dict(item_data[index]) if index < len(item_data) else {}
            metadata.update({
                "audio_path": str(audio_file),
                "start_sample": start_sample,
                "end_sample": end_sample,
                "duration_samples": end_sample - start_sample,
                "start": start_sample / target_rate,
                "end": end_sample / target_rate,
                "duration": (end_sample - start_sample) / target_rate,
            })
            timeline.append(metadata)

        after = AudioSegment.silent(
            duration=max(0, int(round(padding_after * 1000))),
            frame_rate=target_rate,
        ).set_channels(target_channels).set_sample_width(target_width)
        combined += after

        output_format = output_path.suffix.lower().lstrip(".") or "wav"
        export_parameters = ["-acodec", "pcm_s16le"] if output_format == "wav" else []
        combined.export(
            str(output_path),
            format=output_format,
            parameters=export_parameters,
        )

        self.last_timeline = {
            "version": 1,
            "sample_rate": target_rate,
            "channels": target_channels,
            "sample_width": target_width,
            "padding_before": padding_before,
            "padding_after": padding_after,
            "duration_samples": sample_count(combined),
            "duration": sample_count(combined) / target_rate,
            "items": timeline,
        }

        if timeline_path:
            timeline_path = Path(timeline_path)
            timeline_path.parent.mkdir(parents=True, exist_ok=True)
            timeline_path.write_text(
                json.dumps(self.last_timeline, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        return str(output_path)
    
    def get_duration(self, audio_path):
        """حساب مدة الملف الصوتي"""
        try:
            result = subprocess.run([
                'ffprobe', '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                str(audio_path)
            ], capture_output=True, text=True, timeout=30)
            
            return float(result.stdout.strip())
        except Exception as e:
            print(f"خطأ في حساب المدة: {e}")
            return 0
    
    def normalize_loudness(self, input_path, output_path, target_lufs=-14):
        """تطبيع مستوى الصوت"""
        cmd = [
            'ffmpeg', '-y',
            '-i', str(input_path),
            '-af', f'loudnorm=I={target_lufs}:LRA=11:TP=-1.5',
            '-c:a', 'libmp3lame', '-b:a', '192k',
            str(output_path)
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        return str(output_path)
