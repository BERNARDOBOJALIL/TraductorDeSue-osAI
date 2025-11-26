from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, AliasChoices, EmailStr
from typing import Optional, List, Dict, Any
import concurrent.futures
import os
from uuid import uuid4
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt

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

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "tu-secret-key-super-segura-cambiala-en-produccion")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 días por defecto

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Auth Models ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    nombre: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: str
    email: str
    nombre: Optional[str] = None
    created_at: str


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


class GenerateImageRequest(BaseModel):
    descripcion_sueno: str = Field(..., description="Descripción del sueño para generar la imagen")
    estilo: Optional[str] = Field("surrealista y onírico", description="Estilo artístico de la imagen")
    size: Optional[str] = Field("1024x1024", description="Tamaño de la imagen: 1024x1024, 1792x1024, 1024x1792")
    sesion_id: Optional[str] = Field(None, description="ID de sesión para vincular la imagen")



# --- MongoDB (opcional) ---
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
    uri = os.getenv("MONGODB_URI")
    if not uri:
        return None
    try:
        _MONGO_CLIENT = MongoClient(uri, serverSelectionTimeoutMS=3000)
        return _MONGO_CLIENT
    except Exception:
        return None


def _get_mongo_db():
    """Devuelve la base de datos de Mongo."""
    client = _get_mongo_client()
    if client is None:
        return None
    db_name = os.getenv("MONGODB_DB", "ai_dreams")
    return client[db_name]


def _get_mongo_collection():
    """Devuelve la colección de sesiones."""
    db = _get_mongo_db()
    if db is None:
        return None
    coll_name = os.getenv("MONGODB_COLLECTION", "sessions")
    return db[coll_name]


def _get_users_collection():
    """Devuelve la colección de usuarios."""
    db = _get_mongo_db()
    if db is None:
        return None
    return db.get_collection("users")


def _mongo_create_session(ruta_sueno: str, texto_sueno: str, contexto: str, interpretacion: str, ruta_salida: Optional[str], user_id: Optional[str] = None):
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
        "user_id": user_id,
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


def _mongo_get_session(sesion_id: str, user_id: Optional[str] = None):
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
    col = _get_mongo_collection()
    if col is None:
        return None
    try:
        query = {}
        if user_id:
            query["user_id"] = user_id
        cur = col.find(query, {"_id": 0, "id": 1, "created_at": 1, "archivo": 1, "interpretacion_resumen": 1, "output_file": 1}).sort("created_at", -1).limit(max(1, limit))
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


# --- Auth Functions ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Extrae y valida el JWT del header Authorization."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
        return {"user_id": user_id, "email": payload.get("email")}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")


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
        # Verificar si el email ya existe
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


# --- Auth Endpoints ---
@app.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate) -> Dict[str, Any]:
    """Registra un nuevo usuario y devuelve un JWT."""
    if _get_users_collection() is None:
        raise HTTPException(status_code=503, detail="MongoDB no está disponible. Configura MONGODB_URI.")
    
    hashed_password = get_password_hash(user.password)
    user_id = _create_user_mongo(user.email, hashed_password, user.nombre)
    
    if user_id is None:
        raise HTTPException(status_code=400, detail="El email ya está registrado o hubo un error.")
    
    access_token = create_access_token(data={"sub": user_id, "email": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/login", response_model=Token)
def login(credentials: UserLogin) -> Dict[str, Any]:
    """Inicia sesión y devuelve un JWT."""
    if _get_users_collection() is None:
        raise HTTPException(status_code=503, detail="MongoDB no está disponible. Configura MONGODB_URI.")
    
    user_doc = _get_user_by_email_mongo(credentials.email)
    if user_doc is None or not verify_password(credentials.password, user_doc.get("hashed_password", "")):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    
    access_token = create_access_token(data={"sub": user_doc["id"], "email": user_doc["email"]})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/me", response_model=UserResponse)
def get_me(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Devuelve la información del usuario actual."""
    user_doc = _get_user_by_email_mongo(current_user["email"])
    if user_doc is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {
        "id": user_doc["id"],
        "email": user_doc["email"],
        "nombre": user_doc.get("nombre"),
        "created_at": user_doc.get("created_at", ""),
    }


# --- Image Generation ---
def _generate_dream_image(descripcion: str, estilo: str = "surrealista y onírico", size: str = "1024x1024") -> tuple[Optional[str], Optional[str]]:
    """Genera una imagen usando Hugging Face Inference Client. Retorna (data_url, error_msg)."""
    hf_token = os.getenv("HUGGINGFACE_TOKEN")
    if not hf_token:
        return None, "HUGGINGFACE_TOKEN no configurada. Obtén una gratis en https://huggingface.co/settings/tokens"

    try:
        from huggingface_hub import InferenceClient
        import base64
        from io import BytesIO

        # Construir prompt en inglés (funciona mejor)
        prompt = f"Dream illustration with {estilo} style: {descripcion}. Concept art, dreamlike atmosphere, vibrant colors, high quality, detailed"

        if len(prompt) > 1000:
            prompt = prompt[:997] + "..."

        # Usar el cliente oficial de Hugging Face
        client = InferenceClient(token=hf_token)

        # text_to_image devuelve un objeto PIL.Image
        image = client.text_to_image(
            prompt,
            model="stabilityai/stable-diffusion-2-1",
        )

        # Convertir PIL Image a base64
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()
        image_url = f"data:image/png;base64,{img_b64}"
        
        return image_url, None

    except Exception as e:
        error_msg = str(e)
        print(f"Error generando imagen: {error_msg}")
        return None, error_msg

    except Exception as e:
        error_msg = str(e)
        print(f"Error generando imagen: {error_msg}")
        return None, error_msg

    except Exception as e:
        error_msg = str(e)
        print(f"Error generando imagen: {error_msg}")
        return None, error_msg


@app.post("/generate-image")
def generate_image(req: GenerateImageRequest, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Genera una imagen del sueño usando Stable Diffusion (Hugging Face)."""
    if not os.getenv("HUGGINGFACE_TOKEN"):
        raise HTTPException(status_code=503, detail="HUGGINGFACE_TOKEN no configurada. Obtén una gratis en https://huggingface.co/settings/tokens")
    
    descripcion = (req.descripcion_sueno or "").strip()
    if not descripcion:
        raise HTTPException(status_code=400, detail="descripcion_sueno requerida")
    
    # Generar imagen
    image_url, error_msg = _generate_dream_image(descripcion, req.estilo or "surrealista y onírico", req.size or "1024x1024")
    
    if not image_url:
        detail_msg = f"No se pudo generar la imagen: {error_msg}" if error_msg else "No se pudo generar la imagen. Revisa tu API key de OpenAI."
        raise HTTPException(status_code=502, detail=detail_msg)
    
    # Si hay sesion_id, actualizar la sesión en Mongo con la URL de la imagen
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


@app.get("/health")
def health() -> Dict[str, Any]:
    try:
        ok_interprete = construir_cadena_interprete() is not None
    except Exception:
        ok_interprete = False
    mongo_enabled = _get_mongo_collection() is not None
    return {"status": "ok", "llm_available": ok_interprete, "mongo": mongo_enabled}


@app.post("/interpret-text")
def interpret_text(req: InterpretTextRequest, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    texto = (req.texto_sueno or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="texto_sueno requerido")

    user_id = current_user["user_id"]

    # Modo offline forzado si se solicita o por env
    if bool(req.offline) or os.getenv("FORCE_OFFLINE", "0") == "1":
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
            sesion_id = _mongo_create_session(req.filename or "(API)", texto, req.contexto_emocional or "", interpretacion, ruta_salida, user_id)
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

            payload = {
                "texto_sueno": texto,
                "contexto_emocional": req.contexto_emocional or "",
                "memoria_json": memoria_json,
            }
            try:
                timeout_secs = int(os.getenv("LLM_TIMEOUT_SECS", "20"))
            except Exception:
                timeout_secs = 20

            def _invoke():
                return chain.invoke(payload)

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(_invoke)
                res = fut.result(timeout=timeout_secs)
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
        except concurrent.futures.TimeoutError:
            # Exceso de tiempo: usar fallback offline
            interpretacion = ""
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
        sesion_id = _mongo_create_session(req.filename or "(API)", texto, req.contexto_emocional or "", interpretacion, ruta_salida, user_id)
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
def interpret_file(req: InterpretFileRequest, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if not (req.ruta or "").strip():
        raise HTTPException(status_code=400, detail="ruta requerida")

    user_id = current_user["user_id"]
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
            mongo_id = _mongo_create_session(req.ruta, texto_sueno, req.contexto_emocional or "", interpretacion, ruta_salida, user_id)
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
def list_sessions(limit: int = 5, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        n = max(1, min(50, int(limit)))
    except Exception:
        n = 5
    user_id = current_user["user_id"]
    # Preferir Mongo si está configurado
    docs = _mongo_list_sessions(n, user_id)
    if docs is not None:
        return {"sessions": docs}
    return {"sessions": _resumen_ultimas_sesiones(n)}


@app.get("/sessions/{sesion_id}")
def get_session(sesion_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    user_id = current_user["user_id"]
    # Preferir Mongo si está configurado
    s = _mongo_get_session(sesion_id, user_id) if _get_mongo_collection() is not None else None
    if not s:
        s = _buscar_sesion(sesion_id)
    if not s:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    # Verificar que la sesión pertenezca al usuario (si tiene user_id)
    if s.get("user_id") and s.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="No tienes permiso para acceder a esta sesión")
    return s


@app.post("/sessions/{sesion_id}/followup")
def followup(sesion_id: str, req: FollowupRequest, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    user_id = current_user["user_id"]
    s = _mongo_get_session(sesion_id, user_id) if _get_mongo_collection() is not None else None
    if not s:
        s = _buscar_sesion(sesion_id)
    if not s:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    # Verificar que la sesión pertenezca al usuario (si tiene user_id)
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
            # Usar utilidades internas para compactar historial Q/A
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
        try:
            timeout_secs = int(os.getenv("LLM_TIMEOUT_SECS", "20"))
        except Exception:
            timeout_secs = 20

        def _invoke_fu():
            return chain_fu.invoke(payload_fu)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_invoke_fu)
            resp = fut.result(timeout=timeout_secs)
        if not isinstance(resp, str):
            resp = getattr(resp, "content", None) or str(resp)
        respuesta = str(resp)
    except concurrent.futures.TimeoutError as e:
        raise HTTPException(status_code=504, detail="Tiempo de espera agotado para follow-up")
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
