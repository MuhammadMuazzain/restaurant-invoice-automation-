from __future__ import annotations

import base64
from io import BytesIO

from pdf2image import convert_from_path


def pdf_to_base64_png_images(pdf_path: str, *, max_pages: int | None = 3) -> list[str]:
    imgs = convert_from_path(pdf_path, fmt="png")
    if max_pages is not None:
        imgs = imgs[:max_pages]

    base64_imgs: list[str] = []
    for image in imgs:
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        base64_imgs.append(img_str)

    return base64_imgs

