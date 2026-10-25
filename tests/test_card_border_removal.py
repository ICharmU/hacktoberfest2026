"""
Unit test for compositor image card flickering border and arrow permanent border layers.
Verifies that:
1. Arrow border layer has permanent black outline & yellow accent without red fill.
2. Arrow fill layer has red fill without outline, ready to flicker on/off.
3. Image card layers produce permanent image card + separate flickering border overlay.
DOES NOT generate any video clips.
"""

from pathlib import Path
import tempfile
import numpy as np
from PIL import Image
from pipeline.compositor.renderer import VideoCompositor

def test_arrow_and_card_layers():
    compositor = VideoCompositor()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "sample_beat.png"
        sample_img = Image.new("RGBA", (400, 300), (0, 200, 255, 255))
        sample_img.save(tmp_path, "PNG")

        # 1. Test _create_image_card_layers
        card_img, border_img = compositor._create_image_card_layers(tmp_path, max_w=860, max_h=620)
        
        cw, ch = card_img.size
        assert border_img.size == (cw, ch)

        card_arr = np.array(card_img)
        border_arr = np.array(border_img)

        # A: card_img has image content and no synthetic neon yellow border
        yellow_in_card = (card_arr[:, :, 0] == 255) & (card_arr[:, :, 1] == 215) & (card_arr[:, :, 2] == 0)
        assert not np.any(yellow_in_card), "card_img should not contain yellow border!"

        # B: border_img has glowing yellow border pixels
        yellow_in_border = (border_arr[:, :, 0] == 255) & (border_arr[:, :, 1] == 215) & (border_arr[:, :, 2] == 0)
        assert np.any(yellow_in_border), "border_img must contain glowing yellow border pixels!"

        # C: border_img interior (where image is placed) must be transparent
        # Padding is 12, so center area should have alpha == 0
        center_alpha = border_arr[30:ch - 30, 30:cw - 30, 3]
        assert np.all(center_alpha == 0), "border_img interior must be transparent!"

        # 2. Test _draw_pointing_arrow_layers
        arrow_border, arrow_fill = compositor._draw_pointing_arrow_layers(cw, ch)
        assert arrow_border.size == (1080, ch + 100)
        assert arrow_fill.size == (1080, ch + 100)

        border_arr = np.array(arrow_border)
        fill_arr = np.array(arrow_fill)

        # Arrow border has visible stroke
        border_visible = border_arr[:, :, 3] > 0
        assert np.any(border_visible), "Arrow border layer must have visible pixels!"
        
        # Arrow border has black outline
        black_pixels = border_visible & (border_arr[:, :, 0] == 0) & (border_arr[:, :, 1] == 0) & (border_arr[:, :, 2] == 0)
        assert np.any(black_pixels), "Arrow border layer must have black outline!"
        
        # Arrow border has yellow accent
        yellow_accent = border_visible & (border_arr[:, :, 0] == 255) & (border_arr[:, :, 1] == 230) & (border_arr[:, :, 2] == 0)
        assert np.any(yellow_accent), "Arrow border layer must have yellow accent line!"

        # Arrow fill layer has red fill
        fill_visible = fill_arr[:, :, 3] > 0
        assert np.any(fill_visible), "Arrow fill layer must have visible pixels!"
        red_pixels = fill_visible & (fill_arr[:, :, 0] == 255) & (fill_arr[:, :, 1] == 30) & (fill_arr[:, :, 2] == 30)
        assert np.any(red_pixels), "Arrow fill layer must have red fill pixels!"

        # Arrow fill layer must NOT have black border
        fill_black = fill_visible & (fill_arr[:, :, 0] == 0) & (fill_arr[:, :, 1] == 0) & (fill_arr[:, :, 2] == 0)
        assert not np.any(fill_black), "Arrow fill layer must not have black outline!"

        # 3. Test backward compatibility helpers
        combined_arrows = compositor._draw_pointing_arrows(cw, ch)
        assert combined_arrows.size == (1080, ch + 100)

        clean_card = compositor._create_image_card(tmp_path)
        assert clean_card.size == (cw, ch)

        bordered_card = compositor._create_bordered_card(tmp_path)
        assert bordered_card.size == (cw, ch)

        print("[OK] All arrow layers and flickering card border assertions passed!")

if __name__ == "__main__":
    test_arrow_and_card_layers()
