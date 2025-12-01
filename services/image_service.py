"""Servicio de generación de imágenes."""
from typing import Optional, Tuple
from config import GEMINI_IMAGE_API_KEY, GEMINI_API_KEY


def generate_dream_image(descripcion: str, estilo: str = "surrealista y onírico", size: str = "1024x1024") -> Tuple[Optional[str], Optional[str]]:
    """Genera una imagen usando Gemini 2.5 Flash Image. Retorna (data_url, error_msg)."""
    gemini_key = GEMINI_IMAGE_API_KEY or GEMINI_API_KEY
    if not gemini_key:
        return None, "GEMINI_IMAGE_API_KEY o GEMINI_API_KEY no configurada"

    try:
        from google import genai
        import base64

        client = genai.Client(api_key=gemini_key)

        prompt = f"Create a dream illustration with {estilo} style: {descripcion}. Concept art, dreamlike atmosphere, vibrant colors, high quality, detailed"

        if len(prompt) > 2000:
            prompt = prompt[:1997] + "..."

        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt],
        )

        if hasattr(response, 'candidates') and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate, 'content') and candidate.content:
                    for part in candidate.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data is not None:
                            image_bytes = part.inline_data.data
                            img_b64 = base64.b64encode(image_bytes).decode()
                            
                            mime_type = part.inline_data.mime_type or "image/png"
                            if "jpeg" in mime_type or "jpg" in mime_type:
                                image_url = f"data:image/jpeg;base64,{img_b64}"
                            else:
                                image_url = f"data:image/png;base64,{img_b64}"
                            
                            return image_url, None
        
        return None, "No se generó ninguna imagen en la respuesta"

    except Exception as e:
        error_msg = str(e)
        print(f"Error generando imagen: {error_msg}")
        return None, error_msg
