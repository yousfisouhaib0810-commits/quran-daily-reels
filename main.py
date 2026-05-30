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
from src.ai.background_advisor import BackgroundAdvisor
from src.detection.person_detector import PersonDetector
from src.render.renderer import VideoRenderer
from src.upload.drive import GoogleDriveUploader
from src.upload.youtube import YouTubeUploader


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
    
    # ===== 3. جلب النصوص (نص عربي فقط) =====
    print("\n📝 جلب النصوص... (بدون ترجمة)")
    quran_api = QuranAPI(translation_id=config["sources"]["translation_id"]) 
    
    ayahs_data = []
    for ayah_info in selection["ayahs"]:
        arabic = quran_api.get_ayah_text(ayah_info["surah"], ayah_info["ayah"])
        
        if arabic:
            ayahs_data.append({
                "surah": ayah_info["surah"],
                "ayah": ayah_info["ayah"],
                "arabic": arabic,
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

    advisor_context = {
        "surah": surah_info["name_en"],
        "ayah_range": f"{selection['start_ayah']}-{selection['end_ayah']}",
        "arabic_preview": " | ".join(a["arabic"] for a in ayahs_data[:3])
    }

    ai_config = config.get("ai_background", {})
    person_config = config.get("person_filter", {})

    advisor = None
    # تفضيل مفتاح من الإعدادات، ثم المتغير البيئي OPENAI_API_KEY
    ai_key = ai_config.get("api_key") or os.environ.get("OPENAI_API_KEY")
    
    print(f"   🤖 إعدادات الذكاء الاصطناعي:")
    print(f"      Enabled: {ai_config.get('enabled')}")
    print(f"      Provider: {ai_config.get('provider')}")
    print(f"      Model: {ai_config.get('model')}")
    print(f"      API Key: {'✅ موجود' if ai_key else '❌ غير موجود'}")
    
    if ai_config.get("enabled") and ai_key:
        print(f"   ✅ تفعيل الذكاء الاصطناعي لاختيار الخلفية...")
        advisor = BackgroundAdvisor(
            api_key=ai_key,
            model=ai_config.get("model", "gpt-4o-mini"),
            temperature=ai_config.get("temperature", 0.35)
        )
    elif ai_config.get("enabled"):
        print("   ⚠️ تم تفعيل الذكاء الاصطناعي لكن لم يتم العثور على مفتاح OpenAI (OPENAI_API_KEY أو ai_background.api_key)")

    person_detector = None
    if person_config.get("enabled", True):
        try:
            person_detector = PersonDetector(
                sample_frames=person_config.get("sample_frames", 12),
                min_detections=person_config.get("min_detections", 1),
                confidence_threshold=person_config.get("confidence_threshold", 0.5),
                resize_width=person_config.get("resize_width", 720)
            )
        except Exception as exc:  # noqa: BLE001
            print(f"   ⚠️ تعذر تهيئة فلتر الأشخاص: {exc}")

    pexels_api_key = os.environ.get("PEXELS_API_KEY", config["pexels"]["api_key"])
    
    if pexels_api_key == "YOUR_PEXELS_API_KEY_HERE":
        print("   ⚠️ لم يتم تعيين Pexels API Key - استخدام خلفية افتراضية")
        background_path = create_default_background(total_duration, config)
        background = None
    else:
        pexels = PexelsAPI(api_key=pexels_api_key, cache_dir="data/backgrounds")
        bg_manager = BackgroundManager(
            pexels,
            advisor=advisor,
            person_detector=person_detector,
            max_attempts=ai_config.get("max_attempts", 5)
        )
        
        background = bg_manager.get_random_background(
            duration_needed=total_duration,
            search_queries=config["pexels"]["search_queries"],
            context=advisor_context,
            orientation=config["pexels"].get("orientation", "portrait"),
            min_duration=config["pexels"].get("min_duration")
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
    
    # ===== 8. رفع إلى Google Drive و YouTube =====
    print("\n☁️ رفع الفيديو...")
    
    # رفع إلى Google Drive
    if config["google_drive"]["enabled"]:
        try:
            drive = GoogleDriveUploader()
            drive.authenticate()
            
            folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", config["google_drive"].get("folder_id"))
            
            result = drive.upload_file(
                final_video,
                folder_id=folder_id if folder_id != "YOUR_GOOGLE_DRIVE_FOLDER_ID" else None
            )
            print(f"   ✅ Google Drive: {result['link']}")
        except Exception as e:
            print(f"   ⚠️ فشل رفع Google Drive: {e}")
    
    # رفع إلى YouTube
    youtube_enabled = os.environ.get("YOUTUBE_ENABLED", "false").lower() == "true"
    print(f"\n📺 YouTube Upload Status: YOUTUBE_ENABLED={youtube_enabled}")
    
    if youtube_enabled:
        try:
            print("   🔐 جاري المصادقة مع YouTube...")
            youtube = YouTubeUploader()
            youtube.authenticate()
            
            # تجهيز العنوان والوصف
            surah_name = surah_info["name"]
            ayah_range = f"{selection['start_ayah']}-{selection['end_ayah']}"
            title = f"{surah_name} | آية {ayah_range} | {reciter['name']} #Shorts"
            
            description = f"""تلاوة خاشعة من سورة {surah_name}
الآيات: {ayah_range}
القارئ: {reciter['name']}

#Shorts #قرآن #تلاوة #Quran #Recitation #{surah_info['name_en'].replace(' ', '')}"""
            
            print(f"   📤 جاري رفع الفيديو: {title}")
            result = youtube.upload_video(
                final_video,
                title=title,
                description=description,
                tags=["Shorts", "قرآن", "تلاوة", "Quran", reciter['name'], surah_info['name_en']],
                category_id="22",
                privacy_status="public"
            )
            print(f"   ✅ YouTube: {result['url']}")

            buffer_api_key = os.environ.get("BUFFER_API_KEY")
            buffer_tiktok_id = os.environ.get("BUFFER_TIKTOK_ID")
            if buffer_api_key and buffer_tiktok_id:
                try:
                    from src.upload.buffer import BufferUploader

                    buffer = BufferUploader(api_key=buffer_api_key)
                    buffer_result = buffer.create_update(
                        profile_id=buffer_tiktok_id,
                        text=f"{title}\n\n{description}",
                        media_link=result["url"]
                    )
                    update_id = buffer_result.get("update", {}).get("id") or buffer_result.get("id")
                    print(f"   ✅ Buffer/TikTok: تم إنشاء تحديث {update_id}")
                except Exception as e:
                    print(f"   ⚠️ فشل نشر TikTok عبر Buffer: {e}")
            else:
                print("   ⚠️ تخطي Buffer/TikTok: BUFFER_API_KEY أو BUFFER_TIKTOK_ID غير متوفر")
        except Exception as e:
            print(f"   ❌ فشل رفع YouTube: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("   ⚠️ YouTube upload معطل (YOUTUBE_ENABLED != true)")
    
    # ===== 9. تحديث الحالة =====
    print("\n💾 تحديث الحالة...")
    selector.update_position(selection["next_position"])
    background_id = background["id"] if isinstance(background, dict) else None
    selector.update_last_run(
        reciter_id=reciter["id"],
        background_id=background_id
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
