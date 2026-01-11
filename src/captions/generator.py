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
        تحويل بيانات الآيات لمقاطع متزامنة مع تحليل الصوت
        """
        segments = []
        current_time = padding_before
        
        for ayah in ayahs_data:
            arabic = ayah["arabic"]
            english = ayah["english"]
            duration = ayah["duration"]
            audio_path = ayah.get("audio_path")
            
            # تقسيم الآية (2-3 كلمات لكل جزء)
            arabic_parts = self._split_text_smart(arabic, max_words=3)
            num_parts = max(1, len(arabic_parts))
            english_parts = self._redistribute_parts(english, num_parts)
            
            # حساب مدد دقيقة لكل جزء بالاعتماد على الصوت
            part_durations = self._estimate_audio_part_durations(
                audio_path,
                num_parts,
                duration
            )
            
            for i in range(num_parts):
                ar_part = arabic_parts[i]
                en_part = english_parts[i] if i < len(english_parts) else ""
                part_duration = part_durations[i] if i < len(part_durations) else duration / num_parts
                
                segment = {
                    "start": current_time,
                    "end": current_time + part_duration,
                    "arabic": ar_part,
                    "english": en_part.upper(),
                    "surah": ayah.get("surah"),
                    "ayah": ayah.get("ayah")
                }
                segments.append(segment)
                current_time += part_duration
        
        return segments

    def _split_text_smart(self, text, max_words=3):
        words = text.split()
        if len(words) <= max_words:
            return [text]
        parts = []
        for i in range(0, len(words), max_words):
            parts.append(" ".join(words[i:i + max_words]))
        return parts

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

    def _estimate_audio_part_durations(self, audio_path, num_parts, fallback_duration):
        """تحليل ملف الصوت لإيجاد مدد دقيقة لكل جزء"""
        if not audio_path or num_parts <= 0:
            return [fallback_duration / max(1, num_parts)] * max(1, num_parts)
        try:
            audio = AudioSegment.from_file(str(audio_path))
            silence_thresh = audio.dBFS - 26
            nonsilent = detect_nonsilent(
                audio,
                min_silence_len=120,
                silence_thresh=silence_thresh
            )
            durations = [max(60, end - start) / 1000 for start, end in nonsilent]
            if not durations:
                return [fallback_duration / num_parts] * num_parts
            durations = self._match_segments_to_parts(durations, num_parts)
            total = sum(durations)
            scale = fallback_duration / total if total > 0 else 1
            return [max(0.25, d * scale) for d in durations]
        except Exception as exc:
            print(f"⚠️ تعذر تحليل الصوت {audio_path}: {exc}")
            return [fallback_duration / num_parts] * num_parts

    def _match_segments_to_parts(self, durations, num_parts):
        """تطويع قائمة المدد لتطابق عدد الأجزاء مع الحفاظ على الترتيب"""
        segs = durations[:]
        if not segs:
            return [1 / num_parts] * num_parts
        # دمج أو تقسيم حتى نصل للعدد المطلوب
        while len(segs) > num_parts:
            new_segs = []
            i = 0
            while i < len(segs):
                if len(new_segs) + (len(segs) - i) == num_parts:
                    new_segs.extend(segs[i:])
                    break
                if i < len(segs) - 1:
                    new_segs.append(segs[i] + segs[i + 1])
                    i += 2
                else:
                    new_segs.append(segs[i])
                    i += 1
            segs = new_segs
        while len(segs) < num_parts:
            idx = segs.index(max(segs))
            half = segs[idx] / 2
            segs[idx] = half
            segs.insert(idx, half)
        return segs
