#!/usr/bin/env python3
"""
بوت فيديو القرآن اليومي
يُنتج فيديو ريلز يومياً مع آيات من القرآن الكريم
"""

import json
import random
import sys
import os
from pathlib import Path
from datetime import datetime

# إضافة المسار الجذري
sys.path.insert(0, str(Path(__file__).parent))

from src.data.surahs import get_surah_info, SURAHS
from src.sources.api import QuranAPI, EveryAyahAudio, PexelsAPI
from src.selection.selector import AyahSelector
from src.captions.generator import CaptionGenerator
from src.audio.processor import AudioProcessor
from src.background.manager import BackgroundManager
from src.render.renderer import VideoRenderer
from src.upload.drive import GoogleDriveUploader


def load_config():
    """تحميل الإعدادات"""
    config_path = Path(__file__).parent / "config" / "config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def select_random_reciter(config, last_reciter=None):
    """اختيار قارئ عشوائي مختلف عن السابق"""
    reciters = config["reciters"]
    available = [r for r in reciters if r["id"] != last_reciter]
    
    if not available:
        available = reciters
    
    return random.choice(available)


def main():
    """البايبلاين الرئيسي"""
    print("=" * 50)
    print("🕌 بوت فيديو القرآن اليومي")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # تحميل الإعدادات
    config = load_config()
    
    # ===== 1. اختيار القارئ =====
    print("\n📖 اختيار القارئ...")
    selector = AyahSelector(
        state_file="state/state.json",
        min_duration=config["timing"]["min_duration_seconds"]
    )
    
    last_reciter = selector.state.get("last_reciter")
    reciter = select_random_reciter(config, last_reciter)
    print(f"   القارئ: {reciter['name']}")
    
    # ===== 2. اختيار الآيات =====
    print("\n📜 اختيار الآيات...")
    audio_client = EveryAyahAudio(
        reciter_id=reciter["id"],
        cache_dir="data/audio"
    )
    
    selection = selector.select_ayahs_for_duration(
        audio_client,
        target_duration=config["timing"]["min_duration_seconds"]
    )
    
    surah_info = selection["surah_info"]
    print(f"   السورة: {surah_info['name']} ({surah_info['name_en']})")
    print(f"   الآيات: {selection['start_ayah']} - {selection['end_ayah']}")
    print(f"   المدة: {selection['total_duration']:.2f} ثانية")
    
    # ===== 3. جلب النصوص والترجمات =====
    print("\n📝 جلب النصوص والترجمات...")
    quran_api = QuranAPI(translation_id=config["sources"]["translation_id"])
    
    ayahs_data = []
    for ayah_info in selection["ayahs"]:
        arabic = quran_api.get_ayah_text(ayah_info["surah"], ayah_info["ayah"])
        english = quran_api.get_ayah_translation(ayah_info["surah"], ayah_info["ayah"])
        
        if arabic and english:
            ayahs_data.append({
                "surah": ayah_info["surah"],
                "ayah": ayah_info["ayah"],
                "arabic": arabic,
                "english": english.upper(),
                "audio_path": ayah_info["audio_path"],
                "duration": ayah_info["duration"]
            })
    
    print(f"   تم جلب {len(ayahs_data)} آية")
    
    # ===== 4. معالجة الصوت =====
    print("\n🔊 معالجة الصوت...")
    audio_processor = AudioProcessor(output_dir="temp")
    
    audio_files = [a["audio_path"] for a in ayahs_data]
    padding_before = config["timing"]["padding_before_ms"] / 1000
    padding_after = config["timing"]["padding_after_ms"] / 1000
    
    final_audio = audio_processor.concatenate_audio(
        audio_files,
        output_path="temp/final_audio.mp3",
        padding_before=padding_before,
        padding_after=padding_after
    )
    
    total_duration = audio_processor.get_duration(final_audio)
    print(f"   مدة الصوت النهائية: {total_duration:.2f} ثانية")
    
    # ===== 5. تحضير الخلفية =====
    print("\n🎬 تحضير الخلفية...")
    
    pexels_api_key = os.environ.get("PEXELS_API_KEY", config["pexels"]["api_key"])
    
    if pexels_api_key == "YOUR_PEXELS_API_KEY_HERE":
        print("   ⚠️ لم يتم تعيين Pexels API Key - استخدام خلفية افتراضية")
        # إنشاء خلفية سوداء بسيطة
        background_path = create_default_background(total_duration, config)
    else:
        pexels = PexelsAPI(api_key=pexels_api_key, cache_dir="data/backgrounds")
        bg_manager = BackgroundManager(pexels)
        
        background = bg_manager.get_random_background(
            duration_needed=total_duration,
            search_queries=config["pexels"]["search_queries"]
        )
        
        if background:
            background_path = bg_manager.prepare_background(
                background["path"],
                "temp/background_prepared.mp4",
                target_duration=total_duration,
                width=config["video"]["width"],
                height=config["video"]["height"]
            )
            print(f"   تم تحضير الخلفية: {background['id']}")
        else:
            background_path = create_default_background(total_duration, config)
    
    # ===== 6. توليد الترجمة =====
    print("\n📝 توليد الترجمة...")
    caption_gen = CaptionGenerator(config)
    
    segments = caption_gen.create_segments_from_ayahs(ayahs_data, padding_before=padding_before)
    
    ass_path = caption_gen.generate_ass(
        segments,
        output_path="temp/captions.ass",
        padding_before=0,
        padding_after=0
    )
    print(f"   تم إنشاء ملف الترجمة")
    
    # ===== 7. رندر الفيديو =====
    print("\n🎥 رندر الفيديو...")
    renderer = VideoRenderer(config, output_dir="output")
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    surah_name = surah_info["name_en"].replace(" ", "_").replace("'", "")
    output_filename = f"{date_str}_{surah_name}_{selection['start_ayah']}-{selection['end_ayah']}.mp4"
    
    final_video = renderer.render(
        background_path=background_path,
        audio_path=final_audio,
        ass_path=ass_path,
        output_filename=output_filename
    )
    
    # ===== 8. رفع إلى Google Drive =====
    print("\n☁️ رفع إلى Google Drive...")
    
    if config["google_drive"]["enabled"]:
        try:
            drive = GoogleDriveUploader()
            drive.authenticate()
            
            folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", config["google_drive"].get("folder_id"))
            
            result = drive.upload_file(
                final_video,
                folder_id=folder_id if folder_id != "YOUR_GOOGLE_DRIVE_FOLDER_ID" else None
            )
            print(f"   ✅ تم الرفع: {result['link']}")
        except Exception as e:
            print(f"   ⚠️ فشل الرفع: {e}")
    else:
        print("   ⏭️ الرفع معطل")
    
    # ===== 9. تحديث الحالة =====
    print("\n💾 تحديث الحالة...")
    selector.update_position(selection["next_position"])
    selector.update_last_run(
        reciter_id=reciter["id"],
        background_id=background.get("id") if 'background' in dir() else None
    )
    
    next_pos = selection["next_position"]
    next_surah = get_surah_info(next_pos["surah"])
    print(f"   الفيديو القادم: {next_surah['name']} - آية {next_pos['ayah']}")
    
    # ===== تم =====
    print("\n" + "=" * 50)
    print("✅ تم بنجاح!")
    print(f"📁 الفيديو: {final_video}")
    print("=" * 50)
    
    return final_video


def create_default_background(duration, config):
    """إنشاء خلفية افتراضية (تدرج أزرق داكن)"""
    import subprocess
    
    output_path = "temp/default_background.mp4"
    Path("temp").mkdir(exist_ok=True)
    
    width = config["video"]["width"]
    height = config["video"]["height"]
    fps = config["video"]["fps"]
    
    # إنشاء خلفية متدرجة
    cmd = [
        'ffmpeg', '-y',
        '-f', 'lavfi',
        '-i', f'color=c=0x1a1a2e:size={width}x{height}:duration={duration}:rate={fps}',
        '-vf', 'format=yuv420p',
        '-c:v', 'libx264', '-preset', 'fast',
        output_path
    ]
    
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
