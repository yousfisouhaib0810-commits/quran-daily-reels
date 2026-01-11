"""
مصادر البيانات - جلب النصوص والترجمات والصوت
"""
import requests
import os
import json
import subprocess
from pathlib import Path


class QuranAPI:
    """API للحصول على النص العثماني والترجمة"""
    
    BASE_URL = "https://api.alquran.cloud/v1"
    
    def __init__(self, translation_id=131):  # 131 = Sahih International
        self.translation_id = translation_id
    
    def get_ayah_text(self, surah, ayah):
        """جلب النص العثماني للآية"""
        url = f"{self.BASE_URL}/ayah/{surah}:{ayah}/quran-uthmani"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "OK" and data.get("data"):
                return data["data"]["text"]
        except Exception as e:
            print(f"خطأ في جلب النص: {e}")
        
        return None
    
    def get_ayah_translation(self, surah, ayah):
        """جلب الترجمة الإنجليزية للآية"""
        url = f"{self.BASE_URL}/ayah/{surah}:{ayah}/en.sahih"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "OK" and data.get("data"):
                text = data["data"]["text"]
                # إزالة HTML tags
                import re
                text = re.sub(r'<[^>]+>', '', text)
                return text
        except Exception as e:
            print(f"خطأ في جلب الترجمة: {e}")
        
        return None
    
    def get_multiple_ayahs(self, surah, start_ayah, end_ayah):
        """جلب عدة آيات مع ترجماتها"""
        ayahs = []
        for ayah_num in range(start_ayah, end_ayah + 1):
            arabic = self.get_ayah_text(surah, ayah_num)
            english = self.get_ayah_translation(surah, ayah_num)
            
            if arabic and english:
                ayahs.append({
                    "surah": surah,
                    "ayah": ayah_num,
                    "arabic": arabic,
                    "english": english.upper()  # UPPERCASE للترجمة
                })
        
        return ayahs


class EveryAyahAudio:
    """تحميل الصوت من EveryAyah"""
    
    BASE_URL = "https://everyayah.com/data"
    
    def __init__(self, reciter_id, cache_dir="data/audio"):
        self.reciter_id = reciter_id
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_audio_url(self, surah, ayah):
        """بناء رابط الصوت"""
        # تنسيق: 001001.mp3 (سورة 3 أرقام + آية 3 أرقام)
        filename = f"{surah:03d}{ayah:03d}.mp3"
        return f"{self.BASE_URL}/{self.reciter_id}/{filename}"
    
    def download_ayah(self, surah, ayah):
        """تحميل صوت آية واحدة"""
        url = self.get_audio_url(surah, ayah)
        local_path = self.cache_dir / self.reciter_id / f"{surah:03d}{ayah:03d}.mp3"
        
        # إنشاء المجلد
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        # تحقق من الكاش
        if local_path.exists():
            return str(local_path)
        
        # تحميل
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            return str(local_path)
        except Exception as e:
            print(f"خطأ في تحميل الصوت {surah}:{ayah}: {e}")
            return None
    
    def get_audio_duration(self, audio_path):
        """حساب مدة الصوت بالثواني باستخدام ffprobe"""
        try:
            result = subprocess.run([
                'ffprobe', '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                audio_path
            ], capture_output=True, text=True, timeout=30)
            
            return float(result.stdout.strip())
        except Exception as e:
            print(f"خطأ في حساب المدة: {e}")
            return 0
    
    def download_multiple_ayahs(self, surah, start_ayah, end_ayah):
        """تحميل عدة آيات وحساب مددها"""
        audio_files = []
        total_duration = 0
        
        for ayah_num in range(start_ayah, end_ayah + 1):
            audio_path = self.download_ayah(surah, ayah_num)
            
            if audio_path:
                duration = self.get_audio_duration(audio_path)
                audio_files.append({
                    "surah": surah,
                    "ayah": ayah_num,
                    "path": audio_path,
                    "duration": duration
                })
                total_duration += duration
        
        return audio_files, total_duration


class PexelsAPI:
    """جلب فيديوهات الخلفية من Pexels"""
    
    BASE_URL = "https://api.pexels.com/videos"
    
    def __init__(self, api_key, cache_dir="data/backgrounds"):
        self.api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.headers = {"Authorization": api_key}
    
    def search_videos(self, query="mosque", orientation="portrait", min_duration=15):
        """البحث عن فيديوهات"""
        url = f"{self.BASE_URL}/search"
        params = {
            "query": query,
            "orientation": orientation,
            "per_page": 20,
            "size": "large"
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # فلترة حسب المدة
            videos = []
            for video in data.get("videos", []):
                if video.get("duration", 0) >= min_duration:
                    # البحث عن أفضل جودة عمودية
                    for file in video.get("video_files", []):
                        if file.get("height", 0) >= 1920:
                            videos.append({
                                "id": video["id"],
                                "url": file["link"],
                                "duration": video["duration"],
                                "width": file.get("width"),
                                "height": file.get("height")
                            })
                            break
            
            return videos
        except Exception as e:
            print(f"خطأ في البحث عن فيديوهات: {e}")
            return []
    
    def download_video(self, video_url, video_id):
        """تحميل فيديو الخلفية"""
        local_path = self.cache_dir / f"{video_id}.mp4"
        
        # تحقق من الكاش
        if local_path.exists():
            return str(local_path)
        
        try:
            response = requests.get(video_url, timeout=120, stream=True)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return str(local_path)
        except Exception as e:
            print(f"خطأ في تحميل الفيديو: {e}")
            return None
