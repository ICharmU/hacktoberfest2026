"""
Video Compositor:
Assembles vertical video (1080x1920) with:
1. Subway Surfers sliced background
2. Central foreground topic image with border
3. Flashing pointing arrows (off for 0.1s every 0.5s)
4. Stylized auto-wrapped subtitles (proper line breaks, no literal '\\n')
5. Edge-TTS narration audio
"""

import math
from pathlib import Path
from typing import List, Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    CompositeVideoClip
)
from pipeline.observability import observe

from pipeline.config import (
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
    VIDEO_FPS,
    ARROW_CYCLE_SECONDS,
    ARROW_OFF_DURATION,
    DEFAULT_FONT_FILE,
    load_caption_style
)
from pipeline.tts.voice_actor import VoiceResult, BeatTiming

class VideoCompositor:
    def __init__(self, font_path: Path = DEFAULT_FONT_FILE):
        self.font_path = font_path
        self.style = load_caption_style("brainrot_viral")

    def _draw_pointing_arrows(self, card_w: int, card_h: int) -> Image.Image:
        """
        Creates an RGBA image containing high-contrast red/yellow pointing arrows
        pointing at the left and right borders of the central card.
        """
        canvas_w = VIDEO_WIDTH
        canvas_h = card_h + 100
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        
        # Center coordinates of the image card on this canvas
        cx = canvas_w // 2
        cy = canvas_h // 2
        card_half_w = card_w // 2
        
        arrow_len = 110
        arrow_head = 45
        
        # Left arrow (pointing right -> [ CARD ])
        lx_start = cx - card_half_w - arrow_len - 30
        lx_tip = cx - card_half_w - 20
        # Right arrow (pointing left [ CARD ] <- )
        rx_start = cx + card_half_w + arrow_len + 30
        rx_tip = cx + card_half_w + 20

        # Draw left arrow
        left_poly = [
            (lx_start, cy - 18),
            (lx_tip - arrow_head, cy - 18),
            (lx_tip - arrow_head, cy - 38),
            (lx_tip, cy),
            (lx_tip - arrow_head, cy + 38),
            (lx_tip - arrow_head, cy + 18),
            (lx_start, cy + 18)
        ]
        
        # Draw right arrow
        right_poly = [
            (rx_start, cy - 18),
            (rx_tip + arrow_head, cy - 18),
            (rx_tip + arrow_head, cy - 38),
            (rx_tip, cy),
            (rx_tip + arrow_head, cy + 38),
            (rx_tip + arrow_head, cy + 18),
            (rx_start, cy + 18)
        ]

        # Black outline / stroke for arrows
        for poly in [left_poly, right_poly]:
            draw.polygon(poly, fill=(255, 30, 30, 255), outline=(0, 0, 0, 255), width=8)
            # Add yellow inner accent
            draw.line([(p[0], p[1]) for p in poly[:4]], fill=(255, 230, 0, 255), width=3)
            
        return canvas

    def _create_bordered_card(self, image_path: Path, max_w: int = 860, max_h: int = 620) -> Image.Image:
        """
        Loads the foreground image, fits inside max dimensions, and adds a thick high-visibility border.
        """
        if not image_path.exists():
            # Blank transparent card
            return Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
            
        with Image.open(image_path) as img:
            img = img.convert("RGBA")
            img.thumbnail((max_w - 24, max_h - 24), Image.Resampling.LANCZOS)
            iw, ih = img.size
            
            # Canvas with border
            border_pad = 12
            cw = iw + border_pad * 2
            ch = ih + border_pad * 2
            
            card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            draw = ImageDraw.Draw(card)
            
            # Glowing double border (Black outer, Neon Yellow inner)
            draw.rectangle([0, 0, cw, ch], fill=(0, 0, 0, 255))
            draw.rectangle([4, 4, cw - 4, ch - 4], fill=(255, 215, 0, 255))
            draw.rectangle([10, 10, cw - 10, ch - 10], fill=(0, 0, 0, 255))
            
            card.paste(img, (border_pad, border_pad), img)
            return card

    def _render_caption_image(self, lines: List[str]) -> Image.Image:
        """
        Renders multi-line subtitles onto a transparent image with thick stroke and shadow.
        Explicitly displays distinct lines rather than escaped 'n'.
        """
        canvas_w = VIDEO_WIDTH
        canvas_h = 360
        img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype(str(self.font_path), self.style.get("font_size", 72))
        except Exception:
            font = ImageFont.load_default()

        # Sanitize lines: strip, uppercase if styled, eliminate any literal \n
        clean_lines = []
        for line in lines:
            line_str = str(line).replace("\\n", "\n")
            for sub in line_str.split("\n"):
                s = sub.strip()
                if s:
                    clean_lines.append(s.upper() if self.style.get("all_caps", True) else s)
                    
        if not clean_lines:
            return img

        # Compute total height
        line_spacing = 16
        line_metrics = []
        total_h = 0
        for l in clean_lines:
            bbox = draw.textbbox((0, 0), l, font=font)
            lw = bbox[2] - bbox[0]
            lh = bbox[3] - bbox[1]
            line_metrics.append((lw, lh))
            total_h += lh + line_spacing
        total_h -= line_spacing

        start_y = max(20, (canvas_h - total_h) // 2)
        curr_y = start_y
        
        stroke_w = self.style.get("stroke_width", 8)
        stroke_col = self.style.get("stroke_color", "#000000")
        text_col = self.style.get("text_color", "#FFFF00")
        
        for (line_text, (lw, lh)) in zip(clean_lines, line_metrics):
            line_x = (canvas_w - lw) // 2
            
            # Drop shadow
            draw.text(
                (line_x + 6, curr_y + 6),
                line_text,
                font=font,
                fill=(0, 0, 0, 200),
                stroke_width=stroke_w,
                stroke_fill=(0, 0, 0, 255)
            )
            # Main stroked text
            draw.text(
                (line_x, curr_y),
                line_text,
                font=font,
                fill=text_col,
                stroke_width=stroke_w,
                stroke_fill=stroke_col
            )
            curr_y += lh + line_spacing

        return img

    def _pil_to_clip(self, pil_img: Image.Image, duration: float, start: float, pos, flash: bool = False) -> ImageClip:
        """
        Converts a PIL RGBA image into a MoviePy ImageClip with proper alpha masking,
        and optional flashing off for 0.1s every 0.5s.
        """
        arr = np.array(pil_img.convert("RGBA"), dtype=np.uint8)
        rgb = arr[:, :, :3]
        alpha = arr[:, :, 3].astype(float) / 255.0

        cycle = ARROW_CYCLE_SECONDS
        off_dur = ARROW_OFF_DURATION
        on_dur = cycle - off_dur  # 0.4s

        if flash:
            # Mask function: alpha if on, 0 if off
            def flash_mask(gf, t):
                base_m = gf(t)
                return base_m if ((t % cycle) < on_dur) else np.zeros_like(base_m)
            mask_clip = ImageClip(alpha, ismask=True).set_start(start).set_duration(duration).fl(flash_mask)
        else:
            mask_clip = ImageClip(alpha, ismask=True).set_start(start).set_duration(duration)

        clip = (
            ImageClip(rgb)
            .set_start(start)
            .set_duration(duration)
            .set_mask(mask_clip)
            .set_position(pos)
        )
        return clip

    @observe(name="video_compositor")
    def compose(
        self,
        gameplay_clip: VideoFileClip,
        voice_result: VoiceResult,
        beat_images: List[Path],
        output_video_path: Path
    ) -> Path:
        print("[compositor] Building video layers...", flush=True)
        output_video_path.parent.mkdir(parents=True, exist_ok=True)
        
        total_duration = voice_result.duration_seconds
        
        # Audio track
        audio_clip = AudioFileClip(voice_result.audio_file)
        background = gameplay_clip.subclip(0, total_duration).set_audio(audio_clip)

        clips_to_composite = [background]

        # Card center position (Upper third for TikTok/Shorts: y = ~480)
        card_center_y = 520
        caption_pos_y = 1220

        # 1. Image Cards and Flashing Pointing Arrows (per beat)
        for i, beat in enumerate(voice_result.beat_timings):
            beat_start = beat.start_seconds
            beat_end = beat.end_seconds
            beat_dur = max(0.2, beat_end - beat_start)
            
            image_path = beat_images[i] if i < len(beat_images) else beat_images[0]
            
            # A. Image Card
            card_pil = self._create_bordered_card(image_path)
            cw, ch = card_pil.size
            card_pos = ("center", card_center_y - ch // 2)
            card_clip = self._pil_to_clip(card_pil, beat_dur, beat_start, card_pos, flash=False)
            clips_to_composite.append(card_clip)

            # B. Flashing Pointing Arrows
            arrows_pil = self._draw_pointing_arrows(cw, ch)
            arrows_pos = ("center", card_center_y - ch // 2 - 50)
            arrow_clip = self._pil_to_clip(arrows_pil, beat_dur, beat_start, arrows_pos, flash=True)
            clips_to_composite.append(arrow_clip)

        # 2. Verbatim Rapid-Fire Subtitles (1-3 words per cue, exact speech sync)
        print(f"[compositor] Rendering {len(voice_result.caption_cues)} verbatim caption overlays...", flush=True)
        for cue in voice_result.caption_cues:
            cue_start = cue.start_seconds
            cue_end = cue.end_seconds
            cue_dur = max(0.12, cue_end - cue_start)
            
            # Render the exact spoken words in bold high-contrast font
            caption_pil = self._render_caption_image([cue.text])
            caption_pos = ("center", caption_pos_y)
            caption_clip = self._pil_to_clip(caption_pil, cue_dur, cue_start, caption_pos, flash=False)
            clips_to_composite.append(caption_clip)

        # Assemble and render
        final_video = CompositeVideoClip(clips_to_composite, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
        final_video = final_video.set_duration(total_duration)

        print(f"[compositor] Rendering final MP4 to: {output_video_path}...", flush=True)
        final_video.write_videofile(
            str(output_video_path),
            fps=VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            preset="fast",
            threads=4,
            logger="bar"
        )
        print(f"[compositor] Video successfully rendered: {output_video_path}", flush=True)
        return output_video_path
