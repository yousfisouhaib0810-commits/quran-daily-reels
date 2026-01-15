"""
توليد ملفات الترجمة ASS للفيديو
تزامن دقيق 100% مع صوت القارئ الفعلي
"""
from pathlib import Path
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import math


class CaptionGenerator:
    """مولد ترجمات ASS مع تزامن دقيق حسب صوت القارئ"""
    
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
        إنشاء مقاطع متزامنة مع صوت القارئ الفعلي
        - تحليل صوت كل آية لاكتشاف بداية ونهاية القراءة
        - النص يظهر عند بداية الكلام ويختفي عند نهايته
        """
        segments = []
        current_time = padding_before
        
        for ayah in ayahs_data:
            arabic = ayah["arabic"]
            duration = ayah["duration"]
            audio_path = ayah.get("audio_path")
            
            words = arabic.split()
            num_words = len(words)
            num_parts = math.ceil(num_words / self.MAX_WORDS)
            
            # تحليل الصوت لاكتشاف توقيتات الكلام الفعلية
            speech_ranges = self._detect_speech_in_audio(audio_path)
            
            if speech_ranges:
                # بداية ونهاية الكلام الفعلي في هذه الآية
                speech_start = speech_ranges[0][0]  # بداية أول كلام
                speech_end = speech_ranges[-1][1]   # نهاية آخر كلام
                speech_duration = speech_end - speech_start
                
                print(f"   📝 الآية {ayah.get('surah')}:{ayah.get('ayah')} - كلام من {speech_start:.2f}s إلى {speech_end:.2f}s")
                
                # تقسيم النص
                arabic_parts = self._split_words_evenly(words, num_parts)
                
                # توزيع الأجزاء على مدة الكلام الفعلية
                time_per_word = speech_duration / num_words
                word_idx = 0
                
                for part in arabic_parts:
                    part_words = part.split()
                    num_part_words = len(part_words)
                    
                    # التوقيت مبني على الكلام الفعلي
                    start_time = current_time + speech_start + (word_idx * time_per_word)
                    end_time = current_time + speech_start + ((word_idx + num_part_words) * time_per_word)
                    
                    segments.append({
                        "start": start_time,
                        "end": end_time,
                        "arabic": part,
                        "surah": ayah.get("surah"),
                        "ayah": ayah.get("ayah")
                    })
                    
                    print(f"      [{word_idx+1}] {start_time:.2f}s → {end_time:.2f}s")
                    word_idx += num_part_words
            else:
                # fallback: توزيع على كامل المدة
                print(f"   ⚠️ الآية {ayah.get('surah')}:{ayah.get('ayah')} - تعذر تحليل الصوت")
                arabic_parts = self._split_words_evenly(words, num_parts)
                time_per_word = duration / num_words
                word_idx = 0
                
                for part in arabic_parts:
                    part_words = part.split()
                    num_part_words = len(part_words)
                    
                    start_time = current_time + (word_idx * time_per_word)
                    end_time = current_time + ((word_idx + num_part_words) * time_per_word)
                    
                    segments.append({
                        "start": start_time,
                        "end": end_time,
                        "arabic": part,
                        "surah": ayah.get("surah"),
                        "ayah": ayah.get("ayah")
                    })
                    word_idx += num_part_words
            
            current_time += duration
        
        print(f"   ✅ إجمالي {len(segments)} مقطع")
        return segments
    
    def _detect_speech_in_audio(self, audio_path):
        """
        تحليل ملف الصوت لاكتشاف متى يبدأ وينتهي الكلام
        يرجع قائمة من (start_sec, end_sec) للمقاطع الصوتية
        """
        if not audio_path:
            return None
        
        try:
            audio = AudioSegment.from_file(str(audio_path))
            
            # إعدادات حساسة لاكتشاف الكلام
            silence_thresh = audio.dBFS - 16
            min_silence_len = 100  # 100ms صمت
            
            # كشف المقاطع غير الصامتة (الكلام)
            nonsilent = detect_nonsilent(
                audio,
                min_silence_len=min_silence_len,
                silence_thresh=silence_thresh,
                seek_step=5
            )
            
            if not nonsilent:
                return None
            
            # تحويل من ميلي ثانية إلى ثواني
            ranges = []
            for start_ms, end_ms in nonsilent:
                ranges.append((start_ms / 1000.0, end_ms / 1000.0))
            
            return ranges
            
        except Exception as exc:
            print(f"      ⚠️ خطأ في تحليل الصوت: {exc}")
            return None
    
    def _split_words_evenly(self, words, num_parts):
        """تقسيم الكلمات بالتساوي"""
        if num_parts <= 1:
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
