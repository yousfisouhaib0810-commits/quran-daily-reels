"""
رندر الفيديو النهائي باستخدام FFmpeg
"""
import subprocess
from pathlib import Path
from datetime import datetime


class VideoRenderer:
    """مولد الفيديو النهائي"""
    
    def __init__(self, config, output_dir="output"):
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # إعدادات الفيديو
        self.width = config["video"]["width"]
        self.height = config["video"]["height"]
        self.fps = config["video"]["fps"]
        self.bitrate = config["video"]["bitrate"]
        self.codec = config["video"]["codec"]
        self.preset = config["video"]["preset"]
        self.audio_bitrate = config["video"]["audio_bitrate"]
    
    def render(self, background_path, audio_path, ass_path, output_filename=None):
        """
        رندر الفيديو النهائي
        
        background_path: فيديو الخلفية المُعد
        audio_path: الصوت المدمج مع padding
        ass_path: ملف الترجمة ASS
        """
        if output_filename is None:
            date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            output_filename = f"quran_reel_{date_str}.mp4"
        
        output_path = self.output_dir / output_filename
        
        # FFmpeg command لدمج كل شيء
        # نستخدم subtitles filter لحرق الترجمة في الفيديو
        cmd = [
            'ffmpeg', '-y',
            '-i', str(background_path),  # فيديو الخلفية
            '-i', str(audio_path),       # الصوت
            '-vf', f"subtitles='{str(ass_path).replace(chr(92), '/')}'",  # الترجمة
            '-c:v', self.codec,
            '-preset', self.preset,
            '-b:v', self.bitrate,
            '-c:a', 'aac',
            '-b:a', self.audio_bitrate,
            '-shortest',  # أقصر مدة من الاثنين
            '-r', str(self.fps),
            str(output_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"✅ تم إنشاء الفيديو: {output_path}")
            return str(output_path)
        except subprocess.CalledProcessError as e:
            print(f"❌ خطأ في الرندر: {e.stderr}")
            
            # محاولة بديلة بدون ASS معقد
            return self._render_fallback(background_path, audio_path, output_path)
    
    def _render_fallback(self, background_path, audio_path, output_path):
        """رندر بديل في حالة فشل ASS"""
        cmd = [
            'ffmpeg', '-y',
            '-i', str(background_path),
            '-i', str(audio_path),
            '-c:v', self.codec,
            '-preset', self.preset,
            '-b:v', self.bitrate,
            '-c:a', 'aac',
            '-b:a', self.audio_bitrate,
            '-shortest',
            '-r', str(self.fps),
            str(output_path)
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        print(f"✅ تم إنشاء الفيديو (بدون ترجمة مدمجة): {output_path}")
        return str(output_path)
    
    def get_video_info(self, video_path):
        """الحصول على معلومات الفيديو"""
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_format', '-show_streams',
            str(video_path)
        ]
        
        import json
        result = subprocess.run(cmd, capture_output=True, text=True)
        return json.loads(result.stdout)
