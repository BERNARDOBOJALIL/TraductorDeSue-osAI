"""
======================================================
 Traductor de Sueños - Agente basado en Gemini AI
======================================================
Correcciones clave:
- Alinea la variable de entorno esperada a GOOGLE_API_KEY (acepta GEMINI_API_KEY como alias).
- Usa el pipeline `prompt | llm | StrOutputParser()` y `invoke()` (sin deprecaciones).
- Suprime mensajes ruidosos de gRPC/absl al importar el cliente.
- Fallback local si el modelo no responde o no hay clave: nunca escribe vacío.
"""

import os
import warnings
from contextlib import redirect_stderr
from dotenv import load_dotenv

# Colores en consola (opcional)
HAVE_COLORAMA = True
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init(autoreset=True)
except Exception:
    HAVE_COLORAMA = False

# Reducir verbosidad gRPC/absl antes de importar clientes que puedan loguear en stderr
os.environ.setdefault("GRPC_VERBOSITY", "NONE")  # NONE/ERROR/INFO
os.environ.setdefault("GRPC_TRACE", "")

# LangChain/Google imports (tolerantes a ausencia de librería)
LANGCHAIN_OK = True
ChatGoogleGenerativeAI = None
PromptTemplate = None
StrOutputParser = None

try:
    # Evita que mensajes de bajo nivel contaminen la consola durante el import
    with open(os.devnull, "w") as _devnull:
        with redirect_stderr(_devnull):
            from langchain_google_genai import ChatGoogleGenerativeAI as _ChatGG
    ChatGoogleGenerativeAI = _ChatGG

    # PromptTemplate: intentar core primero, luego fallback
    try:
        from langchain_core.prompts import PromptTemplate as _PromptTemplate
    except Exception:
        from langchain.prompts import PromptTemplate as _PromptTemplate
    PromptTemplate = _PromptTemplate

    # Output parser a string: core primero, luego fallback
    try:
        from langchain_core.output_parsers import StrOutputParser as _StrOutputParser
    except Exception:
        try:
            from langchain.output_parsers import StrOutputParser as _StrOutputParser
        except Exception:
            _StrOutputParser = None
    StrOutputParser = _StrOutputParser
except Exception:
    LANGCHAIN_OK = False

# 1) Cargar variables de entorno
load_dotenv()

# 2) Normalizar clave: permitir GEMINI_API_KEY pero usar GOOGLE_API_KEY
google_key = os.getenv("GOOGLE_API_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")
if not google_key and gemini_key:
    # Propagar alias para el SDK de Google
    os.environ["GOOGLE_API_KEY"] = gemini_key
    google_key = gemini_key

def construir_cadena_interprete():
    """Crea y devuelve una cadena (Runnable) de interpretación si LangChain y la clave están disponibles."""
    if not LANGCHAIN_OK or not google_key or ChatGoogleGenerativeAI is None or PromptTemplate is None:
        return None

    # 3) Configuración del modelo Gemini
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.8,  # alto grado de creatividad interpretativa
        google_api_key=google_key,
    )

    # 4) Prompt para el traductor de sueños
    prompt_template = PromptTemplate(
        input_variables=["texto_sueno", "contexto_emocional"],
        template=(
            """
Eres un analista onírico con conocimientos en psicología simbólica, arquetipos jungianos,
análisis de sueños freudiano y narrativa terapéutica contemporánea. Tu tarea es interpretar el sueño que
te proporciona el usuario, identificando símbolos, emociones, arquetipos y posibles mensajes del inconsciente.

Analiza con empatía y profundidad, evitando respuestas genéricas. Usa un lenguaje accesible, reflexivo y poético,
pero con base psicológica. No hables de predicciones o supersticiones, sino de interpretaciones emocionales y simbólicas.

---
SUEÑO DESCRITO:
{texto_sueno}

CONTEXTO EMOCIONAL:
{contexto_emocional}

---
Tu respuesta debe incluir:
1. Un resumen simbólico del sueño (en tono narrativo breve).
2. Un análisis psicológico de los principales símbolos, emociones o acciones.
3. Una interpretación general: ¿qué podría estar expresando el inconsciente?
4. Un consejo o reflexión integradora, invitando al autoconocimiento.
---
"""
        ),
    )

    # 5) Pipeline Runnable: prompt -> llm -> str
    chain = prompt_template | llm
    if StrOutputParser is not None:
        chain = chain | StrOutputParser()
    return chain


def construir_cadena_followup():
    """Crea y devuelve una cadena (Runnable) para responder preguntas de seguimiento
    basadas en el sueño y la interpretación previa.
    """
    if not LANGCHAIN_OK or not google_key or ChatGoogleGenerativeAI is None or PromptTemplate is None:
        return None

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.5,  # tono más estable para follow-ups
        google_api_key=google_key,
    )

    prompt_template = PromptTemplate(
        input_variables=["texto_sueno", "contexto_emocional", "interpretacion_previa", "pregunta"],
        template=(
            """
Eres un analista onírico. Responde de forma breve (máximo 3–5 frases) y concreta a la pregunta
de seguimiento del usuario. Basa tu respuesta en el sueño, el contexto emocional y la interpretación previa.
No inventes detalles no soportados; si algo no está claro en el material, dilo explícitamente y sugiere cómo
explorarlo.

---
SUEÑO:
{texto_sueno}

CONTEXTO EMOCIONAL:
{contexto_emocional}

INTERPRETACIÓN PREVIA:
{interpretacion_previa}

PREGUNTA DE SEGUIMIENTO:
{pregunta}
---
Respuesta breve y directa:
"""
        ),
    )

    chain = prompt_template | llm
    if StrOutputParser is not None:
        chain = chain | StrOutputParser()
    return chain


def leer_sueno(ruta_archivo: str):
    """Lee el contenido del archivo del sueño en UTF-8."""
    try:
        with open(ruta_archivo, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print("Error: No se encontró el archivo con el sueño.")
        return None
    except Exception as e:
        print(f"Error al leer el archivo: {e}")
        return None


def guardar_interpretacion(ruta_original: str, interpretacion: str):
    """Guarda la interpretación en <base>_interpretado.txt, evitando archivos vacíos.
    Devuelve la ruta del archivo si se guardó, o None si no se escribió.
    """
    base, ext = os.path.splitext(ruta_original)
    nueva_ruta = f"{base}_interpretado{ext if ext else '.txt'}"
    try:
        # No crees archivos vacíos por error
        contenido = (interpretacion or "").strip()
        if not contenido:
            msg = "Advertencia: la interpretación quedó vacía; no se escribirá el archivo."
            print((Fore.YELLOW + msg + Style.RESET_ALL) if HAVE_COLORAMA else msg)
            return None
        with open(nueva_ruta, "w", encoding="utf-8") as f:
            f.write(contenido)
        msg_ok = f"\n🌙 Interpretación guardada en: {nueva_ruta}\n"
        print((Fore.GREEN + msg_ok + Style.RESET_ALL) if HAVE_COLORAMA else msg_ok)
        return nueva_ruta
    except Exception as e:
        msg_err = f"Error al guardar la interpretación: {e}"
        print((Fore.RED + msg_err + Style.RESET_ALL) if HAVE_COLORAMA else msg_err)
        return None


def interpretar_offline(texto_sueno: str, contexto: str = "") -> str:
    """Fallback sencillo sin red: produce una interpretación básica para no dejar el archivo vacío."""
    texto_sueno = (texto_sueno or "").strip()
    contexto = (contexto or "").strip()
    resumen = texto_sueno.splitlines()[0][:120] if texto_sueno else "(sin descripción)"
    return (
        "Resumen simbólico:\n"
        f"- El sueño podría aludir a {('una búsqueda interna y cambio' if 'bosque' in texto_sueno.lower() else 'procesos internos')}.\n\n"
        "Análisis psicológico:\n"
        "- Observa los elementos centrales (lugares, objetos, acciones) y las emociones que despiertan.\n"
        "- Atiende tensiones entre deseo y miedo, y señales de transición vital.\n\n"
        "Interpretación general:\n"
        f"- Este relato sugiere elaboración de experiencias recientes y necesidades de integración emocional. {('Se percibe nostalgia o duelo.' if 'llor' in texto_sueno.lower() else '')}\n\n"
        "Consejo integrador:\n"
        "- Escribe el sueño completo, identifica 3 símbolos y compón una frase puente entre lo soñado y tu vida actual.\n\n"
        f"Fragmento del sueño: {resumen}\n"
        + (f"Contexto emocional: {contexto}\n" if contexto else "")
    )


# Utilidades de resumen (deben existir antes de ejecuta_tarea)
def _buscar_seccion(texto: str, titulo: str) -> int:
    idx = texto.lower().find(titulo.lower())
    return idx

def resumen_corto(texto: str, max_len: int = 280) -> str:
    """Obtiene un resumen breve y robusto del texto de interpretación.
    Preferencia: extraer la sección 'Resumen simbólico' si existe; si no, el primer párrafo.
    """
    if not texto:
        return "(sin contenido)"
    t = texto.strip()

    # Intentar extraer desde 'Resumen simbólico'
    start = _buscar_seccion(t, "Resumen simbólico")
    if start == -1:
        start = _buscar_seccion(t, "Resumen")
    if start != -1:
        sub = t[start:]
        # Cortar hasta el siguiente encabezado conocido
        cortes = [
            _buscar_seccion(sub, "Análisis psicológico"),
            _buscar_seccion(sub, "Interpretación general"),
            _buscar_seccion(sub, "Consejo integrador"),
            _buscar_seccion(sub, "---"),
        ]
        cortes_validos = [c for c in cortes if c not in (-1, 0)]
        limite = min(cortes_validos) if cortes_validos else len(sub)
        candidato = sub[:limite].strip()
    else:
        # Primer párrafo o primera línea
        partes = t.split("\n\n")
        candidato = partes[0].strip() if partes else t

    # Limitar longitud
    if len(candidato) > max_len:
        return candidato[: max_len - 1].rstrip() + "…"
    return candidato

def extraer_bloque_por_titulo(texto: str, titulo: str) -> str | None:
    """Extrae el bloque que inicia en `titulo` hasta el siguiente encabezado conocido."""
    if not texto:
        return None
    t = texto.strip()
    start = _buscar_seccion(t, titulo)
    if start == -1:
        return None
    sub = t[start:]
    cortes = [
        _buscar_seccion(sub, "Análisis psicológico"),
        _buscar_seccion(sub, "Consejo integrador"),
        _buscar_seccion(sub, "Resumen simbólico"),
        _buscar_seccion(sub, "---"),
    ]
    cortes_validos = [c for c in cortes if c not in (-1, 0)]
    limite = min(cortes_validos) if cortes_validos else len(sub)
    bloque = sub[:limite].strip()
    # Quitar la línea de encabezado si corresponde
    lineas = bloque.splitlines()
    if lineas and "interpretación general" in lineas[0].lower():
        bloque = "\n".join(lineas[1:]).strip()
    return bloque or None


def interpretar_y_guardar(ruta_sueno: str, contexto_emocional: str) -> tuple[None | str, str]:
    """Ejecuta la interpretación (online u offline), guarda el archivo y
    devuelve (ruta_salida, interpretacion).
    """
    texto_sueno = leer_sueno(ruta_sueno)
    if texto_sueno is None:
        return None, ""

    interpretando = "\n🔮 Interpretando tu sueño...\n"
    print((Fore.MAGENTA + interpretando + Style.RESET_ALL) if HAVE_COLORAMA else interpretando)

    interpretacion = ""
    chain = construir_cadena_interprete()
    if chain is not None:
        try:
            # Usar invoke/run según implementación actual
            try:
                res = chain.invoke({
                    "texto_sueno": texto_sueno,
                    "contexto_emocional": contexto_emocional,
                })
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
            except AttributeError:
                # Si no existe invoke (versiones antiguas), intentar run
                interpretacion = chain.run({
                    "texto_sueno": texto_sueno,
                    "contexto_emocional": contexto_emocional,
                })
        except Exception as e:
            aviso = f"Aviso: no se pudo usar Gemini ({e}). Se usará un análisis básico offline."
            print((Fore.YELLOW + aviso + Style.RESET_ALL) if HAVE_COLORAMA else aviso)

    if not (interpretacion or "").strip():
        interpretacion = interpretar_offline(texto_sueno, contexto_emocional)

    ruta_salida = guardar_interpretacion(ruta_sueno, interpretacion)
    return ruta_salida, interpretacion


def responder_followup_offline(interpretacion: str, pregunta: str) -> str:
    """Responde de forma breve usando la interpretación previa como base, sin LLM."""
    base = extraer_bloque_por_titulo(interpretacion, "Interpretación general") or resumen_corto(interpretacion, 240)
    pregunta = (pregunta or "").strip()
    if not base:
        return "Con la información disponible, sólo puedo sugerir observar cómo se relaciona este sueño con tus emociones recientes."
    # Heurística simple: referencia la interpretación general
    respuesta = (
        "Según la interpretación general, este sueño apunta a procesos de integración emocional. "
        "En tu pregunta, percibo interés por detalles específicos: considera cómo los símbolos clave conectan con tu situación actual. "
        "Si algo no encaja, anota nuevos sueños o sensaciones para refinar el sentido."
    )
    # Limitar extensión
    return respuesta[:380]


def ejecuta_tarea():
    titulo = " --- 💤 Traductor de Sueños (Gemini AI) --- "
    subtitulo = "Convierte tus sueños en lenguaje simbólico y reflexión.\n"
    if HAVE_COLORAMA:
        print(Fore.CYAN + Style.BRIGHT + titulo + Style.RESET_ALL)
        print(Fore.CYAN + subtitulo + Style.RESET_ALL)
    else:
        print(titulo)
        print(subtitulo)

    # Fast-path: modo automático (una sola interpretación y salir)
    if os.getenv("AUTO_RUN") == "1":
        auto_msg = "(AUTO_RUN=1) Usando archivo por defecto 'sueño.txt' y contexto vacío.\n"
        print((Fore.BLUE + auto_msg + Style.RESET_ALL) if HAVE_COLORAMA else auto_msg)
        ruta_salida, interpretacion = interpretar_y_guardar("sueño.txt", "")
        if (interpretacion or "").strip():
            bloque = extraer_bloque_por_titulo(interpretacion, "Interpretación general") or resumen_corto(interpretacion, 280)
            encabezado = "--- Interpretación general ---\n"
            if HAVE_COLORAMA:
                print(Fore.YELLOW + Style.BRIGHT + encabezado + Style.RESET_ALL)
                print(Fore.WHITE + bloque + Style.RESET_ALL)
            else:
                print(encabezado)
                print(bloque)
            if ruta_salida:
                nota = f"\n(Lee la interpretación completa en: {ruta_salida})\n"
                print((Fore.GREEN + nota + Style.RESET_ALL) if HAVE_COLORAMA else nota)
            # Follow-up automático si se pasa AUTO_FOLLOWUP y pregunta
            auto_follow = os.getenv("AUTO_FOLLOWUP") == "1"
            pregunta_auto = os.getenv("FOLLOWUP_QUESTION", "").strip()
            if auto_follow and pregunta_auto:
                chain_fu = construir_cadena_followup()
                print((Fore.CYAN + "\n🤔 Seguimiento:" + Style.RESET_ALL) if HAVE_COLORAMA else "\n🤔 Seguimiento:")
                try:
                    if chain_fu is not None:
                        resp = chain_fu.invoke({
                            "texto_sueno": leer_sueno("sueño.txt") or "",
                            "contexto_emocional": "",
                            "interpretacion_previa": interpretacion,
                            "pregunta": pregunta_auto,
                        })
                        if not isinstance(resp, str):
                            resp = getattr(resp, "content", None) or str(resp)
                    else:
                        resp = responder_followup_offline(interpretacion, pregunta_auto)
                    print(Fore.WHITE + str(resp) + Style.RESET_ALL if HAVE_COLORAMA else str(resp))
                except Exception as e:
                    msg = f"No fue posible responder el seguimiento automáticamente: {e}"
                    print((Fore.YELLOW + msg + Style.RESET_ALL) if HAVE_COLORAMA else msg)
        return

    # Bucle simple: interpretar uno y preguntar si se desea otro
    while True:
        ruta = input("📝 Ruta del archivo (Enter para 'sueño.txt'): ").strip() or "sueño.txt"
        ctx = input("💭 ¿Cómo te sentiste durante o después del sueño? (opcional): ").strip()

        ruta_salida, interpretacion = interpretar_y_guardar(ruta, ctx)
        if (interpretacion or "").strip():
            bloque = extraer_bloque_por_titulo(interpretacion, "Interpretación general") or resumen_corto(interpretacion, 280)
            encabezado = "--- Interpretación general ---\n"
            if HAVE_COLORAMA:
                print(Fore.YELLOW + Style.BRIGHT + encabezado + Style.RESET_ALL)
                print(Fore.WHITE + bloque + Style.RESET_ALL)
            else:
                print(encabezado)
                print(bloque)
            if ruta_salida:
                nota = f"\n(Lee la interpretación completa en: {ruta_salida})\n"
                print((Fore.GREEN + nota + Style.RESET_ALL) if HAVE_COLORAMA else nota)

        # Bucle de follow-up por este sueño
        while True:
            q = input("\n¿Tienes una pregunta de seguimiento? (Enter para omitir): ").strip()
            if not q:
                break
            chain_fu = construir_cadena_followup()
            print((Fore.CYAN + "\n🤔 Seguimiento:" + Style.RESET_ALL) if HAVE_COLORAMA else "\n🤔 Seguimiento:")
            try:
                if chain_fu is not None:
                    resp = chain_fu.invoke({
                        "texto_sueno": leer_sueno(ruta) or "",
                        "contexto_emocional": ctx,
                        "interpretacion_previa": interpretacion,
                        "pregunta": q,
                    })
                    if not isinstance(resp, str):
                        resp = getattr(resp, "content", None) or str(resp)
                else:
                    resp = responder_followup_offline(interpretacion, q)
                print(Fore.WHITE + str(resp) + Style.RESET_ALL if HAVE_COLORAMA else str(resp))
            except Exception as e:
                msg = f"No fue posible responder el seguimiento: {e}"
                print((Fore.YELLOW + msg + Style.RESET_ALL) if HAVE_COLORAMA else msg)

        otra = input("\n¿Interpretar otro sueño? (s/n): ").strip().lower()
        if otra not in {"s", "si", "sí"}:
            print("Hasta luego 👋")
            break

if __name__ == "__main__":
    ejecuta_tarea()
