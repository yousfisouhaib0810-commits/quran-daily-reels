"""
رفع الفيديوهات إلى YouTube
"""
import os
import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class YouTubeUploader:
    """رافع فيديوهات YouTube"""
    
    def __init__(self):
        self.credentials = None
        self.youtube = None
    
    def authenticate(self):
        """المصادقة مع YouTube API"""
        # قراءة client secrets من متغير البيئة أو ملف
        client_secrets_json = os.environ.get("YOUTUBE_CLIENT_SECRETS")
        
        if client_secrets_json:
            # من متغير البيئة (GitHub Actions)
            client_info = json.loads(client_secrets_json)
            self.credentials = Credentials.from_authorized_user_info(client_info)
        else:
            # من ملف محلي
            creds_file = Path("config/youtube_credentials.json")
            if creds_file.exists():
                with open(creds_file, 'r') as f:
                    client_info = json.load(f)
                self.credentials = Credentials.from_authorized_user_info(client_info)
            else:
                raise FileNotFoundError(
                    "لم يتم العثور على بيانات اعتماد YouTube. "
                    "يرجى إعداد YOUTUBE_CLIENT_SECRETS أو config/youtube_credentials.json"
                )
        
        self.youtube = build('youtube', 'v3', credentials=self.credentials)
    
    def upload_video(self, video_path, title, description="", tags=None, category_id="22", privacy_status="public"):
        """
        رفع فيديو إلى YouTube
        
        Args:
            video_path: مسار الفيديو
            title: عنوان الفيديو
            description: وصف الفيديو
            tags: قائمة الوسوم
            category_id: رقم الفئة (22 = People & Blogs)
            privacy_status: الخصوصية (public, unlisted, private)
        
        Returns:
            dict: معلومات الفيديو المرفوع
        """
        if not self.youtube:
            self.authenticate()
        
        if tags is None:
            tags = ["قرآن", "تلاوة", "Quran", "Recitation"]
        
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': category_id
            },
            'status': {
                'privacyStatus': privacy_status,
                'selfDeclaredMadeForKids': False
            }
        }
        
        # إنشاء media upload
        media = MediaFileUpload(
            video_path,
            mimetype='video/mp4',
            resumable=True,
            chunksize=1024 * 1024  # 1MB chunks
        )
        
        # رفع الفيديو
        request = self.youtube.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media
        )
        
        response = None
        print("   📤 جاري رفع الفيديو إلى YouTube...")
        
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"      {progress}% مكتمل")
        
        video_id = response['id']
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        print(f"   ✅ تم الرفع: {video_url}")
        
        return {
            'id': video_id,
            'url': video_url,
            'title': response['snippet']['title']
        }
