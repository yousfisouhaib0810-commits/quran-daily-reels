"""
إدارة فيديوهات الخلفية
"""
import subprocess
import random
from pathlib import Path


class BackgroundManager:
    """مدير الخلفيات"""
    
    def __init__(self, pexels_api, cache_dir="data/backgrounds", used_file="state/used_backgrounds.json"):
        self.pexels = pexels_api
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.used_file = Path(used_file)
        self.used_backgrounds = self._load_used()
    
    def _load_used(self):
        """تحميل قائمة الخلفيات المستخدمة"""
        import json
        if self.used_file.exists():
            with open(self.used_file, 'r') as f:
                return json.load(f)
        return []
    
    def _save_used(self):
        """حفظ قائمة الخلفيات المستخدمة"""
        import json
        self.used_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.used_file, 'w') as f:
            json.dump(self.used_backgrounds, f)
    
    def get_random_background(self, duration_needed, search_queries=None):
        """
        الحصول على فيديو خلفية عشوائي
        """
        if search_queries is None:
            search_queries = ["mosque", "sky clouds", "nature calm", "sunset"]
        
        # البحث عن فيديوهات
        all_videos = []
        for query in search_queries:
            videos = self.pexels.search_videos(
                query=query,
                orientation="portrait",
                min_duration=max(10, int(duration_needed))
            )
            all_videos.extend(videos)
        
        if not all_videos:
            print("لم يتم العثور على فيديوهات خلفية!")
            return None
        
        # استبعاد المستخدمة مؤخراً
        available = [v for v in all_videos if v["id"] not in self.used_backgrounds[-20:]]
        
        if not available:
            # إذا استخدمنا كل الفيديوهات، أعد التعيين
            available = all_videos
            self.used_backgrounds = []
        
        # اختيار عشوائي
        selected = random.choice(available)
        
        # تحميل الفيديو
        local_path = self.pexels.download_video(selected["url"], selected["id"])
        
        if local_path:
            # تسجيل كمستخدم
            self.used_backgrounds.append(selected["id"])
            self._save_used()
        
        return {
            "id": selected["id"],
            "path": local_path,
            "duration": selected["duration"]
        }
    
    def prepare_background(self, input_path, output_path, target_duration, width=1080, height=1920):
        """
        تحضير الخلفية: قص/loop + تحويل للحجم المطلوب
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # FFmpeg: loop إذا لزم + scale + crop للـ 9:16
        cmd = [
            'ffmpeg', '-y',
            '-stream_loop', '-1',  # loop لانهائي
            '-i', str(input_path),
            '-t', str(target_duration),  # المدة المطلوبة
            '-vf', f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}',
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
            '-an',  # بدون صوت
            str(output_path)
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        
        return str(output_path)
