"""Rutas de interpretación de sueños."""
import os
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from models import InterpretTextRequest, InterpretFileRequest
from auth import get_current_user
from database import _get_mongo_collection, _mongo_create_session
from services.interpretation_service import interpret_dream_with_context
from services.title_service import generate_dream_title
from reporte6_BernardoBojalil import (
    interpretar_offline,
    leer_sueno,
    guardar_interpretacion,
    _crear_sesion,
)
from config import FORCE_OFFLINE


router = APIRouter(prefix="", tags=["Dream Interpretation"])


@router.post("/interpret-text")
def interpret_text(req: InterpretTextRequest, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Interpreta un sueño desde texto."""
    texto = (req.texto_sueno or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="texto_sueno requerido")

    user_id = current_user["user_id"]

    # Modo offline forzado
    if bool(req.offline) or FORCE_OFFLINE:
        interpretacion = interpretar_offline(texto, req.contexto_emocional or "")
        ruta_salida: Optional[str] = None
        if req.save:
            base = req.filename if (req.filename and req.filename.strip()) else "sueño_api.txt"
            try:
                ruta_salida = guardar_interpretacion(base, interpretacion)
            except Exception:
                ruta_salida = None
        sesion_id = None
        if _get_mongo_collection() is not None:
            sesion_id = _mongo_create_session(req.filename or "(API)", texto, req.contexto_emocional or "", interpretacion, ruta_salida, user_id, "Sueño interpretado")
        if not sesion_id:
            try:
                sesion_id = _crear_sesion(req.filename or "(API)", texto, req.contexto_emocional or "", interpretacion, ruta_salida)
            except Exception:
                sesion_id = None
        return {
            "interpretacion": interpretacion,
            "ruta_salida": ruta_salida,
            "sesion_id": sesion_id,
            "title": "Sueño interpretado",
            "titulo": "Sueño interpretado",
        }

    # Interpretación con LLM
    interpretacion, error = interpret_dream_with_context(texto, req.contexto_emocional or "", user_id)

    ruta_salida: Optional[str] = None
    if req.save:
        base = req.filename if (req.filename and req.filename.strip()) else "sueño_api.txt"
        try:
            ruta_salida = guardar_interpretacion(base, interpretacion)
        except Exception:
            ruta_salida = None

    # Generar título automáticamente
    titulo, _ = generate_dream_title(texto)
    if not titulo:
        titulo = "Sueño interpretado"
    
    # Guardar sesión
    sesion_id = None
    if _get_mongo_collection() is not None:
        sesion_id = _mongo_create_session(req.filename or "(API)", texto, req.contexto_emocional or "", interpretacion, ruta_salida, user_id, titulo)
    if not sesion_id:
        try:
            sesion_id = _crear_sesion(req.filename or "(API)", texto, req.contexto_emocional or "", interpretacion, ruta_salida)
        except Exception:
            sesion_id = None

    return {
        "interpretacion": interpretacion,
        "ruta_salida": ruta_salida,
        "sesion_id": sesion_id,
        "title": titulo,
        "titulo": titulo,
    }


@router.post("/interpret-file")
def interpret_file(req: InterpretFileRequest, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Interpreta un sueño desde un archivo."""
    if not (req.ruta or "").strip():
        raise HTTPException(status_code=400, detail="ruta requerida")

    user_id = current_user["user_id"]
    
    # Leer archivo
    texto_sueno = leer_sueno(req.ruta)
    if texto_sueno is None:
        raise HTTPException(status_code=400, detail="No se pudo leer el archivo del sueño")
    
    # Interpretar con LLM
    interpretacion, error = interpret_dream_with_context(texto_sueno, req.contexto_emocional or "", user_id)
    
    if not (interpretacion or "").strip():
        raise HTTPException(status_code=502, detail="No se pudo generar la interpretación. Revisa tu API key/red.")
    
    # Guardar archivo
    ruta_salida = guardar_interpretacion(req.ruta, interpretacion)
    
    # Generar título automáticamente
    titulo = None
    try:
        if texto_sueno:
            titulo, _ = generate_dream_title(texto_sueno)
    except Exception:
        pass
    
    if not titulo:
        titulo = "Sueño interpretado"
    
    # Crear sesión con user_id
    sesion_id = None
    if _get_mongo_collection() is not None:
        try:
            mongo_id = _mongo_create_session(req.ruta, texto_sueno, req.contexto_emocional or "", interpretacion, ruta_salida, user_id, titulo)
            if mongo_id:
                sesion_id = mongo_id
        except Exception:
            pass
    else:
        try:
            sesion_id = _crear_sesion(req.ruta, texto_sueno, req.contexto_emocional or "", interpretacion, ruta_salida)
            if sesion_id:
                from reporte6_BernardoBojalil import MEM
                for s in MEM.get("sessions", []):
                    if s.get("id") == sesion_id:
                        s["user_id"] = user_id
                        break
        except Exception:
            pass
    
    return {
        "interpretacion": interpretacion,
        "ruta_salida": ruta_salida,
        "sesion_id": sesion_id,
        "title": titulo,
        "titulo": titulo,
    }
