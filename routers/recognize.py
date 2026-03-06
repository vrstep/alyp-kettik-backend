from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
# from services.openai_service import recognize_from_image

import base64

from services.ollama_service import recognize_from_image_ollama

router = APIRouter(prefix="/recognize", tags=["recognize"])


class RecognizeRequest(BaseModel):
    image_base64: str  # base64-encoded JPEG/PNG


@router.post("")
async def recognize(req: RecognizeRequest):
    if not req.image_base64:
        raise HTTPException(400, "image_base64 is required")
    try:
        result = await recognize_from_image_ollama(req.image_base64)
        return result
    except Exception as e:
        raise HTTPException(500, f"Recognition failed: {e}")


@router.post("/file")
async def recognize_file(file: UploadFile = File(...)):
    """
    Recognize products from an uploaded image file.
    
    Accepts JPEG/PNG files directly and converts them to base64 internally.
    This endpoint is more convenient for Swagger UI and file uploads.
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Only image files are allowed (JPEG, PNG)")
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Convert to base64 (without data:image/...;base64, prefix)
        image_base64 = base64.b64encode(file_content).decode("utf-8")
        
        # Call the existing recognition function
        result = await recognize_from_image_ollama(image_base64)
        return result
    except Exception as e:
        raise HTTPException(500, f"Recognition failed: {e}")