"""
Unit test for compositor image card border removal.
Verifies that foreground image cards are rendered borderless without synthetic yellow/black rectangles.
DOES NOT generate any video clips.
"""

from pathlib import Path
import tempfile
import numpy as np
from PIL import Image
from pipeline.compositor.renderer import VideoCompositor

def test_image_card_borderless():
    compositor = VideoCompositor()

    # Create a temporary solid cyan image of size 400x300
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "sample_beat.png"
        sample_img = Image.new("RGBA", (400, 300), (0, 200, 255, 255))
        sample_img.save(tmp_path, "PNG")

        # 1. Test _create_image_card
        card = compositor._create_image_card(tmp_path, max_w=860, max_h=620)
        
        # Dimensions must match image without artificial padding (e.g. not 400 + 24, 300 + 24)
        assert card.size == (400, 300), f"Expected (400, 300), got {card.size}"

        arr = np.array(card)
        # Verify neon yellow border color (255, 215, 0) is not present
        yellow_mask = (arr[:, :, 0] == 255) & (arr[:, :, 1] == 215) & (arr[:, :, 2] == 0)
        assert not np.any(yellow_mask), "Found synthetic neon yellow border pixels in card!"

        # Verify all pixels match original image color
        assert np.all(arr[:, :, 0] == 0)
        assert np.all(arr[:, :, 1] == 200)
        assert np.all(arr[:, :, 2] == 255)

        # 2. Test backward-compatible alias _create_bordered_card
        legacy_card = compositor._create_bordered_card(tmp_path, max_w=860, max_h=620)
        assert legacy_card.size == (400, 300)
        assert np.array_equal(arr, np.array(legacy_card))

        # 3. Test non-existent image returns transparent blank card
        missing_path = Path(tmp_dir) / "does_not_exist.png"
        blank_card = compositor._create_image_card(missing_path, max_w=860, max_h=620)
        assert blank_card.size == (860, 620)
        blank_arr = np.array(blank_card)
        assert np.all(blank_arr[:, :, 3] == 0), "Expected transparent card for nonexistent image"

        # 4. Test _draw_pointing_arrows works with card size
        arrows_img = compositor._draw_pointing_arrows(card.size[0], card.size[1])
        assert arrows_img.size[0] == 1080
        assert arrows_img.size[1] == 300 + 100

        print("[OK] All image card border removal assertions passed!")

if __name__ == "__main__":
    test_image_card_borderless()
