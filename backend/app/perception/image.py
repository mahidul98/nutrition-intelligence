import io

from PIL import Image, ImageOps

MAX_SIDE = 1280


def prepare_image(raw: bytes) -> bytes:
    """Fix orientation, downscale, and re-encode as JPEG (drops EXIF/GPS metadata)."""
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88)
    return out.getvalue()