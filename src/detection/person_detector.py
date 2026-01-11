"""فلترة الفيديوهات التي تحتوي على أشخاص باستخدام OpenCV HOG."""
from __future__ import annotations

from typing import List

import cv2


class PersonDetector:
    """يراقب عينات من الفيديو للتأكد من خلوه من الأشخاص."""

    def __init__(
        self,
        sample_frames: int = 10,
        min_detections: int = 1,
        confidence_threshold: float = 0.4,
        resize_width: int = 720
    ) -> None:
        self.sample_frames = max(1, sample_frames)
        self.min_detections = max(1, min_detections)
        self.confidence_threshold = confidence_threshold
        self.resize_width = resize_width

        self._hog = cv2.HOGDescriptor()
        self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def contains_person(self, video_path: str) -> bool:
        """إرجاع True إذا اكتشف شخصاً في عينات من الفيديو."""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print("⚠️ تعذر فتح الفيديو لفحص الأشخاص.")
            return False

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        indices = self._sample_indices(total_frames)
        detections = 0

        for frame_index in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue

            processed = self._prepare_frame(frame)
            rects, weights = self._hog.detectMultiScale(
                processed,
                winStride=(8, 8),
                padding=(8, 8),
                scale=1.05
            )

            hits = self._count_confident(weights)
            detections += hits

            if detections >= self.min_detections:
                cap.release()
                return True

        cap.release()
        return False

    def _prepare_frame(self, frame):
        """تصغير وتحويل الإطار إلى grayscale لتسريع الكشف."""
        if self.resize_width and frame.shape[1] > self.resize_width:
            ratio = self.resize_width / frame.shape[1]
            new_size = (int(frame.shape[1] * ratio), int(frame.shape[0] * ratio))
            frame = cv2.resize(frame, new_size)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return gray

    def _count_confident(self, weights: List[float]) -> int:
        """حساب عدد الاكتشافات ذات الثقة الكافية."""
        count = 0
        for weight in weights:
            if weight >= self.confidence_threshold:
                count += 1
        return count

    def _sample_indices(self, total_frames: int) -> List[int]:
        """اختيار إطارات موزعة بالتساوي للفحص."""
        step = max(1, total_frames // self.sample_frames)
        indices = [min(total_frames - 1, i * step) for i in range(self.sample_frames)]
        return sorted(set(indices))
