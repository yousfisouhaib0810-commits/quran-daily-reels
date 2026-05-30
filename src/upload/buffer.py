"""
رفع التحديثات إلى Buffer (TikTok)
"""
from typing import Optional
import requests


class BufferUploader:
    """رافع تحديثات Buffer"""

    def __init__(self, api_key: str, base_url: str = "https://api.bufferapp.com/1"):
        if not api_key:
            raise ValueError("BUFFER_API_KEY مطلوب")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def create_update(self, profile_id: str, text: str, media_link: str, shorten: bool = False) -> dict:
        """
        إنشاء تحديث في Buffer

        Args:
            profile_id: معرف الحساب (TikTok)
            text: النص المرسل
            media_link: رابط الفيديو (YouTube)
            shorten: تقصير الروابط

        Returns:
            dict: استجابة Buffer
        """
        if not profile_id:
            raise ValueError("BUFFER_TIKTOK_ID مطلوب")
        if not media_link:
            raise ValueError("media_link مطلوب")

        url = f"{self.base_url}/updates/create.json"
        payload = {
            "access_token": self.api_key,
            "text": text,
            "profile_ids[]": profile_id,
            "media[link]": media_link,
            "shorten": "true" if shorten else "false",
        }

        response = requests.post(url, data=payload, timeout=30)
        if not response.ok:
            raise RuntimeError(f"Buffer API error {response.status_code}: {response.text}")

        data = response.json()
        if data.get("success") is False:
            raise RuntimeError(f"Buffer API rejected request: {data}")

        return data
