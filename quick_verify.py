"""
فحص سريع للقراء - عينة من كل سورة
"""
import sys
import json
import requests
from pathlib import Path
from src.data.surahs import SURAHS

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def quick_verify_reciter(reciter_id, reciter_name):
    """فحص سريع: عينة من كل سورة"""
    base_url = f"https://everyayah.com/data/{reciter_id}"
    
    print(f"\nالقارئ: {reciter_name} ({reciter_id})")
    
    missing = []
    checked = 0
    
    # فحص أول 3 آيات من كل سورة + آخر آية
    for surah_num, surah_data in list(SURAHS.items())[:114]:
        num_ayahs = surah_data['ayahs']
        test_ayahs = [1, 2, 3, num_ayahs] if num_ayahs >= 3 else list(range(1, num_ayahs + 1))
        
        for ayah in test_ayahs:
            checked += 1
            filename = f"{surah_num:03d}{ayah:03d}.mp3"
            url = f"{base_url}/{filename}"
            
            try:
                response = requests.head(url, timeout=3)
                if response.status_code == 404:
                    missing.append(f"سورة {surah_num}:{ayah}")
                    print(f"  ❌ {filename}")
            except:
                pass
    
    if missing:
        print(f"  ⚠️  {len(missing)} ملف ناقص من {checked} عينة")
        return False
    else:
        print(f"  ✅ {checked} ملف تم فحصها - كلها موجودة")
        return True


def main():
    config_path = Path("config/config.json")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    reciters = config['reciters']
    
    print(f"فحص {len(reciters)} قارئ (عينة سريعة)...\n")
    
    valid = []
    invalid = []
    
    for i, reciter in enumerate(reciters, 1):
        print(f"[{i}/{len(reciters)}]", end=" ")
        is_valid = quick_verify_reciter(reciter['id'], reciter['name'])
        
        if is_valid:
            valid.append(reciter)
        else:
            invalid.append(reciter)
    
    print(f"\n{'='*60}")
    print(f"النتيجة:")
    print(f"  ✅ صالح: {len(valid)} قارئ")
    print(f"  ❌ بملفات ناقصة: {len(invalid)} قارئ")
    
    if invalid:
        print(f"\nيجب حذف:")
        for r in invalid:
            print(f'  {{"id": "{r["id"]}", "name": "{r["name"]}"}},')


if __name__ == "__main__":
    main()
