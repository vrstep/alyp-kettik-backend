import base64
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from services.ollama_service import recognize_from_image_ollama
from services.openai_service import recognize_from_image

router = APIRouter(prefix="/recognize", tags=["recognize"])
ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "application/octet-stream"}


class RecognizeRequest(BaseModel):
    image_base64: str  # base64-encoded JPEG/PNG


@router.post("")
async def recognize(req: RecognizeRequest):
    if not req.image_base64:
        raise HTTPException(400, "image_base64 is required")
    try:
        return await recognize_from_image_ollama(req.image_base64)
        # return await recognize_from_image(req.image_base64)
    except Exception as e:
        raise HTTPException(500, f"Recognition failed: {e}")


@router.post("/file")
async def recognize_file(file: UploadFile = File(...)):
    content_type = file.content_type or ""
    # Проверяем мягко: либо явный image/*, либо octet-stream (как шлёт Flutter/GetX)
    if content_type and content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported content type: {content_type}")

    try:
        file_content = await file.read()
        image_base64 = base64.b64encode(file_content).decode("utf-8")
        return await recognize_from_image_ollama(image_base64)
        # return await recognize_from_image(image_base64)
    except Exception as e:
        raise HTTPException(500, f"Recognition failed: {e}")