"""Configuración de la aplicación."""
import os

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "tu-secret-key-super-segura-cambiala-en-produccion")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 días

# MongoDB
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "ai_dreams")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "sessions")

# Gemini API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_TEXT_API_KEY = os.getenv("GEMINI_TEXT_API_KEY")
GEMINI_IMAGE_API_KEY = os.getenv("GEMINI_IMAGE_API_KEY")

# LLM Configuration
LLM_TIMEOUT_SECS = int(os.getenv("LLM_TIMEOUT_SECS", "20"))
FORCE_OFFLINE = os.getenv("FORCE_OFFLINE", "0") == "1"

# Context Memory
PREVIOUS_N = int(os.getenv("PREVIOUS_N", "5"))
PREV_FOLLOWUPS_N = int(os.getenv("PREV_FOLLOWUPS_N", "3"))
PREV_JSON_MAX_CHARS = int(os.getenv("PREV_JSON_MAX_CHARS", "20000"))
