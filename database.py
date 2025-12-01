"""Gestión de base de datos MongoDB."""
import os
import json
from typing import Optional, Dict, Any, List
from uuid import uuid4
from datetime import datetime
from config import MONGODB_URI, MONGODB_DB, MONGODB_COLLECTION


# MongoDB client singleton
_MONGO_OK = False
_MONGO_CLIENT = None

try:
    from pymongo import MongoClient
    _MONGO_OK = True
except Exception:
    _MONGO_OK = False


def _get_mongo_client():
    """Devuelve el cliente de Mongo si está disponible; si no, None."""
    global _MONGO_CLIENT
    if not _MONGO_OK:
        return None
    if _MONGO_CLIENT is not None:
        return _MONGO_CLIENT
    if not MONGODB_URI:
        return None
    try:
        _MONGO_CLIENT = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
        return _MONGO_CLIENT
    except Exception:
        return None


def _get_mongo_db():
    """Devuelve la base de datos de Mongo."""
    client = _get_mongo_client()
    if client is None:
        return None
    return client[MONGODB_DB]


def _get_mongo_collection():
    """Devuelve la colección de sesiones."""
    db = _get_mongo_db()
    if db is None:
        return None
    return db[MONGODB_COLLECTION]


def _get_users_collection():
    """Devuelve la colección de usuarios."""
    db = _get_mongo_db()
    if db is None:
        return None
    return db.get_collection("users")


def _mongo_create_session(
    ruta_sueno: str, 
    texto_sueno: str, 
    contexto: str, 
    interpretacion: str, 
    ruta_salida: Optional[str], 
    user_id: Optional[str] = None, 
    titulo: Optional[str] = None
):
    """Crea una sesión en MongoDB."""
    col = _get_mongo_collection()
    if col is None:
        return None
    ses_id = str(uuid4())
    
    # Obtener resumen
    try:
        from reporte6_BernardoBojalil import extraer_bloque_por_titulo, resumen_corto
        resumen_interpretacion = extraer_bloque_por_titulo(interpretacion, "Interpretación general") or resumen_corto(interpretacion, 240)
    except Exception:
        resumen_interpretacion = None
    
    doc = {
        "id": ses_id,
        "user_id": user_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "archivo": ruta_sueno,
        "output_file": ruta_salida,
        "contexto_emocional": contexto,
        "texto_sueno": texto_sueno,
        "interpretacion": interpretacion,
        "title": titulo,
        "titulo": titulo,
        "interpretacion_resumen": (resumen_interpretacion or "").strip(),
        "followups": [],
    }
    try:
        col.insert_one(doc)
        return ses_id
    except Exception:
        return None


def _mongo_get_session(sesion_id: str, user_id: Optional[str] = None):
    """Obtiene una sesión de MongoDB."""
    col = _get_mongo_collection()
    if col is None:
        return None
    try:
        query = {"id": sesion_id}
        if user_id:
            query["user_id"] = user_id
        doc = col.find_one(query, {"_id": 0})
        return doc
    except Exception:
        return None


def _mongo_list_sessions(limit: int = 5, user_id: Optional[str] = None):
    """Lista sesiones de MongoDB."""
    col = _get_mongo_collection()
    if col is None:
        return None
    try:
        query = {}
        if user_id:
            query["user_id"] = user_id
        cur = col.find(
            query, 
            {"_id": 0, "id": 1, "created_at": 1, "archivo": 1, "interpretacion_resumen": 1, "output_file": 1, "title": 1, "titulo": 1}
        ).sort("created_at", -1).limit(max(1, limit))
        return list(cur)
    except Exception:
        return None


def _mongo_add_followup(sesion_id: str, pregunta: str, respuesta: str):
    """Agrega un follow-up a una sesión en MongoDB."""
    col = _get_mongo_collection()
    if col is None:
        return False
    try:
        update = {
            "$push": {
                "followups": {
                    "at": datetime.now().isoformat(timespec="seconds"),
                    "question": pregunta,
                    "answer": respuesta,
                }
            }
        }
        res = col.update_one({"id": sesion_id}, update)
        return res.modified_count > 0
    except Exception:
        return False


def _mongo_delete_session(sesion_id: str, user_id: str):
    """Elimina una sesión de MongoDB."""
    col = _get_mongo_collection()
    if col is None:
        return 0
    try:
        result = col.delete_one({"id": sesion_id, "user_id": user_id})
        return result.deleted_count
    except Exception:
        return 0


def _memoria_json_compacta_user(user_id: str, max_sessions: int = 5, max_followups: int = 3, max_chars: int = 20000) -> str:
    """Devuelve un JSON compacto con las últimas sesiones del usuario para usar como contexto."""
    try:
        col = _get_mongo_collection()
        if col is not None:
            try:
                cur = col.find(
                    {"user_id": user_id},
                    {"_id": 0, "id": 1, "created_at": 1, "archivo": 1, "contexto_emocional": 1, "interpretacion_resumen": 1, "followups": 1}
                ).sort("created_at", -1).limit(max(1, max_sessions))
                sesiones = list(cur)
            except Exception:
                sesiones = []
        else:
            # Fallback a memoria JSON local
            from reporte6_BernardoBojalil import MEM
            todas = MEM.get("sessions", [])
            sesiones = [s for s in todas if s.get("user_id") == user_id]
            sesiones = sorted(sesiones, key=lambda x: x.get("created_at", ""), reverse=True)[:max_sessions]
        
        recortadas = []
        for s in sesiones:
            fu = s.get("followups", []) or []
            if max_followups > 0:
                fu = fu[-max_followups:]
            recortadas.append({
                "id": s.get("id"),
                "created_at": s.get("created_at"),
                "archivo": s.get("archivo"),
                "contexto_emocional": s.get("contexto_emocional"),
                "interpretacion_resumen": s.get("interpretacion_resumen"),
                "followups": fu,
            })
        data = {"sessions": recortadas}
        texto = json.dumps(data, ensure_ascii=False, indent=2)
        if len(texto) > max_chars:
            texto_comp = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            if len(texto_comp) > max_chars:
                return texto_comp[: max_chars - 1].rstrip() + "…"
            return texto_comp
        return texto
    except Exception as e:
        return f"{{\"error\": \"no se pudo construir memoria json: {str(e)}\"}}"


# User management
def _create_user_mongo(email: str, hashed_password: str, nombre: Optional[str] = None) -> Optional[str]:
    """Crea un usuario en Mongo y devuelve su ID."""
    col = _get_users_collection()
    if col is None:
        return None
    user_id = str(uuid4())
    doc = {
        "id": user_id,
        "email": email,
        "hashed_password": hashed_password,
        "nombre": nombre,
        "created_at": datetime.utcnow().isoformat(timespec="seconds"),
    }
    try:
        existing = col.find_one({"email": email})
        if existing:
            return None
        col.insert_one(doc)
        return user_id
    except Exception:
        return None


def _get_user_by_email_mongo(email: str) -> Optional[Dict[str, Any]]:
    """Busca un usuario por email en Mongo."""
    col = _get_users_collection()
    if col is None:
        return None
    try:
        doc = col.find_one({"email": email}, {"_id": 0})
        return doc
    except Exception:
        return None
