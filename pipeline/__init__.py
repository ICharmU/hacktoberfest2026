"""Brainrot Slop Video Generation Pipeline"""
__version__ = "0.1.0"

# Fix MoviePy 1.0.3 compatibility with Pillow 10+
import PIL.Image
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

