"""Servicio de interpretación de sueños."""
import os
import concurrent.futures
from typing import Optional, Tuple
from config import LLM_TIMEOUT_SECS, PREVIOUS_N, PREV_FOLLOWUPS_N, PREV_JSON_MAX_CHARS
from database import _memoria_json_compacta_user
from reporte6_BernardoBojalil import (
    construir_cadena_interprete,
    interpretar_offline,
)


def interpret_dream_with_context(
    texto_sueno: str, 
    contexto_emocional: str, 
    user_id: str
) -> Tuple[str, Optional[str]]:
    """
    Interpreta un sueño usando el LLM con contexto de sueños previos del usuario.
    Retorna (interpretacion, error_msg).
    """
    chain = construir_cadena_interprete()
    interpretacion = ""
    
    if chain is not None:
        try:
            memoria_json = _memoria_json_compacta_user(user_id, PREVIOUS_N, PREV_FOLLOWUPS_N, PREV_JSON_MAX_CHARS)

            payload = {
                "texto_sueno": texto_sueno,
                "contexto_emocional": contexto_emocional,
                "memoria_json": memoria_json,
            }

            def _invoke():
                return chain.invoke(payload)

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(_invoke)
                res = fut.result(timeout=LLM_TIMEOUT_SECS)
            
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
            interpretacion = ""
        except Exception as e:
            print(f"Error en interpretación con LLM: {e}")
            interpretacion = ""

    if not (interpretacion or "").strip():
        # Fallback offline
        interpretacion = interpretar_offline(texto_sueno, contexto_emocional)
    
    return interpretacion, None if interpretacion else "No se pudo generar interpretación"
