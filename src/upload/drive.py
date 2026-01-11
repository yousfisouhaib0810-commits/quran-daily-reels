"""
رفع الفيديو إلى Google Drive
"""
import os
import pickle
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class GoogleDriveUploader:
    """رفع الملفات إلى Google Drive"""
    
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    
    def __init__(self, credentials_path="config/credentials.json", token_path="config/token.pickle"):
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.service = None
    
    def authenticate(self):
        """المصادقة مع Google Drive"""
        creds = None
        
        # تحقق من وجود token محفوظ
        if self.token_path.exists():
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)
        
        # إذا لا يوجد token صالح
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(
                        f"ملف credentials.json غير موجود في {self.credentials_path}\n"
                        "يرجى تحميله من Google Cloud Console"
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), self.SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # حفظ الـ token للمرات القادمة
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('drive', 'v3', credentials=creds)
        return True
    
    def upload_file(self, file_path, folder_id=None, file_name=None):
        """
        رفع ملف إلى Google Drive
        
        file_path: مسار الملف المحلي
        folder_id: معرف مجلد الوجهة (اختياري)
        file_name: اسم الملف على Drive (اختياري)
        """
        if not self.service:
            self.authenticate()
        
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"الملف غير موجود: {file_path}")
        
        if file_name is None:
            file_name = file_path.name
        
        # إعداد metadata
        file_metadata = {'name': file_name}
        
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        # تحديد نوع الملف
        mimetype = 'video/mp4' if file_path.suffix.lower() == '.mp4' else 'application/octet-stream'
        
        media = MediaFileUpload(
            str(file_path),
            mimetype=mimetype,
            resumable=True
        )
        
        # رفع الملف
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink'
        ).execute()
        
        print(f"✅ تم رفع الفيديو: {file.get('name')}")
        print(f"🔗 الرابط: {file.get('webViewLink')}")
        
        return {
            'id': file.get('id'),
            'name': file.get('name'),
            'link': file.get('webViewLink')
        }
    
    def create_folder(self, folder_name, parent_id=None):
        """إنشاء مجلد جديد"""
        if not self.service:
            self.authenticate()
        
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        if parent_id:
            file_metadata['parents'] = [parent_id]
        
        folder = self.service.files().create(
            body=file_metadata,
            fields='id'
        ).execute()
        
        return folder.get('id')
