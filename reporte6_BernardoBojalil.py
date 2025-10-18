"""
======================================================
 Traductor de Sueños - Agente basado en Gemini AI
======================================================
Bernardo Bojalil Lorenzini - 195908
Agentes Inteligentes
Otoño 2025
18 de octubre de 2025

"""

import os
import json
import warnings
from uuid import uuid4
from datetime import datetime
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

# ==================== Memoria persistente ====================
MEMORY_PATH = os.getenv("MEMORY_PATH", "memoria_agente.json")

def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def cargar_memoria() -> dict:
    try:
        if os.path.exists(MEMORY_PATH):
            with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("sessions", [])
                    return data
        return {"sessions": []}
    except Exception:
        # En caso de corrupción del archivo, iniciar limpio
        return {"sessions": []}

def guardar_memoria(mem: dict) -> None:
    try:
        with open(MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
    except Exception as e:
        msg = f"No se pudo guardar la memoria persistente: {e}"
        print((Fore.YELLOW + msg + Style.RESET_ALL) if HAVE_COLORAMA else msg)

MEM = cargar_memoria()

def _crear_sesion(ruta_sueno: str, texto_sueno: str, contexto: str, interpretacion: str, ruta_salida: str | None) -> str:
    ses_id = str(uuid4())
    resumen_interpretacion = extraer_bloque_por_titulo(interpretacion, "Interpretación general") or resumen_corto(interpretacion, 240)
    ses = {
        "id": ses_id,
        "created_at": _now_iso(),
        "archivo": ruta_sueno,
        "output_file": ruta_salida,
        "contexto_emocional": contexto,
        "texto_sueno": texto_sueno,
        "interpretacion": interpretacion,
        "interpretacion_resumen": resumen_interpretacion,
        "followups": [],
    }
    MEM["sessions"].append(ses)
    guardar_memoria(MEM)
    return ses_id

def _buscar_sesion(sesion_id: str) -> dict | None:
    for s in MEM.get("sessions", []):
        if s.get("id") == sesion_id:
            return s
    return None

def _agregar_followup(sesion_id: str, pregunta: str, respuesta: str) -> None:
    s = _buscar_sesion(sesion_id)
    if not s:
        return
    s.setdefault("followups", []).append({
        "at": _now_iso(),
        "question": pregunta,
        "answer": respuesta,
    })
    guardar_memoria(MEM)

def _historial_followup_texto(s: dict, max_items: int = 5) -> str:
    fl = s.get("followups", [])[-max_items:]
    if not fl:
        return "(sin historial)"
    partes = []
    for item in fl:
        partes.append(f"Q: {item.get('question','')}\nA: {item.get('answer','')}")
    return "\n".join(partes)

def _resumen_ultimas_sesiones(n: int = 5) -> list[dict]:
    """Devuelve un arreglo con resumen de las últimas n sesiones (más recientes primero)."""
    sesiones = MEM.get("sessions", [])
    ordenadas = sorted(sesiones, key=lambda x: x.get("created_at", ""), reverse=True)
    res = []
    for s in ordenadas[: max(0, n)]:
        item = {
            "id": s.get("id"),
            "created_at": s.get("created_at"),
            "archivo": s.get("archivo"),
            "interpretacion_resumen": (s.get("interpretacion_resumen") or "").strip(),
            "output_file": s.get("output_file"),
        }
        res.append(item)
    return res

def _mostrar_resumen_ultimos(n: int = 5) -> None:
    """Imprime un resumen compacto de los últimos n sueños guardados."""
    resumenes = _resumen_ultimas_sesiones(n)
    if not resumenes:
        msg = "No hay sesiones previas guardadas."
        print((Fore.YELLOW + msg + Style.RESET_ALL) if HAVE_COLORAMA else msg)
        return
    titulo = f"\n📘 Últimos {len(resumenes)} sueños"
    print(Fore.CYAN + titulo + Style.RESET_ALL if HAVE_COLORAMA else titulo)
    for i, r in enumerate(resumenes, 1):
        fecha = r.get("created_at", "?")
        archivo = os.path.basename(r.get("archivo", "?"))
        ig = r.get("interpretacion_resumen", "")
        if len(ig) > 180:
            ig = ig[:179].rstrip() + "…"
        linea = f"{i}. [{fecha}] {archivo}\n   → {ig}"
        print(Fore.WHITE + linea + Style.RESET_ALL if HAVE_COLORAMA else linea)

def _memoria_json_compacta(max_sessions: int = 5, max_followups: int = 3, max_chars: int = 20000) -> str:
    """Devuelve un JSON compacto con las últimas sesiones para usar como contexto.
    Limita cantidad de sesiones, follow-ups y tamaño total para evitar prompts excesivos.
    Controlable vía env vars: PREVIOUS_N, PREV_FOLLOWUPS_N, PREV_JSON_MAX_CHARS.
    """
    try:
        sesiones = MEM.get("sessions", [])
        ordenadas = sorted(sesiones, key=lambda x: x.get("created_at", ""), reverse=True)[: max(0, max_sessions)]
        recortadas = []
        for s in ordenadas:
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
            # Compactar y, si aún es largo, truncar con marca
            texto_comp = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            if len(texto_comp) > max_chars:
                return texto_comp[: max_chars - 1].rstrip() + "…"
            return texto_comp
        return texto
    except Exception as e:
        return f"{{\"error\": \"no se pudo construir memoria json: {str(e)}\"}}"
    
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
        input_variables=["texto_sueno", "contexto_emocional", "memoria_json"],
        template=(
            """
Eres un analista onírico con conocimientos en psicología simbólica, arquetipos jungianos,
análisis de sueños freudiano y narrativa terapéutica contemporánea. Tu tarea es interpretar el sueño que
te proporciona el usuario, identificando símbolos, emociones, arquetipos y posibles mensajes del inconsciente.

Analiza con empatía y profundidad, evitando respuestas genéricas. Usa un lenguaje accesible, reflexivo y poético,
pero con base psicológica. No hables de predicciones o supersticiones, sino de interpretaciones emocionales y simbólicas.

Dispones de un contexto en formato JSON con resúmenes de sueños previos del usuario (ver sección "SUEÑOS PREVIOS DEL USUARIO (JSON)").
Úsalo para detectar patrones y símbolos recurrentes, señalar posibles evoluciones del material onírico y establecer relaciones
claras y útiles entre el sueño actual y los anteriores. Si no hay relación sólida, indícalo explícitamente y no inventes detalles.

---
SUEÑO DESCRITO:
{texto_sueno}

CONTEXTO EMOCIONAL:
{contexto_emocional}

SUEÑOS PREVIOS DEL USUARIO (JSON):
{memoria_json}

---
Tu respuesta debe incluir:
1. Un resumen simbólico del sueño (en tono narrativo breve).
2. Un análisis psicológico de los principales símbolos, emociones o acciones.
3. Una interpretación general: ¿qué podría estar expresando el inconsciente?
4. Un consejo o reflexión integradora, invitando al autoconocimiento.
Puedes mencionar brevemente coincidencias o patrones con sueños previos solo cuando aporten claridad (máximo 2–3 oraciones sobre esto).
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
        input_variables=["texto_sueno", "contexto_emocional", "interpretacion_previa", "pregunta", "historial"],
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

HISTORIAL RECIENTE DE FOLLOW-UPS (Q/A):
{historial}

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


def interpretar_y_guardar(ruta_sueno: str, contexto_emocional: str) -> tuple[None | str, str, str | None]:
    """Ejecuta la interpretación con el LLM, guarda el archivo y
    devuelve (ruta_salida, interpretacion, sesion_id). Si falla, retorna (None, "", None).
    """
    texto_sueno = leer_sueno(ruta_sueno)
    if texto_sueno is None:
        return None, "", None

    interpretando = "\n🔮 Interpretando tu sueño...\n"
    print((Fore.MAGENTA + interpretando + Style.RESET_ALL) if HAVE_COLORAMA else interpretando)

    interpretacion = ""
    chain = construir_cadena_interprete()
    if chain is not None:
        try:
            # Usar invoke/run según implementación actual
            try:
                # Config desde env
                try:
                    prev_n = int(os.getenv("PREVIOUS_N", "5"))
                except ValueError:
                    prev_n = 5
                try:
                    prev_fu_n = int(os.getenv("PREV_FOLLOWUPS_N", "3"))
                except ValueError:
                    prev_fu_n = 3
                try:
                    prev_json_max = int(os.getenv("PREV_JSON_MAX_CHARS", "20000"))
                except ValueError:
                    prev_json_max = 20000
                memoria_json = _memoria_json_compacta(prev_n, prev_fu_n, prev_json_max)
                res = chain.invoke({
                    "texto_sueno": texto_sueno,
                    "contexto_emocional": contexto_emocional,
                    "memoria_json": memoria_json,
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
            aviso = f"Aviso: no se pudo usar Gemini ({e}). No se generará interpretación."
            print((Fore.YELLOW + aviso + Style.RESET_ALL) if HAVE_COLORAMA else aviso)

    if not (interpretacion or "").strip():
        msg = "No se generó interpretación (verifica tu API key y conexión)."
        print((Fore.YELLOW + msg + Style.RESET_ALL) if HAVE_COLORAMA else msg)
        return None, "", None

    ruta_salida = guardar_interpretacion(ruta_sueno, interpretacion)
    sesion_id = _crear_sesion(ruta_sueno, texto_sueno, contexto_emocional, interpretacion, ruta_salida)
    return ruta_salida, interpretacion, sesion_id


# (sin fallback offline de follow-up)


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
        ruta_salida, interpretacion, sesion_id = interpretar_y_guardar("sueño.txt", "")
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
                        ses = _buscar_sesion(sesion_id) if sesion_id else None
                        historial_txt = _historial_followup_texto(ses or {})
                        resp = chain_fu.invoke({
                            "texto_sueno": leer_sueno("sueño.txt") or "",
                            "contexto_emocional": "",
                            "interpretacion_previa": interpretacion,
                            "pregunta": pregunta_auto,
                            "historial": historial_txt,
                        })
                        if not isinstance(resp, str):
                            resp = getattr(resp, "content", None) or str(resp)
                    else:
                        raise RuntimeError("Cadena de follow-up no disponible (revisa API/red)")
                    print(Fore.WHITE + str(resp) + Style.RESET_ALL if HAVE_COLORAMA else str(resp))
                except Exception as e:
                    msg = f"No fue posible responder el seguimiento automáticamente: {e}"
                    print((Fore.YELLOW + msg + Style.RESET_ALL) if HAVE_COLORAMA else msg)
            # Mostrar resumen de últimos sueños si se solicita
            if os.getenv("SHOW_SUMMARY", "0") == "1":
                try:
                    n = int(os.getenv("SUMMARY_N", "5"))
                except ValueError:
                    n = 5
                _mostrar_resumen_ultimos(n)
        return

    # Bucle simple: interpretar uno y preguntar si se desea otro
    while True:
        ruta = input("📝 Ruta del archivo (Enter para 'sueño.txt'): ").strip() or "sueño.txt"
        ctx = input("💭 ¿Cómo te sentiste durante o después del sueño? (opcional): ").strip()

        ruta_salida, interpretacion, sesion_id = interpretar_y_guardar(ruta, ctx)
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
                    ses = _buscar_sesion(sesion_id) if sesion_id else None
                    historial_txt = _historial_followup_texto(ses or {})
                    resp = chain_fu.invoke({
                        "texto_sueno": leer_sueno(ruta) or "",
                        "contexto_emocional": ctx,
                        "interpretacion_previa": interpretacion,
                        "pregunta": q,
                        "historial": historial_txt,
                    })
                    if not isinstance(resp, str):
                        resp = getattr(resp, "content", None) or str(resp)
                else:
                    raise RuntimeError("Cadena de follow-up no disponible (revisa API/red)")
                # guardar en memoria persistente
                if sesion_id:
                    _agregar_followup(sesion_id, q, str(resp))
                print(Fore.WHITE + str(resp) + Style.RESET_ALL if HAVE_COLORAMA else str(resp))
            except Exception as e:
                msg = f"No fue posible responder el seguimiento: {e}"
                print((Fore.YELLOW + msg + Style.RESET_ALL) if HAVE_COLORAMA else msg)
        
        # Mostrar un resumen breve de los últimos sueños tras cada interpretación
        try:
            _mostrar_resumen_ultimos(5)
        except Exception:
            pass

        otra = input("\n¿Interpretar otro sueño? (s/n): ").strip().lower()
        if otra not in {"s", "si", "sí"}:
            print("Hasta luego 👋")
            break

if __name__ == "__main__":
    ejecuta_tarea()
