import base64
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from services.yolo_service import detect_from_base64, detect_from_image_bytes

router = APIRouter(prefix="/recognize", tags=["recognize"])
ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "application/octet-stream"}


class RecognizeRequest(BaseModel):
    image_base64: str  # base64-encoded JPEG/PNG


@router.post("")
async def recognize(req: RecognizeRequest):
    if not req.image_base64:
        raise HTTPException(400, "image_base64 is required")
    try:
        return await detect_from_base64(req.image_base64)
    except Exception as e:
        raise HTTPException(500, f"Recognition failed: {e}")


@router.post("/file")
async def recognize_file(file: UploadFile = File(...)):
    content_type = file.content_type or ""
    if content_type and content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported content type: {content_type}")

    try:
        file_content = await file.read()
        return await detect_from_image_bytes(file_content)
    except Exception as e:
        raise HTTPException(500, f"Recognition failed: {e}")