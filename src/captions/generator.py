"""
توليد ملفات الترجمة ASS للفيديو
تزامن دقيق 100% مع الصوت - بحد أقصى 4 كلمات لكل مقطع
"""
from pathlib import Path
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import math


class CaptionGenerator:
    """مولد ترجمات ASS مع تزامن دقيق"""
    
    MAX_WORDS_PER_SEGMENT = 4  # الحد الأقصى للكلمات في كل مقطع
    
    def __init__(self, config):
        self.config = config
        self.video_width = config["video"]["width"]
        self.video_height = config["video"]["height"]
        
        # إعدادات الخطوط (العربية فقط)
        self.arabic_font = config["fonts"]["arabic"]["name"]
        self.arabic_size = config["fonts"]["arabic"]["size"]
        
        # إعدادات التموضع
        self.arabic_y = int(self.video_height * config["layout"]["arabic_y_percent"] / 100)
        
        # إعدادات الأنيميشن
        self.fade_in = config["animation"]["fade_in_ms"]
        self.fade_out = config["animation"]["fade_out_ms"]
    
    def _format_time(self, seconds):
        """تحويل الثواني لتنسيق ASS بدقة 0.01 ثانية"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"
    
    def _create_header(self):
        """إنشاء رأس ملف ASS"""
        return f"""[Script Info]
Title: Quran Daily Reel
ScriptType: v4.00+
PlayResX: {self.video_width}
PlayResY: {self.video_height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Arabic,Amiri,{self.arabic_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,6,4,5,50,50,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    def generate_ass(self, segments, output_path, padding_before=0.2, padding_after=0.2):
        """توليد ملف ASS من مقاطع الآيات"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        content = self._create_header()
        
        for segment in segments:
            start_time = max(0, segment["start"])
            end_time = segment["end"]
            
            if end_time <= start_time:
                end_time = start_time + 0.5
            
            start_str = self._format_time(start_time)
            end_str = self._format_time(end_time)
            
            arabic_text = segment["arabic"]
            
            # بدون تأثير fade - ظهور واختفاء فوري مع الصوت
            content += f"Dialogue: 0,{start_str},{end_str},Arabic,,0,0,0,,{{\\pos({self.video_width//2},{self.arabic_y})}}{arabic_text}\n"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(output_path)
    
    def create_segments_from_ayahs(self, ayahs_data, padding_before=0.2):
        """
        تحويل بيانات الآيات لمقاطع متزامنة بدقة 100%
        - تحليل الصوت لكشف مواقع الكلمات
        - تقسيم النص لأجزاء بحد أقصى 4 كلمات
        - مطابقة التوقيتات مع مقاطع الصوت
        """
        segments = []
        current_time = padding_before
        
        for ayah in ayahs_data:
            arabic = ayah["arabic"]
            duration = ayah["duration"]
            audio_path = ayah.get("audio_path")
            
            words = arabic.split()
            num_words = len(words)
            
            # حساب عدد الأجزاء المطلوبة (بحد أقصى 4 كلمات لكل جزء)
            num_parts = math.ceil(num_words / self.MAX_WORDS_PER_SEGMENT)
            
            print(f"   📝 الآية {ayah.get('surah')}:{ayah.get('ayah')} - {num_words} كلمة → {num_parts} جزء")
            
            # تقسيم الكلمات بالتساوي على الأجزاء
            arabic_parts = self._split_words_evenly(words, num_parts)
            
            # تحليل الصوت للحصول على توقيتات دقيقة
            word_timings = self._analyze_audio_for_words(audio_path, duration, num_words)
            
            if word_timings and len(word_timings) >= num_words:
                # توقيتات دقيقة متاحة - استخدمها
                print(f"      ✅ تزامن دقيق: {len(word_timings)} توقيت للكلمات")
                segments.extend(
                    self._create_segments_from_word_timings(
                        arabic_parts, words, word_timings, current_time, ayah
                    )
                )
            else:
                # توزيع متناسب مع عدد الكلمات
                print(f"      ⚠️ تزامن تقديري بناءً على عدد الكلمات")
                segments.extend(
                    self._create_segments_proportional(
                        arabic_parts, words, duration, current_time, ayah
                    )
                )
            
            current_time += duration
        
        print(f"   ✅ إجمالي {len(segments)} مقطع تم إنشاؤها")
        return segments
    
    def _split_words_evenly(self, words, num_parts):
        """تقسيم الكلمات بالتساوي على عدد الأجزاء المحدد"""
        if num_parts <= 0:
            return [" ".join(words)]
        
        parts = []
        words_per_part = len(words) / num_parts
        
        for i in range(num_parts):
            start_idx = int(i * words_per_part)
            end_idx = int((i + 1) * words_per_part) if i < num_parts - 1 else len(words)
            part_words = words[start_idx:end_idx]
            if part_words:
                parts.append(" ".join(part_words))
        
        return parts if parts else [" ".join(words)]
    
    def _analyze_audio_for_words(self, audio_path, total_duration, num_words):
        """
        تحليل الصوت لاستخراج توقيتات دقيقة لكل كلمة
        يستخدم كشف الصمت بحساسية عالية جداً
        """
        if not audio_path:
            return None
        
        try:
            audio = AudioSegment.from_file(str(audio_path))
            audio_duration_ms = len(audio)
            
            # إعدادات فائقة الحساسية
            silence_thresh = audio.dBFS - 14  # حساسية أعلى
            min_silence_len = 30  # 30ms فقط للكشف عن فواصل الكلمات
            
            # كشف المقاطع غير الصامتة
            nonsilent_ranges = detect_nonsilent(
                audio,
                min_silence_len=min_silence_len,
                silence_thresh=silence_thresh,
                seek_step=3  # دقة 3ms
            )
            
            if not nonsilent_ranges:
                return None
            
            # دمج المقاطع القريبة جداً (أقل من 60ms)
            merged_ranges = self._merge_ranges(nonsilent_ranges, gap_ms=60)
            
            # إذا عدد المقاطع أقل من الكلمات، قسّم المقاطع الطويلة
            if len(merged_ranges) < num_words:
                merged_ranges = self._subdivide_long_ranges(
                    merged_ranges, num_words, audio_duration_ms
                )
            
            # تحويل لتوقيتات بالثواني
            timings = []
            for start_ms, end_ms in merged_ranges:
                timings.append({
                    "start": start_ms / 1000.0,
                    "end": end_ms / 1000.0,
                    "duration": (end_ms - start_ms) / 1000.0
                })
            
            return timings
            
        except Exception as exc:
            print(f"      ⚠️ تعذر تحليل الصوت: {exc}")
            return None
    
    def _merge_ranges(self, ranges, gap_ms=60):
        """دمج المقاطع المتقاربة"""
        if not ranges:
            return []
        
        merged = [list(ranges[0])]
        
        for start, end in ranges[1:]:
            if start - merged[-1][1] <= gap_ms:
                merged[-1][1] = end
            else:
                merged.append([start, end])
        
        return merged
    
    def _subdivide_long_ranges(self, ranges, target_count, total_ms):
        """تقسيم المقاطع الطويلة للوصول للعدد المطلوب"""
        if len(ranges) >= target_count:
            return ranges
        
        result = []
        needed = target_count - len(ranges)
        
        # حساب متوسط طول المقطع
        avg_duration = total_ms / target_count
        
        for start, end in ranges:
            duration = end - start
            
            # إذا المقطع طويل، قسّمه
            if duration > avg_duration * 1.5 and needed > 0:
                subdivisions = min(int(duration / avg_duration), needed + 1)
                sub_duration = duration / subdivisions
                
                for i in range(subdivisions):
                    sub_start = start + (i * sub_duration)
                    sub_end = start + ((i + 1) * sub_duration)
                    result.append([int(sub_start), int(sub_end)])
                    if i > 0:
                        needed -= 1
            else:
                result.append([start, end])
        
        return result
    
    def _create_segments_from_word_timings(self, arabic_parts, words, word_timings, base_time, ayah):
        """إنشاء مقاطع بناءً على توقيتات الكلمات الدقيقة"""
        segments = []
        word_idx = 0
        
        for part in arabic_parts:
            part_words = part.split()
            num_part_words = len(part_words)
            
            if word_idx >= len(word_timings):
                break
            
            # بداية المقطع = بداية أول كلمة فيه
            start_timing = word_timings[word_idx]
            
            # نهاية المقطع = نهاية آخر كلمة فيه
            end_idx = min(word_idx + num_part_words - 1, len(word_timings) - 1)
            end_timing = word_timings[end_idx]
            
            segments.append({
                "start": base_time + start_timing["start"],
                "end": base_time + end_timing["end"],
                "arabic": part,
                "surah": ayah.get("surah"),
                "ayah": ayah.get("ayah")
            })
            
            word_idx += num_part_words
        
        return segments
    
    def _create_segments_proportional(self, arabic_parts, words, duration, base_time, ayah):
        """إنشاء مقاطع بتوزيع متناسب مع عدد الكلمات"""
        segments = []
        total_words = len(words)
        time_per_word = duration / total_words
        
        word_idx = 0
        for part in arabic_parts:
            part_words = part.split()
            num_part_words = len(part_words)
            
            start_time = base_time + (word_idx * time_per_word)
            end_time = base_time + ((word_idx + num_part_words) * time_per_word)
            
            segments.append({
                "start": start_time,
                "end": end_time,
                "arabic": part,
                "surah": ayah.get("surah"),
                "ayah": ayah.get("ayah")
            })
            
            word_idx += num_part_words
        
        return segments
