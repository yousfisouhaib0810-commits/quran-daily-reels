# 🔧 دليل حل المشاكل | Troubleshooting Guide

## المشكلة: توقف البوت عن إنشاء الفيديوهات اليومية

### الأعراض
- آخر فيديو تم إنشاؤه كان في 27 يناير 2026
- لم تعمل الجدولة التلقائية (cron) منذ ذلك التاريخ
- البوت يعمل فقط عند التشغيل اليدوي

### السبب الجذري ✅ تم الإصلاح

**المشكلة الرئيسية**: كان الـ workflow يفتقد إلى صلاحية `contents: write`

#### التفاصيل:
1. كان الـ workflow يحاول حفظ حالة التقدم عبر `git commit` و `git push`
2. لكن بدون صلاحية `contents: write`، كانت عملية الـ push تفشل صامتة (بسبب `|| true`)
3. بدون commits منتظمة، اعتبر GitHub المستودع غير نشط
4. GitHub يعطل الـ workflows المجدولة تلقائياً إذا لم يكن هناك نشاط في المستودع
5. **مشكلة أمنية إضافية**: كانت مفاتيح API محفوظة مباشرة في ملف config.json

### الإصلاحات المطبقة ✅

#### 1. إضافة صلاحيات للـ Workflow
```yaml
permissions:
  contents: write
```
هذا يسمح للـ workflow بعمل commit و push للتغييرات.

#### 2. تحسين خطوة الـ Commit
```yaml
git add state/state.json
if ! git diff --staged --quiet; then
  git commit -m "📊 Update state after video generation [$(date +'%Y-%m-%d')]"
  git push
else
  echo "No state changes to commit"
fi
```
- إزالة `|| true` التي كانت تخفي الأخطاء
- إضافة رسائل commit أفضل مع التاريخ
- معالجة أفضل للأخطاء

#### 3. إزالة المفاتيح المكشوفة (Security Fix)
- تم إزالة Pexels API key من config.json
- تم إزالة OpenAI API key من config.json  
- تم إزالة Google Drive folder ID من config.json
- الآن يتم استخدام المفاتيح من GitHub Secrets فقط

## كيفية التحقق من أن الإصلاح نجح

### 1. التحقق من الصلاحيات
انتقل إلى ملف `.github/workflows/daily-video.yml` وتأكد من وجود:
```yaml
permissions:
  contents: write
```

### 2. التحقق من الـ Secrets
اذهب إلى: `Settings → Secrets and variables → Actions`

تأكد من وجود:
- ✅ `PEXELS_API_KEY`
- ✅ `OPENAI_API_KEY`
- ✅ `GOOGLE_CREDENTIALS`
- ✅ `GOOGLE_DRIVE_FOLDER_ID`
- ✅ `YOUTUBE_TOKEN` (إذا كان YouTube مفعل)

### 3. تشغيل يدوي للاختبار
1. اذهب إلى تبويب `Actions`
2. اختر `Daily Quran Reel Generator`
3. اضغط `Run workflow`
4. انتظر حتى يكتمل التشغيل
5. **تحقق من الـ commits**: يجب أن ترى commit جديد من `github-actions[bot]` بعنوان "📊 Update state after video generation"

### 4. التحقق من الجدولة التلقائية
- بعد التشغيل اليدوي الناجح، سيعمل البوت تلقائياً كل يوم عند 6:00 صباحاً (بتوقيت الجزائر)
- تأكد من أن الـ workflow غير معطل في تبويب Actions

## مشاكل شائعة وحلولها

### المشكلة: "Permission denied" عند الـ push
**الحل**: تأكد من وجود `permissions: contents: write` في ملف الـ workflow

### المشكلة: "API key not found"
**الحل**: أضف المفتاح في GitHub Secrets (Settings → Secrets and variables → Actions)

### المشكلة: الـ Workflow معطل (Disabled)
**الحل**: 
1. اذهب إلى Actions
2. ابحث عن رسالة "This workflow was disabled..."
3. اضغط "Enable workflow"

### المشكلة: لا توجد commits بعد تشغيل الـ workflow
**الحل**: 
1. تحقق من logs الـ workflow
2. ابحث عن أخطاء في خطوة "Commit state changes"
3. تأكد من أن ملف state/state.json يتغير فعلاً

## معلومات إضافية

### لماذا يحتاج البوت إلى عمل commits؟
1. **حفظ التقدم**: لتذكر آخر آية تمت قراءتها
2. **إبقاء الـ Workflow نشطاً**: GitHub يعطل الـ workflows بدون نشاط
3. **تتبع التاريخ**: لمعرفة متى تم إنشاء كل فيديو

### جدولة التشغيل
```yaml
schedule:
  - cron: '0 5 * * *'  # 5:00 UTC = 6:00 Algeria Time
```

إذا أردت تغيير الوقت:
- `0 4 * * *` = 5:00 صباحاً بتوقيت الجزائر
- `0 6 * * *` = 7:00 صباحاً بتوقيت الجزائر

## الدعم

إذا واجهت مشاكل أخرى:
1. تحقق من logs الـ workflow في تبويب Actions
2. افتح Issue في المستودع
3. تأكد من صلاحية جميع API Keys

---

**آخر تحديث**: 18 فبراير 2026
