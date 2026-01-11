"""
توليد ملفات الترجمة ASS للفيديو
"""
from pathlib import Path


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
Style: Arabic,Amiri,{self.arabic_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,3,5,50,50,10,1
Style: English,Noto Sans,{self.english_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,2,5,50,50,10,1

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
            
            # تقسيم النص إذا كان طويلاً
            arabic_lines = self._split_long_text(segment["arabic"], max_chars=25, is_arabic=True)
            english_lines = self._split_long_text(segment["english"], max_chars=40, is_arabic=False)
            
            arabic_text = "\\N".join(arabic_lines)
            english_text = "\\N".join(english_lines)
            
            # حساب موقع Y
            arabic_y = self.arabic_y
            english_y = arabic_y + self.arabic_size + self.english_gap + 20
            
            # إضافة الأنيميشن (fade)
            fade_effect = f"{{\\fad({self.fade_in},{self.fade_out})}}"
            
            # سطر النص العربي
            content += f"Dialogue: 0,{start_str},{end_str},Arabic,,0,0,0,,{{\\pos({self.video_width//2},{arabic_y})}}{fade_effect}{arabic_text}\n"
            
            # سطر الترجمة الإنجليزية
            content += f"Dialogue: 0,{start_str},{end_str},English,,0,0,0,,{{\\pos({self.video_width//2},{english_y})}}{fade_effect}{english_text}\n"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(output_path)
    
    def create_segments_from_ayahs(self, ayahs_data, padding_before=0.2):
        """
        تحويل بيانات الآيات لمقاطع متزامنة
        
        ayahs_data: قائمة من {arabic, english, duration}
        """
        segments = []
        current_time = padding_before
        
        for ayah in ayahs_data:
            segment = {
                "start": current_time,
                "end": current_time + ayah["duration"],
                "arabic": ayah["arabic"],
                "english": ayah["english"],
                "surah": ayah.get("surah"),
                "ayah": ayah.get("ayah")
            }
            segments.append(segment)
            current_time += ayah["duration"]
        
        return segments
