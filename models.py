"""Modelos Pydantic para la API."""
from pydantic import BaseModel, Field, AliasChoices, EmailStr
from typing import Optional


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
    size: Optional[str] = Field("1024x1024", description="Tamaño de la imagen")
    sesion_id: Optional[str] = Field(None, description="ID de sesión para vincular la imagen")


class GenerateTitleRequest(BaseModel):
    descripcion_sueno: str = Field(..., description="Descripción del sueño para generar el título")
