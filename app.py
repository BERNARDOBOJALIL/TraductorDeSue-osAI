from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, AliasChoices
from typing import Optional, List, Dict, Any
import os
from uuid import uuid4

# Reuse existing project logic
from reporte6_BernardoBojalil import (
    construir_cadena_interprete,
    construir_cadena_followup,
    interpretar_y_guardar,
    interpretar_offline,
    _memoria_json_compacta,
    _crear_sesion,
    _buscar_sesion,
    _agregar_followup,
    _resumen_ultimas_sesiones,
)

app = FastAPI(title="Traductor de Sueños API", version="1.0.0")


class InterpretTextRequest(BaseModel):
    # Acepta tanto "texto_sueno" como "texto_sueño" en el body
    texto_sueno: str = Field(
        ...,
        description="Descripción del sueño en texto plano",
        validation_alias=AliasChoices("texto_sueno", "texto_sueño"),
    )
    contexto_emocional: Optional[str] = Field("", description="Contexto emocional opcional")
    save: bool = Field(False, description="Si True, guarda interpretación en archivo")
    filename: Optional[str] = Field(
        None,
        description="Nombre base del archivo del sueño para nombrar la salida (solo si save=True)",
    )
    offline: Optional[bool] = Field(False, description="Si true, fuerza modo offline sin LLM")

    model_config = {
        "populate_by_name": True,
        "str_strip_whitespace": True,
    }


class InterpretFileRequest(BaseModel):
    ruta: str = Field(..., description="Ruta del archivo con el sueño (UTF-8)")
    contexto_emocional: Optional[str] = Field("", description="Contexto emocional opcional")


class FollowupRequest(BaseModel):
    pregunta: str = Field(..., description="Pregunta de seguimiento")


# --- MongoDB (opcional) ---
_MONGO_OK = False
try:
    from pymongo import MongoClient
    _MONGO_OK = True
except Exception:
    _MONGO_OK = False


def _get_mongo_collection():
    """Devuelve la colección de Mongo si MONGODB_URI está definido y pymongo está disponible; si no, None."""
    if not _MONGO_OK:
        return None
    uri = os.getenv("MONGODB_URI")
    if not uri:
        return None
    db_name = os.getenv("MONGODB_DB", "ai_dreams")
    coll_name = os.getenv("MONGODB_COLLECTION", "sessions")
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        db = client[db_name]
        return db[coll_name]
    except Exception:
        return None


def _mongo_create_session(ruta_sueno: str, texto_sueno: str, contexto: str, interpretacion: str, ruta_salida: Optional[str]):
    col = _get_mongo_collection()
    if col is None:
        return None
    ses_id = str(uuid4())
    # obtener resumen como en el archivo original
    try:
        from reporte6_BernardoBojalil import extraer_bloque_por_titulo, resumen_corto

        resumen_interpretacion = extraer_bloque_por_titulo(interpretacion, "Interpretación general") or resumen_corto(interpretacion, 240)
    except Exception:
        resumen_interpretacion = None
    doc = {
        "id": ses_id,
        "created_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "archivo": ruta_sueno,
        "output_file": ruta_salida,
        "contexto_emocional": contexto,
        "texto_sueno": texto_sueno,
        "interpretacion": interpretacion,
        "interpretacion_resumen": (resumen_interpretacion or "").strip(),
        "followups": [],
    }
    try:
        col.insert_one(doc)
        return ses_id
    except Exception:
        return None


def _mongo_get_session(sesion_id: str):
    col = _get_mongo_collection()
    if col is None:
        return None
    try:
        doc = col.find_one({"id": sesion_id}, {"_id": 0})
        return doc
    except Exception:
        return None


def _mongo_list_sessions(limit: int = 5):
    col = _get_mongo_collection()
    if col is None:
        return None
    try:
        cur = col.find({}, {"_id": 0, "id": 1, "created_at": 1, "archivo": 1, "interpretacion_resumen": 1, "output_file": 1}).sort("created_at", -1).limit(max(1, limit))
        return list(cur)
    except Exception:
        return None


def _mongo_add_followup(sesion_id: str, pregunta: str, respuesta: str):
    col = _get_mongo_collection()
    if col is None:
        return False
    try:
        update = {
            "$push": {
                "followups": {
                    "at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                    "question": pregunta,
                    "answer": respuesta,
                }
            }
        }
        res = col.update_one({"id": sesion_id}, update)
        return res.modified_count > 0
    except Exception:
        return False


@app.get("/health")
def health() -> Dict[str, Any]:
    try:
        ok_interprete = construir_cadena_interprete() is not None
    except Exception:
        ok_interprete = False
    mongo_enabled = _get_mongo_collection() is not None
    return {"status": "ok", "llm_available": ok_interprete, "mongo": mongo_enabled}


@app.post("/interpret-text")
def interpret_text(req: InterpretTextRequest) -> Dict[str, Any]:
    texto = (req.texto_sueno or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="texto_sueno requerido")

    # Modo offline forzado si se solicita
    if bool(req.offline):
        interpretacion = interpretar_offline(texto, req.contexto_emocional or "")
        ruta_salida: Optional[str] = None
        if req.save:
            base = req.filename if (req.filename and req.filename.strip()) else "sueño_api.txt"
            try:
                from reporte6_BernardoBojalil import guardar_interpretacion
                ruta_salida = guardar_interpretacion(base, interpretacion)
            except Exception:
                ruta_salida = None
        sesion_id = None
        if _get_mongo_collection() is not None:
            sesion_id = _mongo_create_session(req.filename or "(API)", texto, req.contexto_emocional or "", interpretacion, ruta_salida)
        if not sesion_id:
            try:
                sesion_id = _crear_sesion(req.filename or "(API)", texto, req.contexto_emocional or "", interpretacion, ruta_salida)
            except Exception:
                sesion_id = None
        return {"interpretacion": interpretacion, "ruta_salida": ruta_salida, "sesion_id": sesion_id}

    chain = construir_cadena_interprete()
    interpretacion = ""
    if chain is not None:
        try:
            # Construir memoria previa según utilidades existentes
            from os import getenv

            try:
                prev_n = int(getenv("PREVIOUS_N", "5"))
            except ValueError:
                prev_n = 5
            try:
                prev_fu_n = int(getenv("PREV_FOLLOWUPS_N", "3"))
            except ValueError:
                prev_fu_n = 3
            try:
                prev_json_max = int(getenv("PREV_JSON_MAX_CHARS", "20000"))
            except ValueError:
                prev_json_max = 20000
            memoria_json = _memoria_json_compacta(prev_n, prev_fu_n, prev_json_max)

            res = chain.invoke(
                {
                    "texto_sueno": texto,
                    "contexto_emocional": req.contexto_emocional or "",
                    "memoria_json": memoria_json,
                }
            )
            if isinstance(res, str):
                interpretacion = res
            else:
                content = getattr(res, "content", None)
                if isinstance(content, str) and content.strip():
                    interpretacion = content
                elif isinstance(res, dict) and "text" in res:
                    interpretacion = str(res.get("text", ""))
                else:
                    interpretacion = str(res)
        except Exception:
            interpretacion = ""

    if not (interpretacion or "").strip():
        # Fallback offline para no dejar vacío
        interpretacion = interpretar_offline(texto, req.contexto_emocional or "")

    ruta_salida: Optional[str] = None
    if req.save:
        # Para reutilizar la lógica de guardado del proyecto, necesitamos una ruta base.
        # Si no se dio filename, usamos "sueño_api.txt" como base.
        base = req.filename if (req.filename and req.filename.strip()) else "sueño_api.txt"
        try:
            # Guardar reutilizando la función existente que añade _interpretado
            from reporte6_BernardoBojalil import guardar_interpretacion

            ruta_salida = guardar_interpretacion(base, interpretacion)
        except Exception:
            ruta_salida = None

    # Guardado de sesión: preferir Mongo si está disponible; si no, memoria JSON original
    sesion_id = None
    if _get_mongo_collection() is not None:
        sesion_id = _mongo_create_session(req.filename or "(API)", texto, req.contexto_emocional or "", interpretacion, ruta_salida)
    if not sesion_id:
        try:
            sesion_id = _crear_sesion(req.filename or "(API)", texto, req.contexto_emocional or "", interpretacion, ruta_salida)
        except Exception:
            sesion_id = None

    return {
        "interpretacion": interpretacion,
        "ruta_salida": ruta_salida,
        "sesion_id": sesion_id,
    }


@app.post("/interpret-file")
def interpret_file(req: InterpretFileRequest) -> Dict[str, Any]:
    if not (req.ruta or "").strip():
        raise HTTPException(status_code=400, detail="ruta requerida")

    ruta_salida, interpretacion, sesion_id = interpretar_y_guardar(req.ruta, req.contexto_emocional or "")
    if not (interpretacion or "").strip():
        raise HTTPException(status_code=502, detail="No se pudo generar la interpretación. Revisa tu API key/red.")
    # Si Mongo está disponible, reflejar la sesión allí también para unificar fuente de verdad de la API
    if _get_mongo_collection() is not None:
        try:
            # Insertar sesión basada en datos disponibles
            texto_sueno = ""
            try:
                from reporte6_BernardoBojalil import leer_sueno

                texto_sueno = leer_sueno(req.ruta) or ""
            except Exception:
                texto_sueno = ""
            mongo_id = _mongo_create_session(req.ruta, texto_sueno, req.contexto_emocional or "", interpretacion, ruta_salida)
            if mongo_id:
                sesion_id = mongo_id
        except Exception:
            pass
    return {
        "interpretacion": interpretacion,
        "ruta_salida": ruta_salida,
        "sesion_id": sesion_id,
    }


@app.get("/sessions")
def list_sessions(limit: int = 5) -> Dict[str, Any]:
    try:
        n = max(1, min(50, int(limit)))
    except Exception:
        n = 5
    # Preferir Mongo si está configurado
    docs = _mongo_list_sessions(n)
    if docs is not None:
        return {"sessions": docs}
    return {"sessions": _resumen_ultimas_sesiones(n)}


@app.get("/sessions/{sesion_id}")
def get_session(sesion_id: str) -> Dict[str, Any]:
    # Preferir Mongo si está configurado
    s = _mongo_get_session(sesion_id) if _get_mongo_collection() is not None else None
    if not s:
        s = _buscar_sesion(sesion_id)
    if not s:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return s


@app.post("/sessions/{sesion_id}/followup")
def followup(sesion_id: str, req: FollowupRequest) -> Dict[str, Any]:
    s = _mongo_get_session(sesion_id) if _get_mongo_collection() is not None else None
    if not s:
        s = _buscar_sesion(sesion_id)
    if not s:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    pregunta = (req.pregunta or "").strip()
    if not pregunta:
        raise HTTPException(status_code=400, detail="pregunta requerida")

    chain_fu = construir_cadena_followup()
    if chain_fu is None:
        raise HTTPException(status_code=503, detail="Cadena de follow-up no disponible (revisa API/red)")

    try:
        historial_txt = ""
        try:
            # Usar utilidades internas para compactar historial Q/A
            from reporte6_BernardoBojalil import _historial_followup_texto

            historial_txt = _historial_followup_texto(s or {})
        except Exception:
            historial_txt = ""

        resp = chain_fu.invoke(
            {
                "texto_sueno": s.get("texto_sueno", ""),
                "contexto_emocional": s.get("contexto_emocional", ""),
                "interpretacion_previa": s.get("interpretacion", ""),
                "pregunta": pregunta,
                "historial": historial_txt,
            }
        )
        if not isinstance(resp, str):
            resp = getattr(resp, "content", None) or str(resp)
        respuesta = str(resp)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No fue posible responder el seguimiento: {e}")

    # Persistir follow-up según backend disponible
    if _get_mongo_collection() is not None:
        ok = _mongo_add_followup(sesion_id, pregunta, respuesta)
        if not ok:
            # Intentar también en memoria JSON para no perder datos
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


# Convenience root
@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "name": "Traductor de Sueños API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }
