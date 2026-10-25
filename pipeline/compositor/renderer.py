"""
Video Compositor:
Assembles vertical video (1080x1920) with:
1. Subway Surfers sliced background
2. Central foreground topic image with flickering attention border
3. Pointing arrows with permanent border and flashing red fill
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

    def _draw_pointing_arrow_layers(self, card_w: int, card_h: int) -> Tuple[Image.Image, Image.Image]:
        """
        Creates separate layers for pointing arrows:
        1. border_canvas: Permanent non-flickering black border outline with yellow accent.
        2. fill_canvas: High-contrast red fill that flickers on/off.
        """
        canvas_w = VIDEO_WIDTH
        canvas_h = card_h + 100
        border_canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        fill_canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        draw_border = ImageDraw.Draw(border_canvas)
        draw_fill = ImageDraw.Draw(fill_canvas)
        
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

        for poly in [left_poly, right_poly]:
            # Fill layer: solid red fill (flickers)
            draw_fill.polygon(poly, fill=(255, 30, 30, 255))
            
            # Border layer: permanent black stroke + yellow accent line (never flickers)
            draw_border.polygon(poly, fill=None, outline=(0, 0, 0, 255), width=8)
            draw_border.line([(p[0], p[1]) for p in poly[:4]], fill=(255, 230, 0, 255), width=3)
            
        return border_canvas, fill_canvas

    def _draw_pointing_arrows(self, card_w: int, card_h: int) -> Image.Image:
        """
        Creates a combined RGBA image of pointing arrows with both fill and border.
        """
        border_canvas, fill_canvas = self._draw_pointing_arrow_layers(card_w, card_h)
        combined = Image.new("RGBA", border_canvas.size, (0, 0, 0, 0))
        combined.paste(fill_canvas, (0, 0), fill_canvas)
        combined.paste(border_canvas, (0, 0), border_canvas)
        return combined

    def _create_image_card_layers(
        self, image_path: Path, max_w: int = 860, max_h: int = 620, border_pad: int = 12
    ) -> Tuple[Image.Image, Image.Image]:
        """
        Loads the foreground image and returns:
        (card_img, border_img)
        - card_img: Permanent, non-flickering image canvas with padding.
        - border_img: High-visibility glowing double border overlay (Black + Neon Yellow)
                      designed to flicker over the image to draw attention.
        """
        if not image_path.exists():
            blank = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
            return blank, blank.copy()
            
        with Image.open(image_path) as img:
            img = img.convert("RGBA")
            img.thumbnail((max_w - border_pad * 2, max_h - border_pad * 2), Image.Resampling.LANCZOS)
            iw, ih = img.size
            
            cw = iw + border_pad * 2
            ch = ih + border_pad * 2
            
            card_img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            card_img.paste(img, (border_pad, border_pad), img)
            
            border_img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            draw = ImageDraw.Draw(border_img)
            # Glowing double border (Black outer, Neon Yellow inner)
            draw.rectangle([0, 0, cw - 1, ch - 1], outline=(0, 0, 0, 255), width=4)
            draw.rectangle([4, 4, cw - 5, ch - 5], outline=(255, 215, 0, 255), width=6)
            draw.rectangle([10, 10, cw - 11, ch - 11], outline=(0, 0, 0, 255), width=2)
            
            return card_img, border_img

    def _create_image_card(self, image_path: Path, max_w: int = 860, max_h: int = 620) -> Image.Image:
        """
        Loads the foreground image without synthetic borders.
        """
        card_img, _ = self._create_image_card_layers(image_path, max_w=max_w, max_h=max_h)
        return card_img

    def _create_bordered_card(self, image_path: Path, max_w: int = 860, max_h: int = 620) -> Image.Image:
        """
        Combined bordered card (image + static border).
        """
        card_img, border_img = self._create_image_card_layers(image_path, max_w=max_w, max_h=max_h)
        combined = Image.new("RGBA", card_img.size, (0, 0, 0, 0))
        combined.paste(card_img, (0, 0), card_img)
        combined.paste(border_img, (0, 0), border_img)
        return combined

    def _render_karaoke_caption_image(
        self,
        lines: List[str],
        active_line_idx: int,
        active_word_idx: int
    ) -> Image.Image:
        """
        Renders multi-line subtitles with the active spoken word highlighted in high-visibility neon,
        while maintaining rock-solid identical spatial coordinates for all words in the clause.
        """
        canvas_w = VIDEO_WIDTH
        canvas_h = 360
        img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype(str(self.font_path), self.style.get("font_size", 80))
        except Exception:
            font = ImageFont.load_default()

        # Sanitize and uppercase lines
        clean_lines = []
        for line in lines:
            line_str = str(line).replace("\\n", "\n").strip()
            for sub in line_str.split("\n"):
                s = sub.strip()
                if s:
                    clean_lines.append(s.upper() if self.style.get("all_caps", True) else s)

        if not clean_lines:
            return img

        # Dynamic safeguard: measure and auto-scale font if any line exceeds 820px safe width
        max_allowed_w = 820
        line_spacing = 16
        stroke_w = self.style.get("stroke_width", 8)
        stroke_col = self.style.get("stroke_color", "#000000")
        base_text_col = self.style.get("text_color", "#FFFFFF")
        highlight_col = self.style.get("highlight_color", "#FFFF00")

        # Iterate to fit within max_allowed_w if needed
        for _ in range(3):
            space_bbox = draw.textbbox((0, 0), " ", font=font)
            space_w = space_bbox[2] - space_bbox[0]
            parsed_lines = []
            total_h = 0
            max_lw = 0
            for l in clean_lines:
                words = l.split()
                word_boxes = [draw.textbbox((0, 0), w, font=font) for w in words]
                word_widths = [b[2] - b[0] for b in word_boxes]
                lh = max([b[3] - b[1] for b in word_boxes], default=font.size if hasattr(font, 'size') else 60)
                lw = sum(word_widths) + max(0, len(words) - 1) * space_w
                if lw > max_lw:
                    max_lw = lw
                parsed_lines.append((words, word_widths, lw, lh))
                total_h += lh + line_spacing
            total_h -= line_spacing

            if max_lw > max_allowed_w and hasattr(font, "size") and font.size > 40:
                scale = max_allowed_w / max_lw
                new_size = max(40, int(font.size * scale))
                if new_size < font.size:
                    try:
                        font = ImageFont.truetype(str(self.font_path), new_size)
                        continue
                    except Exception:
                        break
            break

        start_y = max(20, (canvas_h - total_h) // 2)
        curr_y = start_y

        for l_idx, (words, word_widths, lw, lh) in enumerate(parsed_lines):
            cur_x = (canvas_w - lw) // 2
            for w_idx, (w, ww) in enumerate(zip(words, word_widths)):
                is_active = (l_idx == active_line_idx and w_idx == active_word_idx)
                fill_color = highlight_col if is_active else base_text_col
                current_stroke_w = (stroke_w + 2) if is_active else stroke_w

                # Drop shadow
                draw.text(
                    (cur_x + 6, curr_y + 6),
                    w,
                    font=font,
                    fill=(0, 0, 0, 200),
                    stroke_width=current_stroke_w,
                    stroke_fill=(0, 0, 0, 255)
                )
                # Main stroked text
                draw.text(
                    (cur_x, curr_y),
                    w,
                    font=font,
                    fill=fill_color,
                    stroke_width=current_stroke_w,
                    stroke_fill=stroke_col
                )
                cur_x += ww + space_w
            curr_y += lh + line_spacing

        return img

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
            
            # A. Image Card (Permanent image + Flickering attention border)
            card_pil, border_pil = self._create_image_card_layers(image_path)
            cw, ch = card_pil.size
            card_pos = ("center", card_center_y - ch // 2)
            
            # Permanent image clip (does not flicker)
            card_clip = self._pil_to_clip(card_pil, beat_dur, beat_start, card_pos, flash=False)
            clips_to_composite.append(card_clip)
            
            # Flickering glowing border clip (draws visual attention to the card)
            border_clip = self._pil_to_clip(border_pil, beat_dur, beat_start, card_pos, flash=True)
            clips_to_composite.append(border_clip)

            # B. Pointing Arrows (Permanent outline border + Flickering red fill)
            arrow_border_pil, arrow_fill_pil = self._draw_pointing_arrow_layers(cw, ch)
            arrows_pos = ("center", card_center_y - ch // 2 - 50)
            
            # Flickering red fill clip (only red fill turns on/off)
            arrow_fill_clip = self._pil_to_clip(arrow_fill_pil, beat_dur, beat_start, arrows_pos, flash=True)
            clips_to_composite.append(arrow_fill_clip)
            
            # Permanent non-flickering arrow border clip
            arrow_border_clip = self._pil_to_clip(arrow_border_pil, beat_dur, beat_start, arrows_pos, flash=False)
            clips_to_composite.append(arrow_border_clip)

        # 2. Speech-Synchronized Karaoke Subtitles (Full sentences/clauses with active word highlight)
        print(f"[compositor] Rendering {len(voice_result.caption_cues)} speech-synchronized caption overlays...", flush=True)
        for cue in voice_result.caption_cues:
            cue_start = cue.start_seconds
            cue_end = cue.end_seconds
            cue_dur = max(0.08, cue_end - cue_start)
            
            if cue.lines:
                caption_pil = self._render_karaoke_caption_image(
                    lines=cue.lines,
                    active_line_idx=cue.active_line_index,
                    active_word_idx=cue.active_word_index
                )
            else:
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
