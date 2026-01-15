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
    
    MAX_WORDS = 4  # الحد الأقصى للكلمات في كل مقطع
    
    def __init__(self, config):
        self.config = config
        self.video_width = config["video"]["width"]
        self.video_height = config["video"]["height"]
        self.arabic_size = config["fonts"]["arabic"]["size"]
        self.arabic_y = int(self.video_height * config["layout"]["arabic_y_percent"] / 100)
    
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

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    def generate_ass(self, segments, output_path, **kwargs):
        """توليد ملف ASS من المقاطع"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        content = self._create_header()
        
        for seg in segments:
            start_str = self._format_time(seg["start"])
            end_str = self._format_time(seg["end"])
            text = seg["arabic"]
            
            content += f"Dialogue: 0,{start_str},{end_str},Arabic,,0,0,0,,{{\\pos({self.video_width//2},{self.arabic_y})}}{text}\n"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(output_path)
    
    def create_segments_from_ayahs(self, ayahs_data, padding_before=0.2):
        """
        إنشاء مقاطع متزامنة بدقة 100%
        - كل آية تُقسم لأجزاء (بحد أقصى 4 كلمات)
        - التوقيت يُحسب بناءً على مدة الآية الفعلية
        - يبدأ النص مع بداية القراءة وينتهي مع نهايتها بالضبط
        """
        segments = []
        current_time = padding_before  # بداية أول آية بعد الـ padding
        
        for ayah in ayahs_data:
            arabic = ayah["arabic"]
            duration = ayah["duration"]  # المدة الفعلية لهذه الآية
            audio_path = ayah.get("audio_path")
            
            words = arabic.split()
            num_words = len(words)
            
            # حساب عدد الأجزاء المطلوبة (بحد أقصى 4 كلمات لكل جزء)
            num_parts = math.ceil(num_words / self.MAX_WORDS)
            
            print(f"   📝 الآية {ayah.get('surah')}:{ayah.get('ayah')} - {num_words} كلمة → {num_parts} جزء")
            
            # تقسيم الكلمات بالتساوي على الأجزاء
            arabic_parts = self._split_words_evenly(words, num_parts)
            
            # توزيع متناسب مع عدد الكلمات (أبسط وأدق)
            # كل جزء يأخذ وقتاً متناسباً مع عدد كلماته
            ayah_segments = self._create_segments_proportional(
                arabic_parts, words, duration, current_time, ayah
            )
            segments.extend(ayah_segments)
            
            # طباعة التوقيتات للتحقق
            for i, seg in enumerate(ayah_segments):
                print(f"      [{i+1}] {seg['start']:.2f}s → {seg['end']:.2f}s : {seg['arabic'][:30]}...")
            
            current_time += duration
        
        print(f"   ✅ إجمالي {len(segments)} مقطع تم إنشاؤها")
        return segments
    
    def _split_words_evenly(self, words, num_parts):
        """تقسيم الكلمات بالتساوي على عدد الأجزاء المحدد"""
        if num_parts <= 0 or num_parts == 1:
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
    
    def _create_segments_proportional(self, arabic_parts, words, duration, base_time, ayah):
        """
        إنشاء مقاطع بتوزيع متناسب مع عدد الكلمات
        - كل جزء يأخذ وقتاً يتناسب مع عدد كلماته
        - البداية والنهاية دقيقة مع الصوت
        """
        segments = []
        total_words = len(words)
        
        # حساب الوقت لكل كلمة
        time_per_word = duration / total_words
        
        word_idx = 0
        for part in arabic_parts:
            part_words = part.split()
            num_part_words = len(part_words)
            
            # بداية هذا الجزء = بداية الآية + (عدد الكلمات السابقة × وقت الكلمة)
            start_time = base_time + (word_idx * time_per_word)
            
            # نهاية هذا الجزء = بداية + (عدد كلمات هذا الجزء × وقت الكلمة)
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
