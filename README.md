# Traductor de Sueños (Gemini AI)

Agente local que interpreta el archivo `sueño.txt` y escribe `sueño_interpretado.txt` usando Google Gemini vía LangChain. En consola muestra únicamente la sección “Interpretación general” con formato legible (colores opcionales con Colorama). Soporta preguntas de seguimiento (follow-up) por cada sueño interpretado.

## Características técnicas del agente

- Pipeline moderno de LangChain: `PromptTemplate | ChatGoogleGenerativeAI | StrOutputParser` y `.invoke()` (sin deprecaciones).
- Gestión de API Key: usa `GOOGLE_API_KEY` y acepta `GEMINI_API_KEY` como alias.
- Consola clara: imprime solo “Interpretación general”; la salida completa se guarda en archivo.
- Follow-up por sueño: puedes hacer varias preguntas de seguimiento tras cada interpretación (también hay modo automático por variables de entorno).
- Contexto con memoria JSON: el análisis incorpora un bloque JSON con resúmenes de sueños previos para detectar patrones y relaciones cuando aporten claridad.
- Silenciamiento de logs ruidosos: reduce mensajes de gRPC/absl al importar el cliente para evitar warnings molestos en Windows/PowerShell.
- Manejo de errores y seguridad de archivos: si falla la API o no hay respuesta válida, informa el problema y no escribe archivo vacío.
- Compatibilidad UTF-8: nombres con acentos y contenido en español.

## Requisitos

- Python 3.10+
- Dependencias (instalación con requirements):
  - langchain
  - langchain-google-genai
  - python-dotenv
  - colorama (opcional, colores en consola)

Instalación (Windows PowerShell):

```powershell
# (Opcional) crear entorno virtual
py -m venv venv
venv\Scripts\Activate

# instalar dependencias
pip install -r requirements.txt
```

## Configuración de la clave (API)

- GOOGLE_API_KEY
- GEMINI_API_KEY

Definir en PowerShell (solo para la sesión actual):

```powershell
$env:GOOGLE_API_KEY = "tu_api_key"
```

o crear un archivo `.env` en esta carpeta:

```
GOOGLE_API_KEY=tu_api_key
```


## Despliegue local paso a paso (Windows PowerShell)

1) Clona o abre la carpeta del proyecto en tu equipo.
2) (Opcional) Crea y activa un entorno virtual:

```powershell
py -m venv venv
venv\Scripts\Activate
```

3) Instala dependencias:

```powershell
pip install -r requirements.txt
```

4) Define la API Key (o crea `.env`):

```powershell
$env:GOOGLE_API_KEY = "tu_api_key"
```

5) Coloca tu descripción del sueño en `sueño.txt` (UTF-8) y ejecuta:

```powershell
python .\reporte6_BernardoBojalil.py
```

## Notas

- El programa no genera archivos vacíos: si falla la API/red, informa en consola y no escribe salida.
- No compartas tu `.env` ni tu API Key en repos públicos.

## Modos y banderas útiles

- AUTO_RUN=1: ejecuta una sola interpretación leyendo `sueño.txt` y termina.
- AUTO_FOLLOWUP=1 con FOLLOWUP_QUESTION="...": realiza una pregunta de seguimiento automática tras interpretar.
- SHOW_SUMMARY=1 y opcional SUMMARY_N=5: al finalizar en AUTO_RUN, imprime un resumen compacto de los últimos N sueños guardados.
- PREVIOUS_N=5: número de sesiones previas a incluir en el contexto JSON.
- PREV_FOLLOWUPS_N=3: número de follow-ups por sesión a incluir en el JSON.
- PREV_JSON_MAX_CHARS=20000: tamaño máximo del JSON (se compacta o trunca si es necesario).

En PowerShell, por ejemplo:

```powershell
$env:AUTO_RUN = "1"
$env:SHOW_SUMMARY = "1"
$env:SUMMARY_N = "5"
python .\reporte6_BernardoBojalil.py
```

## Ver resúmenes sin interpretar

Al iniciar en modo interactivo, el programa ofrece un pequeño menú:

- 1) Interpretar un sueño
- 2) Ver resúmenes recientes
- 3) Salir

Elige la opción 2 para ver un listado compacto de los últimos sueños guardados (toma el extracto de “Interpretación general”).

## Persistencia (memoria)

- Cada ejecución se guarda en `memoria_agente.json` con: fecha, archivo de entrada, contexto emocional, interpretación completa, un extracto de “Interpretación general” y el historial de preguntas/respuestas de seguimiento.
- En modo interactivo, al terminar una interpretación se imprime automáticamente un resumen compacto de las últimas sesiones.
- En AUTO_RUN, puedes activar `SHOW_SUMMARY=1` (y opcional `SUMMARY_N`) para mostrar el mismo resumen.