"""
YOLO11s product detection service.

The model runs on the server. The phone uploads an image,
this service runs inference and returns detected products
matched against the database.
"""

import io
import os
import logging
from collections import Counter

import cv2
import numpy as np
from ultralytics import YOLO

from database import get_product_by_yolo_class

logger = logging.getLogger(__name__)

# ── Model loading ─────────────────────────────────────────────────────────────
_MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "my_model.pt")
_model: YOLO | None = None
_device: str = "cpu"

# YOLO class name → human-friendly DB product name mapping
YOLO_CLASS_TO_PRODUCT = {
    "bon_aqua_1l":           "BonAqua 1L",
    "coca_cola_1l":          "Coca-Cola 1L",
    "eggs_kazger_10p":       "Яйца Казгер 10 шт",
    "kublei_325g":           "Кублей 325г",
    "maheev_shashlyk_500g":  "Махеев Шашлык 500г",
    "mayo_ryaba_364ml":      "Майонез Ряба 364мл",
    "milk_petropavlovsk_3.2":"Молоко Петропавловск 3.2%",
    "milka_almond_80g":      "Milka Almond 80g",
    "piala_25b":             "Piala 25 пак",
    "red_bull_250ml":        "Red Bull 250мл",
    "twix_55g":              "Twix 55г",
}

CONFIDENCE_THRESHOLD = 0.5


def get_model() -> YOLO:
    """Lazy-load the YOLO model (loaded once, reused for all requests)."""
    global _model, _device
    if _model is None:
        import torch

        if not os.path.exists(_MODEL_PATH):
            raise FileNotFoundError(f"YOLO model not found at {_MODEL_PATH}")
        _device = "cuda:0" if torch.cuda.is_available() else "cpu"
        print(f"[YOLO] Loading model from {_MODEL_PATH} on {_device} ...")
        _model = YOLO(_MODEL_PATH, task="detect")
        print(f"[YOLO] Model loaded. Classes: {_model.names}")
    return _model


async def detect_from_image_bytes(image_bytes: bytes) -> dict:
    """
    Run YOLO detection on raw image bytes.

    Returns the same format the frontend already expects:
    {
      "recognized_items": [
        {"product_id": 1, "name": "Coca-Cola 1L", "price": 450, "quantity": 1, "confidence": 0.92}
      ],
      "unrecognized": [],
      "total": 450.0
    }
    """
    # Decode image bytes → numpy array (OpenCV)
    nparr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Could not decode image")

    # Run YOLO inference
    model = get_model()
    results = model(frame, verbose=False, device=_device)
    detections = results[0].boxes

    # Count detections per class (with max confidence per class)
    class_counts: Counter = Counter()
    class_confidences: dict[str, float] = {}

    for i in range(len(detections)):
        conf = detections[i].conf.item()
        if conf < CONFIDENCE_THRESHOLD:
            continue

        class_idx = int(detections[i].cls.item())
        class_name = model.names[class_idx]

        class_counts[class_name] += 1
        # Keep the highest confidence for each class
        if class_name not in class_confidences or conf > class_confidences[class_name]:
            class_confidences[class_name] = conf

    # Match detections against the database
    recognized_items = []
    unrecognized = []
    total = 0.0

    for class_name, quantity in class_counts.items():
        product = await get_product_by_yolo_class(class_name)
        if product:
            price = float(product["price"])
            recognized_items.append({
                "product_id": product["id"],
                "name": product["name"],
                "price": price,
                "quantity": quantity,
                "confidence": round(class_confidences[class_name], 2),
            })
            total += price * quantity
        else:
            # Product detected by YOLO but not found in DB
            friendly_name = YOLO_CLASS_TO_PRODUCT.get(class_name, class_name)
            unrecognized.append(friendly_name)
            logger.warning("YOLO detected '%s' but no matching product in DB", class_name)

    return {
        "recognized_items": recognized_items,
        "unrecognized": unrecognized,
        "total": round(total, 2),
    }


async def detect_from_base64(image_base64: str) -> dict:
    """Run YOLO detection on a base64-encoded image string."""
    import base64
    image_bytes = base64.b64decode(image_base64)
    return await detect_from_image_bytes(image_bytes)
