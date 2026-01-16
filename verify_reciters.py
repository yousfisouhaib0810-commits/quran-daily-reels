"""
التحقق من توفر الملفات الصوتية لجميع القراء
"""
import sys
import json
import requests
from pathlib import Path
from src.data.surahs import SURAHS

# إصلاح مشكلة encoding في Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def verify_reciter(reciter_id, reciter_name):
    """التحقق من توفر ملفات القارئ"""
    base_url = f"https://everyayah.com/data/{reciter_id}"
    
    print(f"\n{'='*60}")
    print(f"🔍 فحص القارئ: {reciter_name}")
    print(f"   ID: {reciter_id}")
    print(f"{'='*60}")
    
    missing_files = []
    total_ayahs = 0
    
    for surah_num, surah_data in SURAHS.items():
        num_ayahs = surah_data['ayahs']
        
        for ayah in range(1, num_ayahs + 1):
            total_ayahs += 1
            # تنسيق: 001001.mp3 (surah 3 digits + ayah 3 digits)
            filename = f"{surah_num:03d}{ayah:03d}.mp3"
            url = f"{base_url}/{filename}"
            
            # فحص سريع (HEAD request)
            try:
                response = requests.head(url, timeout=5)
                if response.status_code == 404:
                    missing_files.append(f"سورة {surah_num} آية {ayah}")
                    print(f"   ❌ ناقص: {filename}")
            except Exception as e:
                print(f"   ⚠️ خطأ في فحص {filename}: {e}")
    
    print(f"\n📊 النتيجة:")
    print(f"   إجمالي الآيات: {total_ayahs}")
    print(f"   الملفات الناقصة: {len(missing_files)}")
    
    if missing_files:
        print(f"\n   ⚠️ ملفات ناقصة:")
        for i, missing in enumerate(missing_files[:10], 1):  # عرض أول 10
            print(f"      {i}. {missing}")
        if len(missing_files) > 10:
            print(f"      ... و {len(missing_files) - 10} ملف آخر")
        return False
    else:
        print(f"   ✅ جميع الملفات موجودة!")
        return True


def main():
    """فحص جميع القراء"""
    config_path = Path("config/config.json")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    reciters = config['reciters']
    
    print(f"🕌 فحص {len(reciters)} قارئ")
    print(f"⏳ قد يستغرق هذا عدة دقائق...\n")
    
    valid_reciters = []
    invalid_reciters = []
    
    for reciter in reciters:
        reciter_id = reciter['id']
        reciter_name = reciter['name']
        
        is_valid = verify_reciter(reciter_id, reciter_name)
        
        if is_valid:
            valid_reciters.append(reciter)
        else:
            invalid_reciters.append(reciter)
    
    # النتيجة النهائية
    print(f"\n\n{'='*60}")
    print(f"📋 النتيجة النهائية:")
    print(f"{'='*60}")
    print(f"✅ قراء صالحون: {len(valid_reciters)}")
    for r in valid_reciters:
        print(f"   • {r['name']}")
    
    print(f"\n❌ قراء بملفات ناقصة: {len(invalid_reciters)}")
    for r in invalid_reciters:
        print(f"   • {r['name']} ({r['id']})")
    
    # حفظ القراء الصالحين فقط
    if invalid_reciters:
        print(f"\n💡 توصية: احذف القراء التالية من config.json:")
        for r in invalid_reciters:
            print(f"   {{'id': '{r['id']}', 'name': '{r['name']}'}},")


if __name__ == "__main__":
    main()
