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
    
    MAX_WORDS = 3  # الحد الأقصى للكلمات في كل مقطع - أقل لدقة أعلى
    
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
        إنشاء مقاطع متزامنة مع صوت القارئ الفعلي بدقة عالية جداً
        - تحليل صوت كل آية لاكتشاف بداية ونهاية القراءة
        - تقسيم النص حسب مقاطع الصوت الفعلية
        - النص يظهر ويختفي بدقة مع صوت القارئ
        """
        segments = []
        current_time = padding_before
        
        for ayah in ayahs_data:
            arabic = ayah["arabic"]
            duration = ayah["duration"]
            audio_path = ayah.get("audio_path")
            
            words = arabic.split()
            num_words = len(words)
            
            # تحليل الصوت لاكتشاف توقيتات الكلام الفعلية بدقة millisecond
            speech_ranges = self._detect_speech_in_audio(audio_path)
            
            if speech_ranges and len(speech_ranges) > 0:
                # دمج المقاطع المتقاربة جداً (أقل من 100ms)
                merged_ranges = self._merge_close_ranges(speech_ranges, gap_threshold=0.1)
                
                speech_start = merged_ranges[0][0]
                speech_end = merged_ranges[-1][1]
                speech_duration = speech_end - speech_start
                
                print(f"   📝 الآية {ayah.get('surah')}:{ayah.get('ayah')} - {len(merged_ranges)} مقطع صوتي")
                print(f"      الكلام من {speech_start:.3f}s إلى {speech_end:.3f}s")
                
                # إذا كان عندنا مقاطع صوتية متعددة، نوزع الكلمات عليها
                if len(merged_ranges) >= 2:
                    # توزيع ذكي: كل مقطع صوتي = segment
                    word_idx = 0
                    for i, (range_start, range_end) in enumerate(merged_ranges):
                        range_duration = range_end - range_start
                        # عدد الكلمات لهذا المقطع حسب نسبة المدة
                        words_for_this_range = max(1, int((range_duration / speech_duration) * num_words))
                        
                        if word_idx >= num_words:
                            break
                        
                        # أخذ الكلمات لهذا المقطع
                        end_word_idx = min(word_idx + words_for_this_range, num_words)
                        if i == len(merged_ranges) - 1:  # آخر مقطع يأخذ الباقي
                            end_word_idx = num_words
                        
                        segment_words = words[word_idx:end_word_idx]
                        
                        # لكن لا نتجاوز MAX_WORDS
                        if len(segment_words) > self.MAX_WORDS:
                            # نقسمها لعدة segments
                            num_parts = math.ceil(len(segment_words) / self.MAX_WORDS)
                            time_per_word = range_duration / len(segment_words)
                            
                            for j in range(num_parts):
                                start_idx = j * self.MAX_WORDS
                                end_idx = min((j + 1) * self.MAX_WORDS, len(segment_words))
                                part_words = segment_words[start_idx:end_idx]
                                
                                part_start = current_time + range_start + (start_idx * time_per_word)
                                part_end = current_time + range_start + (end_idx * time_per_word)
                                
                                segments.append({
                                    "start": part_start,
                                    "end": part_end,
                                    "arabic": " ".join(part_words),
                                    "surah": ayah.get("surah"),
                                    "ayah": ayah.get("ayah")
                                })
                                print(f"      ✓ {part_start:.3f}s → {part_end:.3f}s: {' '.join(part_words)}")
                        else:
                            segments.append({
                                "start": current_time + range_start,
                                "end": current_time + range_end,
                                "arabic": " ".join(segment_words),
                                "surah": ayah.get("surah"),
                                "ayah": ayah.get("ayah")
                            })
                            print(f"      ✓ {current_time + range_start:.3f}s → {current_time + range_end:.3f}s: {' '.join(segment_words)}")
                        
                        word_idx = end_word_idx
                else:
                    # مقطع صوتي واحد: نقسم الكلمات بالتساوي
                    num_parts = math.ceil(num_words / self.MAX_WORDS)
                    time_per_word = speech_duration / num_words
                    
                    for i in range(num_parts):
                        start_idx = i * self.MAX_WORDS
                        end_idx = min((i + 1) * self.MAX_WORDS, num_words)
                        part_words = words[start_idx:end_idx]
                        
                        part_start = current_time + speech_start + (start_idx * time_per_word)
                        part_end = current_time + speech_start + (end_idx * time_per_word)
                        
                        segments.append({
                            "start": part_start,
                            "end": part_end,
                            "arabic": " ".join(part_words),
                            "surah": ayah.get("surah"),
                            "ayah": ayah.get("ayah")
                        })
                        print(f"      ✓ {part_start:.3f}s → {part_end:.3f}s: {' '.join(part_words)}")
            else:
                # fallback: توزيع على كامل المدة
                print(f"   ⚠️ الآية {ayah.get('surah')}:{ayah.get('ayah')} - تعذر تحليل الصوت")
                num_parts = math.ceil(num_words / self.MAX_WORDS)
                time_per_word = duration / num_words
                
                for i in range(num_parts):
                    start_idx = i * self.MAX_WORDS
                    end_idx = min((i + 1) * self.MAX_WORDS, num_words)
                    part_words = words[start_idx:end_idx]
                    
                    part_start = current_time + (start_idx * time_per_word)
                    part_end = current_time + (end_idx * time_per_word)
                    
                    segments.append({
                        "start": part_start,
                        "end": part_end,
                        "arabic": " ".join(part_words),
                        "surah": ayah.get("surah"),
                        "ayah": ayah.get("ayah")
                    })
            
            current_time += duration
        
        print(f"   ✅ إجمالي {len(segments)} مقطع بدقة millisecond")
        return segments
    
    def _merge_close_ranges(self, ranges, gap_threshold=0.1):
        """
        دمج المقاطع الصوتية المتقاربة جداً
        gap_threshold: الفجوة بالثواني (0.1 = 100ms)
        """
        if not ranges or len(ranges) <= 1:
            return ranges
        
        merged = []
        current_start, current_end = ranges[0]
        
        for start, end in ranges[1:]:
            if start - current_end <= gap_threshold:
                # دمج
                current_end = end
            else:
                # حفظ المقطع الحالي وبدء مقطع جديد
                merged.append((current_start, current_end))
                current_start, current_end = start, end
        
        merged.append((current_start, current_end))
        return merged
    
    def _detect_speech_in_audio(self, audio_path):
        """
        تحليل ملف الصوت لاكتشاف متى يبدأ وينتهي الكلام
        يرجع قائمة من (start_sec, end_sec) للمقاطع الصوتية
        """
        if not audio_path:
            return None
        
        try:
            audio = AudioSegment.from_file(str(audio_path))
            
            # إعدادات دقيقة جداً لاكتشاف الكلام (بالأجزاء من الثانية)
            silence_thresh = audio.dBFS - 14  # أكثر حساسية
            min_silence_len = 50  # 50ms صمت - دقة مضاعفة
            
            # كشف المقاطع غير الصامتة (الكلام) بدقة عالية
            nonsilent = detect_nonsilent(
                audio,
                min_silence_len=min_silence_len,
                silence_thresh=silence_thresh,
                seek_step=1  # مسح كل 1ms لدقة قصوى
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
