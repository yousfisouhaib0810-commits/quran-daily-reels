"""
معالجة الصوت - دمج ملفات الآيات وإضافة padding
"""
import subprocess
from pathlib import Path
import tempfile


class AudioProcessor:
    """معالج الصوت"""
    
    def __init__(self, output_dir="temp"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def concatenate_audio(self, audio_files, output_path, padding_before=0.2, padding_after=0.2):
        """
        دمج ملفات صوت متعددة مع padding
        
        audio_files: قائمة مسارات ملفات MP3
        """
        if not audio_files:
            raise ValueError("لا توجد ملفات صوت للدمج!")
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # إذا كان ملف واحد فقط
        if len(audio_files) == 1:
            # إضافة padding فقط
            pad_cmd = [
                'ffmpeg', '-y',
                '-i', str(audio_files[0]),
                '-af', f'adelay={int(padding_before*1000)}|{int(padding_before*1000)},apad=pad_dur={padding_after}',
                '-c:a', 'libmp3lame', '-b:a', '192k',
                str(output_path)
            ]
            subprocess.run(pad_cmd, capture_output=True, check=True)
            return str(output_path)
        
        # إنشاء ملف concat list
        concat_list = self.output_dir / "concat_list.txt"
        
        with open(concat_list, 'w', encoding='utf-8') as f:
            for audio_file in audio_files:
                # تحويل المسار لصيغة FFmpeg
                safe_path = str(Path(audio_file).absolute()).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")
        
        # ملف مؤقت للصوت المدمج
        temp_concat = self.output_dir / "temp_concat.mp3"
        
        # دمج الملفات
        concat_cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', str(concat_list),
            '-c:a', 'libmp3lame', '-b:a', '192k',
            str(temp_concat)
        ]
        
        subprocess.run(concat_cmd, capture_output=True, check=True)
        
        # إضافة padding (صمت قبل وبعد)
        pad_cmd = [
            'ffmpeg', '-y',
            '-i', str(temp_concat),
            '-af', f'adelay={int(padding_before*1000)}|{int(padding_before*1000)},apad=pad_dur={padding_after}',
            '-c:a', 'libmp3lame', '-b:a', '192k',
            str(output_path)
        ]
        
        subprocess.run(pad_cmd, capture_output=True, check=True)
        
        # تنظيف الملفات المؤقتة
        if concat_list.exists():
            concat_list.unlink()
        if temp_concat.exists():
            temp_concat.unlink()
        
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
