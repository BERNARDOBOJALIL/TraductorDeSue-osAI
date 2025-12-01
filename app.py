"""
MoonBound API - Dream Interpretation and Visualization
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
from reporte6_BernardoBojalil import construir_cadena_interprete
from database import _get_mongo_collection

# Import routers
from routes.auth_routes import router as auth_router
from routes.dream_routes import router as dream_router
from routes.session_routes import router as session_router
from routes.media_routes import router as media_router


app = FastAPI(
    title="MoonBound API",
    version="1.0.0",
    description="Dream interpretation and visualization API powered by Gemini AI"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(dream_router)
app.include_router(session_router)
app.include_router(media_router)


@app.get("/")
def root() -> Dict[str, Any]:
    """Root endpoint."""
    return {
        "name": "MoonBound API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    """Health check endpoint."""
    try:
        ok_interprete = construir_cadena_interprete() is not None
    except Exception:
        ok_interprete = False
    mongo_enabled = _get_mongo_collection() is not None
    return {
        "status": "ok",
        "llm_available": ok_interprete,
        "mongo": mongo_enabled
    }

