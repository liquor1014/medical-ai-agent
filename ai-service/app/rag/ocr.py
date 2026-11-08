"""图片 OCR：按可用引擎依次尝试，返回 (文本, 引擎名)。"""
from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


def _image_for_ocr(data: bytes):
    from PIL import Image  # type: ignore

    return Image.open(io.BytesIO(data)).convert("RGB")


def ocr_image(data: bytes, file_name: str = "") -> tuple[str, str]:
    """尝试 tesseract / PaddleOCR，均不可用时返回 ("", "none")。"""
    # 1) pytesseract（需要本机安装 tesseract 可执行文件）
    try:
        import pytesseract  # type: ignore

        image = _image_for_ocr(data)
        text = pytesseract.image_to_string(image, lang="chi_sim+eng").strip()
        if text:
            logger.info("OCR(tesseract) 成功: %s, %d 字", file_name, len(text))
            return text, "tesseract"
    except Exception as e:
        logger.debug("tesseract OCR 不可用: %s", e)

    # 2) PaddleOCR（依赖较重，按需启用）
    try:
        from paddleocr import PaddleOCR  # type: ignore

        engine = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        result = engine.ocr(_to_numpy(data), cls=True)
        lines = [
            line[1][0]
            for page in (result or [])
            for line in (page or [])
            if line and len(line) > 1 and line[1]
        ]
        text = "\n".join(lines).strip()
        if text:
            logger.info("OCR(PaddleOCR) 成功: %s, %d 字", file_name, len(text))
            return text, "paddleocr"
    except Exception as e:
        logger.debug("PaddleOCR 不可用: %s", e)

    return "", "none"


def _to_numpy(data: bytes):
    import numpy as np  # type: ignore
    from PIL import Image  # type: ignore

    return np.array(Image.open(io.BytesIO(data)).convert("RGB"))


def image_metadata(data: bytes) -> dict:
    """读取图片宽高/格式等基础信息。"""
    try:
        from PIL import Image  # type: ignore

        with Image.open(io.BytesIO(data)) as img:
            return {"width": img.width, "height": img.height, "format": img.format}
    except Exception:
        return {}
