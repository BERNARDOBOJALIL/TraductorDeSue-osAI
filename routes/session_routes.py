"""Rutas de gestión de sesiones."""
import os
import json
import concurrent.futures
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from models import FollowupRequest
from auth import get_current_user
from database import (
    _get_mongo_collection,
    _mongo_list_sessions,
    _mongo_get_session,
    _mongo_add_followup,
    _mongo_delete_session,
)
from reporte6_BernardoBojalil import (
    _buscar_sesion,
    _agregar_followup,
    _resumen_ultimas_sesiones,
    construir_cadena_followup,
)
from config import LLM_TIMEOUT_SECS


router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.get("")
def list_sessions(limit: int = 5, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Lista las sesiones del usuario actual."""
    try:
        n = max(1, min(50, int(limit)))
    except Exception:
        n = 5
    user_id = current_user["user_id"]
    
    docs = _mongo_list_sessions(n, user_id)
    if docs is not None:
        return {"sessions": docs}
    return {"sessions": _resumen_ultimas_sesiones(n)}


@router.get("/{sesion_id}")
def get_session(sesion_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Obtiene una sesión específica."""
    user_id = current_user["user_id"]
    
    s = _mongo_get_session(sesion_id, user_id) if _get_mongo_collection() is not None else None
    if not s:
        s = _buscar_sesion(sesion_id)
    if not s:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    
    # Verificar que la sesión pertenezca al usuario
    if s.get("user_id") and s.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="No tienes permiso para acceder a esta sesión")
    return s


@router.delete("/{sesion_id}")
def delete_session(sesion_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Elimina una sesión del usuario actual."""
    user_id = current_user["user_id"]
    
    # Intentar eliminar de MongoDB
    if _get_mongo_collection() is not None:
        try:
            deleted_count = _mongo_delete_session(sesion_id, user_id)
            
            if deleted_count > 0:
                return {
                    "message": "Sesión eliminada exitosamente",
                    "sesion_id": sesion_id,
                    "deleted": True
                }
            else:
                raise HTTPException(status_code=404, detail="Sesión no encontrada o no tienes permiso para eliminarla")
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error eliminando sesión de MongoDB: {e}")
            raise HTTPException(status_code=500, detail="Error al eliminar la sesión")
    
    # Fallback a archivo JSON local
    try:
        memoria_path = "memoria_agente.json"
        
        if not os.path.exists(memoria_path):
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        
        with open(memoria_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        sesiones = data.get("sesiones", [])
        sesion_encontrada = False
        nuevas_sesiones = []
        
        for s in sesiones:
            if s.get("id") == sesion_id:
                if s.get("user_id") and s.get("user_id") != user_id:
                    raise HTTPException(status_code=403, detail="No tienes permiso para eliminar esta sesión")
                sesion_encontrada = True
            else:
                nuevas_sesiones.append(s)
        
        if not sesion_encontrada:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        
        data["sesiones"] = nuevas_sesiones
        with open(memoria_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return {
            "message": "Sesión eliminada exitosamente",
            "sesion_id": sesion_id,
            "deleted": True
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error eliminando sesión del archivo JSON: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar la sesión")


@router.post("/{sesion_id}/followup")
def followup_handler(sesion_id: str, req: FollowupRequest, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Realiza una pregunta de seguimiento sobre una sesión."""
    user_id = current_user["user_id"]
    s = _mongo_get_session(sesion_id, user_id) if _get_mongo_collection() is not None else None
    if not s:
        s = _buscar_sesion(sesion_id)
    if not s:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    
    # Verificar permisos
    if s.get("user_id") and s.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="No tienes permiso para acceder a esta sesión")
    
    pregunta = (req.pregunta or "").strip()
    if not pregunta:
        raise HTTPException(status_code=400, detail="pregunta requerida")

    chain_fu = construir_cadena_followup()
    if chain_fu is None:
        raise HTTPException(status_code=503, detail="Cadena de follow-up no disponible (revisa API/red)")

    try:
        historial_txt = ""
        try:
            from reporte6_BernardoBojalil import _historial_followup_texto
            historial_txt = _historial_followup_texto(s or {})
        except Exception:
            historial_txt = ""

        payload_fu = {
            "texto_sueno": s.get("texto_sueno", ""),
            "contexto_emocional": s.get("contexto_emocional", ""),
            "interpretacion_previa": s.get("interpretacion", ""),
            "pregunta": pregunta,
            "historial": historial_txt,
        }

        def _invoke_fu():
            return chain_fu.invoke(payload_fu)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_invoke_fu)
            resp = fut.result(timeout=LLM_TIMEOUT_SECS)
        
        if not isinstance(resp, str):
            resp = getattr(resp, "content", None) or str(resp)
        respuesta = str(resp)
    except concurrent.futures.TimeoutError:
        raise HTTPException(status_code=504, detail="Tiempo de espera agotado para follow-up")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No fue posible responder el seguimiento: {e}")

    # Persistir follow-up
    if _get_mongo_collection() is not None:
        ok = _mongo_add_followup(sesion_id, pregunta, respuesta)
        if not ok:
            try:
                _agregar_followup(sesion_id, pregunta, respuesta)
            except Exception:
                pass
    else:
        try:
            _agregar_followup(sesion_id, pregunta, respuesta)
        except Exception:
            pass

    return {"respuesta": respuesta}
