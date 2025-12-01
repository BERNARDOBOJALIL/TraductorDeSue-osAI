"""Rutas de generación de medios (imágenes, títulos)."""
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from models import GenerateImageRequest, GenerateTitleRequest
from auth import get_current_user
from database import _get_mongo_collection
from services.image_service import generate_dream_image
from services.title_service import generate_dream_title
from config import GEMINI_API_KEY


router = APIRouter(prefix="", tags=["Media Generation"])


@router.post("/generate-image")
def generate_image(req: GenerateImageRequest, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Genera una imagen del sueño usando Gemini 2.5 Flash Image."""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY no configurada.")
    
    descripcion = (req.descripcion_sueno or "").strip()
    if not descripcion:
        raise HTTPException(status_code=400, detail="descripcion_sueno requerida")
    
    # Generar imagen
    image_url, error_msg = generate_dream_image(descripcion, req.estilo or "surrealista y onírico", req.size or "1024x1024")
    
    if not image_url:
        detail_msg = f"No se pudo generar la imagen: {error_msg}" if error_msg else "No se pudo generar la imagen."
        raise HTTPException(status_code=502, detail=detail_msg)
    
    # Actualizar sesión si se proporciona sesion_id
    if req.sesion_id and _get_mongo_collection() is not None:
        try:
            col = _get_mongo_collection()
            user_id = current_user["user_id"]
            col.update_one(
                {"id": req.sesion_id, "user_id": user_id},
                {"$set": {"image_url": image_url, "image_generated_at": datetime.utcnow().isoformat(timespec="seconds")}}
            )
        except Exception:
            pass
    
    return {
        "image_url": image_url,
        "descripcion": descripcion,
        "estilo": req.estilo,
        "size": req.size,
    }


@router.post("/generate-title")
def generate_title(req: GenerateTitleRequest, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Genera un título breve del sueño usando Gemini."""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY no configurada.")
    
    descripcion = (req.descripcion_sueno or "").strip()
    if not descripcion:
        raise HTTPException(status_code=400, detail="descripcion_sueno requerida")
    
    # Generar título
    title, error_msg = generate_dream_title(descripcion)
    
    if not title:
        detail_msg = f"No se pudo generar el título: {error_msg}" if error_msg else "No se pudo generar el título."
        raise HTTPException(status_code=502, detail=detail_msg)
    
    return {
        "title": title,
        "titulo": title,
    }
