"""
منطق اختيار الآيات
"""
import json
from pathlib import Path
from ..data.surahs import get_surah_info, get_total_ayahs, get_next_surah


class AyahSelector:
    """اختيار الآيات المتتابعة"""
    
    def __init__(self, state_file="state/state.json", min_duration=15):
        self.state_file = Path(state_file)
        self.replay_file = self.state_file.parent / "replay_once.json"
        self.min_duration = min_duration
        self.state = self._load_state()
    
    def _load_state(self):
        """تحميل الحالة"""
        state = None
        if self.state_file.exists():
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)

        if state is None:
            state = {
            "current_position": {"surah": 1, "ayah": 1},
            "last_run": None,
            "last_reciter": None,
            "last_background": None,
            "videos_generated": 0
            }

        # This file is intentionally separate from state.json. GitHub
        # Actions may restore an older state cache over the checked-out state,
        # while the one-shot replay request must survive that restore.
        replay = self._load_replay_request()
        if replay:
            state["replay_once"] = replay
            if replay.get("position"):
                state["current_position"] = replay["position"]

        return state

    def _load_replay_request(self):
        if not self.replay_file.exists():
            return None
        try:
            with self.replay_file.open('r', encoding='utf-8') as f:
                replay = json.load(f)
            if not isinstance(replay, dict):
                return None
            position = replay.get("position") or {}
            if not position.get("surah") or not position.get("ayah"):
                return None
            return replay
        except (OSError, json.JSONDecodeError, TypeError):
            return None
    
    def _save_state(self):
        """حفظ الحالة"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)
    
    def get_current_position(self):
        """الحصول على الموقع الحالي"""
        return (
            self.state["current_position"]["surah"],
            self.state["current_position"]["ayah"]
        )
    
    def select_ayahs_for_duration(self, audio_client, target_duration=None):
        """
        اختيار آيات متتابعة حتى الوصول للمدة المطلوبة
        لا نخلط بين سور مختلفة
        """
        if target_duration is None:
            target_duration = self.min_duration
        
        surah, start_ayah = self.get_current_position()
        total_ayahs_in_surah = get_total_ayahs(surah)
        
        # حماية: تأكد أن الموقع صحيح
        if start_ayah > total_ayahs_in_surah or start_ayah < 1:
            print(f"⚠️ موقع خاطئ: السورة {surah} الآية {start_ayah}، إعادة التعيين للآية 1")
            start_ayah = 1
            self.state["current_position"]["ayah"] = 1
            self._save_state()
        
        selected_ayahs = []
        total_duration = 0
        current_ayah = start_ayah
        
        # جمع الآيات حتى الوصول للمدة المطلوبة أو نهاية السورة
        while current_ayah <= total_ayahs_in_surah:
            # تحميل الصوت وحساب المدة
            audio_path = audio_client.download_ayah(surah, current_ayah)
            
            if audio_path:
                duration = audio_client.get_audio_duration(audio_path)
                
                selected_ayahs.append({
                    "surah": surah,
                    "ayah": current_ayah,
                    "audio_path": audio_path,
                    "duration": duration
                })
                
                total_duration += duration
                
                # تحقق من الوصول للمدة المطلوبة
                if total_duration >= target_duration:
                    break
            else:
                print(f"⚠️ فشل تحميل الصوت للسورة {surah} الآية {current_ayah}")
            
            current_ayah += 1
        
        # تأكد أن لدينا آيات على الأقل
        if not selected_ayahs:
            raise Exception(f"لم يتم العثور على آيات صالحة من السورة {surah} الآية {start_ayah}")
        
        # تحديث الموقع للفيديو القادم
        next_surah = surah
        next_ayah = current_ayah + 1
        
        # إذا وصلنا لنهاية السورة، انتقل للسورة التالية
        if next_ayah > total_ayahs_in_surah:
            next_surah = get_next_surah(surah)
            next_ayah = 1
        
        return {
            "surah": surah,
            "surah_info": get_surah_info(surah),
            "start_ayah": start_ayah,
            "end_ayah": current_ayah,
            "ayahs": selected_ayahs,
            "total_duration": total_duration,
            "next_position": {"surah": next_surah, "ayah": next_ayah}
        }
    
    def update_position(self, next_position):
        """تحديث الموقع بعد توليد الفيديو"""
        self.state["current_position"] = next_position
        self.state["videos_generated"] += 1
        self._save_state()
    
    def update_last_run(self, reciter_id=None, background_id=None):
        """تحديث معلومات آخر تشغيل"""
        from datetime import datetime
        self.state["last_run"] = datetime.now().isoformat()
        if reciter_id:
            self.state["last_reciter"] = reciter_id
        if background_id:
            self.state["last_background"] = background_id
        # Consume a replay request only after the complete video pipeline has
        # reached this final state update. If generation/upload fails earlier,
        # the request remains available for the next run.
        self.state.pop("replay_once", None)
        if self.replay_file.exists():
            try:
                self.replay_file.unlink()
            except OSError as exc:
                print(f"⚠️ تعذر حذف طلب الإعادة المؤقت: {exc}")
        self._save_state()
