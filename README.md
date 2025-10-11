# Traductor de Sueños (Gemini AI)

Agente local que interpreta el archivo `sueño.txt` y escribe `sueño_interpretado.txt` usando Google Gemini vía LangChain. En consola muestra únicamente la sección “Interpretación general” con formato legible (colores opcionales con Colorama). Soporta preguntas de seguimiento (follow-up) por cada sueño interpretado.

## Características técnicas del agente

- Pipeline moderno de LangChain: `PromptTemplate | ChatGoogleGenerativeAI | StrOutputParser` y `.invoke()` (sin deprecaciones).
- Gestión de API Key: usa `GOOGLE_API_KEY` y acepta `GEMINI_API_KEY` como alias.
- Consola clara: imprime solo “Interpretación general”; la salida completa se guarda en archivo.
- Follow-up por sueño: puedes hacer varias preguntas de seguimiento tras cada interpretación (también hay modo automático por variables de entorno).
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