"""Servicio de generación de títulos."""
from typing import Optional, Tuple
from config import GEMINI_TEXT_API_KEY, GEMINI_API_KEY


def generate_dream_title(descripcion: str) -> Tuple[Optional[str], Optional[str]]:
    """Genera un título breve del sueño usando Gemini. Retorna (title, error_msg)."""
    gemini_key = GEMINI_TEXT_API_KEY or GEMINI_API_KEY
    if not gemini_key:
        return None, "GEMINI_TEXT_API_KEY o GEMINI_API_KEY no configurada"
    
    try:
        from reporte6_BernardoBojalil import ChatGoogleGenerativeAI, LANGCHAIN_OK
        
        if not LANGCHAIN_OK or ChatGoogleGenerativeAI is None:
            return None, "LangChain o ChatGoogleGenerativeAI no disponible"
        
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=gemini_key,
            temperature=0.7,
        )
        
        prompt = f"""Genera un título muy breve y descriptivo (máximo 6 palabras) para este sueño. 
Solo devuelve el título, sin explicaciones adicionales.

Sueño: {descripcion[:500]}

Título:"""
        
        response = llm.invoke(prompt)
        title = response.content.strip().strip('"').strip("'")
        
        if len(title) > 60:
            title = title[:57] + "..."
        
        return title, None
        
    except Exception as e:
        error_msg = str(e)
        print(f"Error generando título: {error_msg}")
        return None, error_msg
