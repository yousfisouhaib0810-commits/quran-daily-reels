"""Automatic background quality checks.

The filter rejects the known dark-blue placeholder and downloaded videos that
are effectively a still image. It intentionally combines motion, texture,
dominant colour and edge density so that a moving night/space scene is not
discarded merely because it is dark or blue.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List

import cv2
import numpy as np


@dataclass
class BackgroundQualityReport:
    accepted: bool
    reason: str
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BackgroundQualityFilter:
    """Reject static/placeholder backgrounds before they reach the renderer."""

    def __init__(
        self,
        sample_frames: int = 12,
        resize_width: int = 320,
        motion_threshold: float = 0.012,
        uniform_ratio_threshold: float = 0.82,
        blue_ratio_threshold: float = 0.62,
        frame_std_threshold: float = 18.0,
        edge_ratio_threshold: float = 0.010,
    ) -> None:
        self.sample_frames = max(3, int(sample_frames))
        self.resize_width = max(96, int(resize_width))
        self.motion_threshold = float(motion_threshold)
        self.uniform_ratio_threshold = float(uniform_ratio_threshold)
        self.blue_ratio_threshold = float(blue_ratio_threshold)
        self.frame_std_threshold = float(frame_std_threshold)
        self.edge_ratio_threshold = float(edge_ratio_threshold)

    def check(self, video_path: str) -> BackgroundQualityReport:
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            return BackgroundQualityReport(False, "video_unreadable", {})

        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        indices = np.linspace(0, max(0, total_frames - 1), self.sample_frames, dtype=int)
        frames: List[np.ndarray] = []
        motions: List[float] = []
        uniform_ratios: List[float] = []
        blue_ratios: List[float] = []
        frame_stds: List[float] = []
        edge_ratios: List[float] = []
        mean_colours: List[np.ndarray] = []

        previous_gray = None
        for index in sorted(set(int(value) for value in indices)):
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue

            if frame.shape[1] > self.resize_width:
                ratio = self.resize_width / frame.shape[1]
                frame = cv2.resize(
                    frame,
                    (self.resize_width, max(1, int(frame.shape[0] * ratio))),
                    interpolation=cv2.INTER_AREA,
                )
            frames.append(frame)

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mean_colour = frame.reshape(-1, 3).mean(axis=0)
            mean_colours.append(mean_colour)
            frame_stds.append(float(np.std(gray)))

            colour_distance = np.linalg.norm(frame.astype(np.float32) - mean_colour, axis=2)
            uniform_ratios.append(float(np.mean(colour_distance <= 22.0)))

            # OpenCV hue is [0, 179]. This covers dark navy/blue placeholders
            # while excluding most neutral black/grey backgrounds.
            blue_mask = (
                (hsv[:, :, 0] >= 100)
                & (hsv[:, :, 0] <= 140)
                & (hsv[:, :, 1] >= 35)
                & (hsv[:, :, 2] <= 165)
            )
            blue_ratios.append(float(np.mean(blue_mask)))

            edges = cv2.Canny(gray, 50, 120)
            edge_ratios.append(float(np.mean(edges > 0)))

            if previous_gray is not None:
                delta = cv2.absdiff(gray, previous_gray)
                motions.append(float(np.mean(delta) / 255.0))
            previous_gray = gray

        capture.release()

        if not frames:
            return BackgroundQualityReport(False, "no_frames", {})

        metrics = {
            "sampled_frames": len(frames),
            "motion_mean": float(np.mean(motions)) if motions else 0.0,
            "motion_p90": float(np.percentile(motions, 90)) if motions else 0.0,
            "uniform_ratio": float(np.mean(uniform_ratios)),
            "blue_ratio": float(np.mean(blue_ratios)),
            "frame_std": float(np.mean(frame_stds)),
            "edge_ratio": float(np.mean(edge_ratios)),
            "mean_bgr": [float(value) for value in np.mean(mean_colours, axis=0)],
        }

        static = (
            metrics["motion_mean"] <= self.motion_threshold
            and metrics["motion_p90"] <= self.motion_threshold * 2.5
        )
        uniform = (
            metrics["uniform_ratio"] >= self.uniform_ratio_threshold
            and metrics["frame_std"] <= self.frame_std_threshold
        )
        blue = metrics["blue_ratio"] >= self.blue_ratio_threshold
        textureless = metrics["edge_ratio"] <= self.edge_ratio_threshold

        # Exact/near-exact match for the project's old 0x1a1a2e placeholder.
        default_bgr = np.array([46.0, 26.0, 26.0])
        colour_distance = float(np.linalg.norm(np.array(metrics["mean_bgr"]) - default_bgr))
        default_like = uniform and colour_distance <= 28.0

        if default_like:
            return BackgroundQualityReport(False, "project_blue_placeholder", metrics)
        if static and uniform and blue:
            return BackgroundQualityReport(False, "static_blue_background", metrics)
        if static and uniform and textureless:
            return BackgroundQualityReport(False, "static_uniform_background", metrics)

        return BackgroundQualityReport(True, "accepted", metrics)
