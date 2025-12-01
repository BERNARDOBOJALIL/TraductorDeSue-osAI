"""Rutas de autenticación."""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any
from models import UserCreate, UserLogin, Token, UserResponse
from auth import get_password_hash, verify_password, create_access_token, get_current_user
from database import _get_users_collection, _create_user_mongo, _get_user_by_email_mongo


router = APIRouter(prefix="", tags=["Authentication"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
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


@router.post("/login", response_model=Token)
def login(credentials: UserLogin) -> Dict[str, Any]:
    """Inicia sesión y devuelve un JWT."""
    if _get_users_collection() is None:
        raise HTTPException(status_code=503, detail="MongoDB no está disponible. Configura MONGODB_URI.")
    
    user_doc = _get_user_by_email_mongo(credentials.email)
    if user_doc is None or not verify_password(credentials.password, user_doc.get("hashed_password", "")):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    
    access_token = create_access_token(data={"sub": user_doc["id"], "email": user_doc["email"]})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
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
