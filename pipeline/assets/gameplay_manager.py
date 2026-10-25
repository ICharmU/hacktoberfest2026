"""
Gameplay Manager for slicing and preparing Subway Surfers background clips.
"""

import random
from pathlib import Path
from moviepy.editor import VideoFileClip
import moviepy.video.fx.all as vfx

from pipeline.config import DEFAULT_GAMEPLAY_VIDEO, VIDEO_WIDTH, VIDEO_HEIGHT

class GameplayManager:
    def __init__(self, gameplay_path: Path = DEFAULT_GAMEPLAY_VIDEO):
        self.gameplay_path = gameplay_path
        if not self.gameplay_path.exists():
            raise FileNotFoundError(f"Subway Surfers gameplay clip not found at {self.gameplay_path}")

    def get_sliced_clip(self, target_duration: float):
        """
        Loads the source gameplay video, slices a random segment of length target_duration,
        and resizes/crops to vertical (VIDEO_WIDTH x VIDEO_HEIGHT).
        """
        print(f"[gameplay] Loading source video: {self.gameplay_path}...")
        full_clip = VideoFileClip(str(self.gameplay_path))
        total_duration = full_clip.duration
        
        if total_duration < target_duration:
            # Loop clip if target duration exceeds available gameplay
            loops = int(target_duration // total_duration) + 1
            full_clip = vfx.loop(full_clip, n=loops)
            total_duration = full_clip.duration
            
        max_start = max(0.0, total_duration - target_duration - 2.0)
        start_time = random.uniform(0.0, max_start)
        end_time = start_time + target_duration + 1.0
        
        print(f"[gameplay] Slicing random segment: {start_time:.2f}s to {end_time:.2f}s (duration: {target_duration:.2f}s)...", flush=True)
        sub_clip = full_clip.subclip(start_time, end_time)
        
        # Crop to vertical 9:16 ratio and resize to 1080x1920
        # If original is landscape (e.g. 1920x1080): crop center width = height * 9/16
        w, h = sub_clip.size
        target_aspect = VIDEO_WIDTH / VIDEO_HEIGHT  # 9/16 = 0.5625
        current_aspect = w / h
        
        if current_aspect > target_aspect:
            # Wider than 9:16 -> crop width
            new_w = int(h * target_aspect)
            x1 = (w - new_w) // 2
            sub_clip = sub_clip.crop(x1=x1, y1=0, x2=x1 + new_w, y2=h)
        else:
            # Taller than 9:16 -> crop height
            new_h = int(w / target_aspect)
            y1 = (h - new_h) // 2
            sub_clip = sub_clip.crop(x1=0, y1=y1, x2=w, y2=y1 + new_h)
            
        sub_clip = sub_clip.resize((VIDEO_WIDTH, VIDEO_HEIGHT))
        return sub_clip
