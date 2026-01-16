# دليل إعداد النشر اليومي التلقائي على YouTube

## الخطوات المطلوبة:

### 1. إعداد YouTube API

1. افتح [Google Cloud Console](https://console.cloud.google.com/)
2. أنشئ مشروع جديد أو اختر مشروع موجود
3. فعّل **YouTube Data API v3**:
   - اذهب إلى "APIs & Services" > "Enable APIs and Services"
   - ابحث عن "YouTube Data API v3"
   - اضغط "Enable"

4. أنشئ بيانات اعتماد OAuth 2.0:
   - اذهب إلى "APIs & Services" > "Credentials"
   - اضغط "Create Credentials" > "OAuth 2.0 Client ID"
   - اختر نوع التطبيق: "Desktop app"
   - سمّه "Quran Daily Bot"
   - احفظ الملف JSON

5. أنشئ Refresh Token:
   ```bash
   # شغل هذا محلياً مرة واحدة
   python setup_youtube_auth.py
   ```
   سيفتح متصفح للتصريح - سجل دخول بحساب YouTube الخاص بك

### 2. إضافة Secrets في GitHub

اذهب إلى مستودع GitHub → Settings → Secrets and variables → Actions → New repository secret:

1. **OPENAI_API_KEY**: مفتاح OpenAI (موجود مسبقاً)
2. **PEXELS_API_KEY**: مفتاح Pexels (موجود مسبقاً)
3. **YOUTUBE_ENABLED**: ضع القيمة `true`
4. **YOUTUBE_CLIENT_SECRETS**: الصق محتوى ملف الـ OAuth JSON بالكامل

### 3. الجدولة التلقائية

الـ workflow الآن مضبوط على:
- **التوقيت**: 6:00 صباحاً بتوقيت الجزائر (UTC+1)
- **التكرار**: يومياً
- **cron**: `0 5 * * *`

### 4. التشغيل اليدوي (اختبار)

يمكنك تشغيل البوت يدوياً:
- اذهب إلى GitHub → Actions → Daily Quran Reel Generator
- اضغط "Run workflow"

### 5. ما يحدث تلقائياً كل يوم:

1. ✅ يختار قارئ عشوائي
2. ✅ يختار آيات قرآنية (استكمال من الموقع السابق)
3. ✅ يحلل الصوت للتزامن الدقيق
4. ✅ يختار خلفية مناسبة بالذكاء الاصطناعي
5. ✅ ينشئ الفيديو بدقة عالية
6. ✅ يرفعه على YouTube تلقائياً
7. ✅ يحدث الموقع للآية التالية

---

## ملاحظات مهمة:

- **Quota**: YouTube API لديه حد يومي للرفع (عادة 6 فيديوهات/يوم للحسابات الجديدة)
- **الخصوصية**: الفيديوهات تُنشر كـ `public` تلقائياً
- **العنوان**: يُنشأ تلقائياً: "اسم السورة | آية X-Y | اسم القارئ"
- **الوصف**: يتضمن معلومات السورة والقارئ ووسوم مناسبة
