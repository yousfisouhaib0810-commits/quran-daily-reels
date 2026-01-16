"""
رفع الفيديوهات إلى YouTube
"""
import os
import json
import pickle
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']


class YouTubeUploader:
    """رافع فيديوهات YouTube"""
    
    def __init__(self):
        self.credentials = None
        self.youtube = None
    
    def authenticate(self):
        """المصادقة مع YouTube API"""
        token_file = Path("config/youtube_token.pickle")
        
        # محاولة تحميل token محفوظ
        if token_file.exists():
            with open(token_file, 'rb') as f:
                self.credentials = pickle.load(f)
        
        # إذا لم يكن هناك credentials صالحة، حاول من متغير البيئة
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                print("   🔄 تحديث YouTube token...")
                self.credentials.refresh(Request())
            else:
                # محاولة قراءة من متغير البيئة للـ GitHub Actions
                youtube_token = os.environ.get("YOUTUBE_TOKEN")
                if youtube_token:
                    token_info = json.loads(youtube_token)
                    self.credentials = Credentials(
                        token=token_info.get('token'),
                        refresh_token=token_info.get('refresh_token'),
                        token_uri=token_info.get('token_uri', 'https://oauth2.googleapis.com/token'),
                        client_id=token_info.get('client_id'),
                        client_secret=token_info.get('client_secret'),
                        scopes=SCOPES
                    )
                else:
                    # OAuth flow للمصادقة المحلية
                    client_secrets = os.environ.get("YOUTUBE_CLIENT_SECRETS")
                    if client_secrets:
                        client_info = json.loads(client_secrets)
                    else:
                        creds_file = Path("config/youtube_client_secrets.json")
                        if not creds_file.exists():
                            raise FileNotFoundError(
                                "لم يتم العثور على بيانات YouTube. "
                                "يرجى تشغيل setup_youtube_auth.py أو تعيين YOUTUBE_TOKEN"
                            )
                        with open(creds_file, 'r') as f:
                            client_info = json.load(f)
                    
                    flow = InstalledAppFlow.from_client_config(client_info, SCOPES)
                    self.credentials = flow.run_local_server(port=0)
                
                # حفظ token للاستخدام القادم
                with open(token_file, 'wb') as f:
                    pickle.dump(self.credentials, f)
        
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
