# دليل إعداد النشر اليومي التلقائي على YouTube

## ⚠️ مهم: يجب إكمال هذه الخطوات لتفعيل النشر التلقائي على YouTube

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
   - نزّل الملف JSON واحفظه باسم `client_secret.json` في مجلد المشروع

### 2. إنشاء YouTube Token (مرة واحدة فقط)

قم بتشغيل السكريبت التالي على جهازك المحلي:

```bash
python setup_youtube_auth.py
```

**ماذا سيحدث:**
1. سيفتح متصفح تلقائياً
2. سجل دخول بحساب YouTube الذي تريد النشر عليه
3. اقبل الصلاحيات المطلوبة
4. السكريبت سيطبع لك JSON يحتوي على refresh token
5. **انسخ هذا JSON** - ستحتاجه في الخطوة التالية

### 3. إضافة Secrets في GitHub

اذهب إلى مستودع GitHub → Settings → Secrets and variables → Actions:

**Secrets المطلوبة:**

1. **YOUTUBE_TOKEN** (جديد - مهم!):
   - الصق JSON الذي حصلت عليه من الخطوة السابقة
   - هذا يحتوي على refresh token للمصادقة التلقائية

2. **YOUTUBE_ENABLED**: 
   - القيمة: `true`

3. Secrets الموجودة مسبقاً:
   - ✅ OPENAI_API_KEY
   - ✅ PEXELS_API_KEY
   - ✅ GOOGLE_CREDENTIALS
   - ✅ GOOGLE_DRIVE_FOLDER_ID

### 4. الجدولة التلقائية

الـ workflow الآن مضبوط على:
- **التوقيت**: 6:00 صباحاً بتوقيت الجزائر (UTC+1)
- **التكرار**: يومياً
- **cron**: `0 5 * * *`

### 5. التشغيل اليدوي (اختبار)

يمكنك تشغيل البوت يدوياً:
- اذهب إلى GitHub → Actions → Daily Quran Reel Generator
- اضغط "Run workflow"

### 6. ما يحدث تلقائياً كل يوم:

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
