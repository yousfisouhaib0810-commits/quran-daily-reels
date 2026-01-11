"""
توليد ملفات الترجمة ASS للفيديو
"""
from pathlib import Path
from pydub import AudioSegment
from pydub.silence import detect_nonsilent


class CaptionGenerator:
    """مولد ترجمات ASS"""
    
    def __init__(self, config):
        self.config = config
        self.video_width = config["video"]["width"]
        self.video_height = config["video"]["height"]
        
        # إعدادات الخطوط
        self.arabic_font = config["fonts"]["arabic"]["name"]
        self.arabic_size = config["fonts"]["arabic"]["size"]
        self.english_font = config["fonts"]["english"]["name"]
        self.english_size = config["fonts"]["english"]["size"]
        
        # إعدادات التموضع
        self.arabic_y = int(self.video_height * config["layout"]["arabic_y_percent"] / 100)
        self.english_gap = config["layout"]["english_gap_px"]
        
        # إعدادات الأنيميشن
        self.fade_in = config["animation"]["fade_in_ms"]
        self.fade_out = config["animation"]["fade_out_ms"]
    
    def _format_time(self, seconds):
        """تحويل الثواني لتنسيق ASS"""
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
Style: English,Noto Sans,{self.english_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,3,5,50,50,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    def _split_long_text(self, text, max_chars=40, is_arabic=True):
        """تقسيم النص الطويل لأسطر متعددة"""
        if len(text) <= max_chars:
            return [text]
        
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 <= max_chars:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = len(word)
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return lines
    
    def generate_ass(self, segments, output_path, padding_before=0.2, padding_after=0.2):
        """
        توليد ملف ASS من مقاطع الآيات
        
        segments: قائمة من {start, end, arabic, english}
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        content = self._create_header()
        
        for segment in segments:
            # استخدام التوقيت مباشرة بدون تعديل
            start_time = segment["start"]
            end_time = segment["end"]
            
            # تأكد من أن الوقت إيجابي
            if start_time < 0:
                start_time = 0
            if end_time <= start_time:
                end_time = start_time + 1.0
            
            start_str = self._format_time(start_time)
            end_str = self._format_time(end_time)
            
            # النص في سطر واحد (بدون تقسيم)
            arabic_text = segment["arabic"]
            english_text = segment["english"]
            
            # حساب موقع Y - العربي في الوسط والإنجليزي تحته
            arabic_y = self.arabic_y
            english_y = arabic_y + self.arabic_size + 50
            
            # إضافة الأنيميشن (fade)
            fade_effect = f"{{\\fad({self.fade_in},{self.fade_out})}}"
            
            # سطر النص العربي (سطر واحد)
            content += f"Dialogue: 0,{start_str},{end_str},Arabic,,0,0,0,,{{\\pos({self.video_width//2},{arabic_y})}}{fade_effect}{arabic_text}\n"
            
            # سطر الترجمة الإنجليزية (سطر واحد تحته)
            content += f"Dialogue: 0,{start_str},{end_str},English,,0,0,0,,{{\\pos({self.video_width//2},{english_y})}}{fade_effect}{english_text}\n"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(output_path)
    
    def create_segments_from_ayahs(self, ayahs_data, padding_before=0.2):
        """
        تحويل بيانات الآيات لمقاطع متزامنة - تقسيم إجباري لأجزاء قصيرة
        """
        segments = []
        current_time = padding_before
        
        for ayah in ayahs_data:
            arabic = ayah["arabic"]
            english = ayah["english"]
            duration = ayah["duration"]
            audio_path = ayah.get("audio_path")
            
            # تقسيم النص إجبارياً لأجزاء قصيرة (2-3 كلمات)
            arabic_parts = self._split_text_smart(arabic, max_words=3)
            english_parts = self._redistribute_parts(english, len(arabic_parts))
            
            print(f"   📝 الآية {ayah.get('surah')}:{ayah.get('ayah')} مقسمة إلى {len(arabic_parts)} جزء")
            print(f"      الأجزاء: {arabic_parts[:3]}...")  # أول 3 أجزاء للعرض
            
            # استخدام تحليل الصوت للتوقيتات فقط (إن وُجد)
            speech_timings = self._detect_speech_segments(audio_path, duration)
            
            # إذا اكتُشف مقطع واحد فقط، تجاهله واستخدم التقسيم الثابت
            if speech_timings and len(speech_timings) > 1:
                print(f"      🔊 اكتُشف {len(speech_timings)} مقطع صوتي")
                # استخدم التوقيتات من تحليل الصوت
                # تطويع عدد الأجزاء ليطابق التوقيتات
                if len(speech_timings) != len(arabic_parts):
                    # أعد توزيع النص ليطابق عدد التوقيتات
                    arabic_parts = self._split_text_smart(arabic, max_words=3, target_parts=len(speech_timings))
                    english_parts = self._redistribute_parts(english, len(arabic_parts))
                    print(f"      🔄 تم إعادة التوزيع إلى {len(arabic_parts)} جزء")
                
                # إنشاء segments بتوقيتات دقيقة
                for i, (start_offset, part_duration) in enumerate(speech_timings):
                    if i >= len(arabic_parts):
                        break
                    
                    ar_part = arabic_parts[i]
                    en_part = english_parts[i] if i < len(english_parts) else ""
                    
                    segments.append({
                        "start": current_time + start_offset,
                        "end": current_time + start_offset + part_duration,
                        "arabic": ar_part,
                        "english": en_part.upper(),
                        "surah": ayah.get("surah"),
                        "ayah": ayah.get("ayah")
                    })
            else:
                print(f"      ⚠️ لم يُكتشف صوت كافٍ - استخدام تقسيم ثابت ({len(arabic_parts)} جزء)")
                # توزيع متساوٍ إذا فشل تحليل الصوت
                part_duration = duration / len(arabic_parts)
                
                for i, (ar_part, en_part) in enumerate(zip(arabic_parts, english_parts)):
                    segments.append({
                        "start": current_time + (i * part_duration),
                        "end": current_time + ((i + 1) * part_duration),
                        "arabic": ar_part,
                        "english": en_part.upper(),
                        "surah": ayah.get("surah"),
                        "ayah": ayah.get("ayah")
                    })
            
            current_time += duration
        
        print(f"   ✅ إجمالي {len(segments)} segment تم إنشاؤها")
        return segments

    def _split_text_smart(self, text, max_words=3, target_parts=None):
        """تقسيم النص لأجزاء قصيرة (2-3 كلمات فقط) - إجباري"""
        words = text.split()
        
        if not target_parts or target_parts <= 0:
            # تقسيم إجباري: كل 2-3 كلمات بالضبط
            if len(words) <= max_words:
                return [text]
            parts = []
            for i in range(0, len(words), max_words):
                part = " ".join(words[i:i + max_words])
                if part:  # تأكد أن الجزء ليس فارغاً
                    parts.append(part)
            return parts
        
        # تقسيم متوازن حسب target_parts
        if len(words) <= target_parts:
            # كل كلمة أو كلمتين
            parts = []
            for i in range(0, len(words), 2):
                part = " ".join(words[i:i+2])
                if part:
                    parts.append(part)
            return parts
        
        # توزيع متوازن مع ضمان أجزاء قصيرة
        words_per_part = max(2, min(max_words, len(words) // target_parts))
        parts = []
        for i in range(target_parts):
            start = int(i * len(words) / target_parts)
            end = int((i + 1) * len(words) / target_parts) if i < target_parts - 1 else len(words)
            part_words = words[start:end]
            if part_words:
                parts.append(" ".join(part_words))
        return parts if parts else [text]

    def _redistribute_parts(self, text, num_parts):
        words = text.split()
        if num_parts <= 0:
            return [text]
        if len(words) <= num_parts:
            parts = []
            for i in range(num_parts):
                parts.append(words[i] if i < len(words) else "")
            return parts
        words_per_part = len(words) / num_parts
        parts = []
        for i in range(num_parts):
            start = int(i * words_per_part)
            end = int((i + 1) * words_per_part)
            part = " ".join(words[start:end])
            parts.append(part)
        return parts

    def _detect_speech_segments(self, audio_path, total_duration):
        """
        كشف مقاطع الكلام في الصوت بدقة عالية جداً
        يرجع: [(start_offset, duration), ...]
        """
        if not audio_path:
            return None
        
        try:
            audio = AudioSegment.from_file(str(audio_path))
            
            # إعدادات فائقة الحساسية للتزامن السريع
            silence_thresh = audio.dBFS - 18  # حساسية عالية جداً
            min_silence_len = 50  # فترة صمت قصيرة جداً (50ms)
            
            # كشف المقاطع غير الصامتة
            nonsilent_ranges = detect_nonsilent(
                audio,
                min_silence_len=min_silence_len,
                silence_thresh=silence_thresh,
                seek_step=5  # دقة فائقة
            )
            
            if not nonsilent_ranges:
                return None
            
            # تحويل لتوقيتات نسبية
            timings = []
            for start_ms, end_ms in nonsilent_ranges:
                start_sec = start_ms / 1000.0
                duration_sec = (end_ms - start_ms) / 1000.0
                # قبول المقاطع القصيرة جداً للتزامن السريع
                if duration_sec >= 0.08:  # على الأقل 80ms
                    timings.append((start_sec, duration_sec))
            
            # دمج المقاطع المتقاربة جداً
            timings = self._merge_close_segments(timings, gap_threshold=0.15)
            
            return timings if timings else None
            
        except Exception as exc:
            print(f"⚠️ تعذر تحليل الصوت {audio_path}: {exc}")
            return None
    
    def _merge_close_segments(self, timings, gap_threshold=0.15):
        """دمج المقاطع المتقاربة جداً لتحسين التزامن"""
        if not timings or len(timings) <= 1:
            return timings
        
        merged = []
        current_start, current_duration = timings[0]
        current_end = current_start + current_duration
        
        for start, duration in timings[1:]:
            gap = start - current_end
            
            if gap <= gap_threshold:
                # دمج المقطعين
                current_duration = (start + duration) - current_start
                current_end = current_start + current_duration
            else:
                # حفظ المقطع الحالي والبدء بمقطع جديد
                merged.append((current_start, current_duration))
                current_start = start
                current_duration = duration
                current_end = start + duration
        
        # إضافة آخر مقطع
        merged.append((current_start, current_duration))
        
        return merged
