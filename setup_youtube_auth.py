"""
سكريبت لإعداد مصادقة YouTube مرة واحدة
"""
import os
import json
import pickle
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# YouTube API scope
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']


def setup_youtube_credentials():
    """إنشاء refresh token لـ YouTube"""
    
    print("🔐 إعداد مصادقة YouTube...")
    print("\n⚠️ تأكد من أنك قمت بـ:")
    print("   1. إنشاء OAuth 2.0 Client ID في Google Cloud Console")
    print("   2. تنزيل ملف JSON وحفظه كـ 'client_secret.json' في هذا المجلد")
    print("\nالضغط Enter للمتابعة...")
    input()
    
    client_secret_file = Path("client_secret.json")
    
    if not client_secret_file.exists():
        print("❌ لم يتم العثور على client_secret.json")
        print("   قم بتنزيله من Google Cloud Console أولاً")
        return
    
    creds = None
    token_file = Path("config/youtube_token.pickle")
    token_file.parent.mkdir(parents=True, exist_ok=True)
    
    # التحقق من وجود token سابق
    if token_file.exists():
        with open(token_file, 'rb') as f:
            creds = pickle.load(f)
    
    # إذا لا يوجد credentials صالح
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 تحديث الـ token...")
            creds.refresh(Request())
        else:
            print("\n🌐 سيتم فتح متصفح للمصادقة...")
            print("   سجل دخول بحساب YouTube الذي تريد الرفع عليه")
            
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secret_file), SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # حفظ الـ credentials كـ pickle
        with open(token_file, 'wb') as f:
            pickle.dump(creds, f)
        
        print(f"\n✅ تم حفظ الـ credentials في: {token_file}")
    
    # طباعة المعلومات للـ GitHub Secret
    print("\n" + "="*50)
    print("📋 معلومات GitHub Secret:")
    print("="*50)
    print("\nSecret Name: YOUTUBE_TOKEN")
    print("\nSecret Value (انسخ هذا):\n")
    
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }
    
    print(json.dumps(token_data, indent=2))
    
    print("\n" + "="*50)
    print("\n✅ الآن:")
    print("   1. انسخ JSON أعلاه")
    print("   2. اذهب إلى GitHub Repository → Settings → Secrets")
    print("   3. أنشئ Secret باسم: YOUTUBE_TOKEN")
    print("   4. الصق المحتوى المنسوخ")
    print("   5. تأكد أن YOUTUBE_ENABLED = true موجود")
    print("="*50)


if __name__ == "__main__":
    setup_youtube_credentials()
