# MoonBound - Dream Interpretation API

**MoonBound** es una API de interpretación y visualización de sueños impulsada por Google Gemini AI. Ofrece análisis psicológicos profundos, generación automática de títulos, creación de imágenes oníricas y gestión completa de sesiones con autenticación por usuario.

Agente local que interpreta el archivo `sueño.txt` y escribe `sueño_interpretado.txt` usando Google Gemini vía LangChain. En consola muestra únicamente la sección "Interpretación general" con formato legible (colores opcionales con Colorama). Soporta preguntas de seguimiento (follow-up) por cada sueño interpretado.

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

## API (FastAPI)

Se agregó una API mínima con FastAPI que reutiliza la lógica existente del proyecto. No se modificó tu `.env` ni se añadieron archivos innecesarios.

### Ejecutar la API

Instala dependencias (si no lo hiciste) y levanta el servidor con Uvicorn:

```powershell
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

- Documentación interactiva: `http://127.0.0.1:8000/docs`
- Redoc: `http://127.0.0.1:8000/redoc`

### Endpoints

#### Endpoints Públicos

- `GET /health`: Estado básico del servicio y disponibilidad del LLM.

#### Autenticación

**Importante:** La API ahora requiere autenticación para los endpoints de interpretación y gestión de sesiones. Cada usuario tiene su propio historial privado de sueños.

- `POST /register`
  - Body JSON:
    - `email` (string, requerido): email del usuario
    - `password` (string, requerido, mínimo 6 caracteres): contraseña
    - `nombre` (string, opcional): nombre del usuario
  - Respuesta JSON:
    - `access_token` (string): JWT token
    - `token_type` (string): "bearer"
  - Nota: Requiere MongoDB configurado.

- `POST /login`
  - Body JSON:
    - `email` (string, requerido): email del usuario
    - `password` (string, requerido): contraseña
  - Respuesta JSON:
    - `access_token` (string): JWT token
    - `token_type` (string): "bearer"

- `GET /me`
  - Headers: `Authorization: Bearer {token}`
  - Respuesta JSON: información del usuario actual (`id`, `email`, `nombre`, `created_at`)

#### Endpoints Protegidos (requieren autenticación)

Para usar estos endpoints, incluye el header: `Authorization: Bearer {tu_token}`

- `POST /interpret-text`
  - Headers: `Authorization: Bearer {token}`
  - Body JSON:
    - `texto_sueno` (string, requerido): descripción del sueño.
    - `contexto_emocional` (string, opcional): contexto emocional.
    - `save` (bool, opcional, por defecto false): si true, guarda la interpretación en archivo.
    - `filename` (string, opcional): nombre base del archivo para el guardado (si `save=true`).
    - `offline` (bool, opcional): forzar modo offline sin LLM.
  - Respuesta JSON:
    - `interpretacion` (string): interpretación completa.
    - `ruta_salida` (string|null): ruta del archivo guardado si aplica.
    - `sesion_id` (string|null): id de sesión persistida.
    - `title` (string): título generado automáticamente del sueño.
    - `titulo` (string): título generado automáticamente del sueño (mismo valor).

- `POST /interpret-file`
  - Headers: `Authorization: Bearer {token}`
  - Body JSON:
    - `ruta` (string, requerido): ruta del archivo del sueño (UTF-8).
    - `contexto_emocional` (string, opcional): contexto emocional.
  - Respuesta JSON:
    - `interpretacion` (string)
    - `ruta_salida` (string|null)
    - `sesion_id` (string|null)
    - `title` (string): título generado automáticamente del sueño.
    - `titulo` (string): título generado automáticamente del sueño (mismo valor).

- `GET /sessions?limit=5`
  - Headers: `Authorization: Bearer {token}`
  - Devuelve un resumen de tus últimas sesiones guardadas (solo las del usuario actual).

- `GET /sessions/{sesion_id}`
  - Headers: `Authorization: Bearer {token}`
  - Devuelve el contenido completo de tu sesión (verifica que sea tuya).

- `DELETE /sessions/{sesion_id}`
  - Headers: `Authorization: Bearer {token}`
  - Elimina una sesión del historial del usuario actual.
  - Respuesta JSON:
    - `message` (string): mensaje de confirmación
    - `sesion_id` (string): id de la sesión eliminada
    - `deleted` (boolean): true si se eliminó exitosamente

- `POST /sessions/{sesion_id}/followup`
  - Headers: `Authorization: Bearer {token}`
  - Body JSON:
    - `pregunta` (string, requerido): pregunta de seguimiento.
  - Respuesta JSON:
    - `respuesta` (string): respuesta breve del analista onírico.

- `POST /generate-title`
  - Headers: `Authorization: Bearer {token}`
  - Body JSON:
    - `descripcion_sueno` (string, requerido): descripción del sueño
  - Respuesta JSON:
    - `title` (string): título generado (máximo 6 palabras, 60 caracteres)
    - `titulo` (string): título generado (mismo valor)
  - Genera un título breve y descriptivo del sueño para mostrar en el historial.

- `POST /generate-image`
  - Headers: `Authorization: Bearer {token}`
  - Body JSON:
    - `descripcion_sueno` (string, requerido): descripción del sueño a visualizar
    - `estilo` (string, opcional, default "surrealista y onírico"): estilo artístico
    - `size` (string, opcional): tamaño de la imagen
    - `sesion_id` (string, opcional): vincular imagen con una sesión existente
  - Respuesta JSON:
    - `image_url` (string): imagen en formato base64 data URL
    - `descripcion` (string): descripción usada
    - `estilo` (string): estilo aplicado
    - `size` (string): tamaño generado
  - Genera una imagen visual del sueño usando Gemini 2.5 Flash Image.

### Ejemplo de uso con autenticación

```powershell
# 1. Registrarse
$body = @{ email = "tu@email.com"; password = "tupassword123"; nombre = "Tu Nombre" } | ConvertTo-Json
$resp = Invoke-RestMethod -Uri http://127.0.0.1:8000/register -Method POST -Body $body -ContentType "application/json"
$token = $resp.access_token

# 2. O iniciar sesión si ya tienes cuenta
$body = @{ email = "tu@email.com"; password = "tupassword123" } | ConvertTo-Json
$resp = Invoke-RestMethod -Uri http://127.0.0.1:8000/login -Method POST -Body $body -ContentType "application/json"
$token = $resp.access_token

# 3. Usar el token para interpretar un sueño
$headers = @{ Authorization = "Bearer $token" }
$body = @{ texto_sueno = "Soñé que volaba sobre el mar" } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/interpret-text -Method POST -Body $body -ContentType "application/json" -Headers $headers

# 4. Ver tus sesiones
Invoke-RestMethod -Uri "http://127.0.0.1:8000/sessions?limit=5" -Method GET -Headers $headers

# 5. Generar imagen del sueño
$body = @{ 
    descripcion_sueno = "Volaba sobre el mar viendo delfines"
    estilo = "surrealista y onírico"
    size = "1024x1024"
} | ConvertTo-Json
$imgResp = Invoke-RestMethod -Uri http://127.0.0.1:8000/generate-image -Method POST -Body $body -ContentType "application/json" -Headers $headers
# La URL de la imagen estará en $imgResp.image_url
```

### Generación de Imágenes

La API ahora incluye generación de imágenes de sueños usando **Gemini 2.5 Flash Image** de Google.

#### Configuración

Usa la misma API key de Gemini que ya tienes configurada:
```env
GEMINI_API_KEY=tu-clave-aqui
```

No requiere configuración adicional.

#### Endpoint de generación de imágenes

- `POST /generate-image`
  - Headers: `Authorization: Bearer {token}`
  - Body JSON:
    - `descripcion_sueno` (string, requerido): descripción del sueño a visualizar
    - `estilo` (string, opcional, default "surrealista y onírico"): estilo artístico
    - `size` (string, opcional): ignorado por ahora
    - `sesion_id` (string, opcional): vincular imagen con una sesión existente
  - Respuesta JSON:
    - `image_url` (string): imagen en formato base64 data URL (no expira)
    - `descripcion` (string): descripción usada
    - `estilo` (string): estilo aplicado
    - `size` (string): tamaño generado

#### Cómo probar en Postman

**Paso 1: Obtener token de autenticación**
- Method: `POST`
- URL: `https://tu-app.onrender.com/login`
- Body (JSON):
```json
{
  "email": "tu@email.com",
  "password": "tu_password"
}
```
- Copia el `access_token` de la respuesta

**Paso 2: Generar imagen**
- Method: `POST`
- URL: `https://tu-app.onrender.com/generate-image`
- Headers:
  - `Authorization: Bearer <tu_access_token>`
  - `Content-Type: application/json`
- Body (JSON):
```json
{
  "descripcion_sueno": "Volaba sobre un océano de nubes doradas al atardecer",
  "estilo": "arte digital vibrante"
}
```

**Paso 3: Visualizar la imagen**
- La respuesta contiene `image_url` con formato: `data:image/png;base64,iVBORw0KGg...`
- Copia todo el contenido de `image_url`
- Pégalo en la barra de direcciones de tu navegador (Chrome/Edge)
- O usa una extensión de Postman para visualizar imágenes base64

**Notas:**
- Las imágenes se devuelven en formato base64 embebidas en la respuesta (no expiran).
- Usa el modelo `gemini-2.5-flash-image` de Google.
- Gratuito dentro de los límites de la API de Gemini.

### Generación de Títulos

Endpoint para generar títulos breves y descriptivos de sueños para mostrar en el historial.

#### Endpoint de generación de títulos

- `POST /generate-title`
  - Headers: `Authorization: Bearer {token}`
  - Body JSON:
    - `descripcion_sueno` (string, requerido): descripción del sueño
  - Respuesta JSON:
    - `title` (string): título generado (máximo 6 palabras)
    - `titulo` (string): título generado (mismo valor)

**Ejemplo en Postman:**
- Method: `POST`
- URL: `https://tu-app.onrender.com/generate-title`
- Headers:
  - `Authorization: Bearer <tu_access_token>`
  - `Content-Type: application/json`
- Body (JSON):
```json
{
  "descripcion_sueno": "Volaba sobre un océano de nubes doradas al atardecer"
}
```

**Respuesta:**
```json
{
  "title": "Vuelo sobre nubes doradas",
  "titulo": "Vuelo sobre nubes doradas"
}
```
```

### Notas

- **Autenticación obligatoria**: Todos los endpoints de interpretación y sesiones requieren un token JWT válido.
- Cada usuario solo puede ver y acceder a sus propias sesiones (aislamiento por `user_id`).
- MongoDB es **requerido** para autenticación. Configura `MONGODB_URI` en tu `.env`.
- La API reusa la memoria persistente `memoria_agente.json` para mantener sesiones locales (fallback si Mongo no está disponible).
- Si el LLM no está disponible, `POST /interpret-text` usa un fallback offline para no retornar vacío.

### Variables de entorno adicionales para autenticación

- `SECRET_KEY` (requerido en producción): clave secreta para firmar JWT tokens. Por defecto usa una clave de desarrollo insegura.
- `ACCESS_TOKEN_EXPIRE_MINUTES` (opcional, por defecto 10080 = 7 días): tiempo de expiración del token en minutos.

### API Keys opcionales separadas

Puedes usar API keys diferentes para distintas funcionalidades de Gemini:

- `GEMINI_API_KEY` (requerido): API key principal de Gemini. Se usa como fallback si las específicas no están configuradas.
- `GEMINI_TEXT_API_KEY` (opcional): API key específica para interpretaciones de texto y generación de títulos. Si no está configurada, usa `GEMINI_API_KEY`.
- `GEMINI_IMAGE_API_KEY` (opcional): API key específica para generación de imágenes. Si no está configurada, usa `GEMINI_API_KEY`.

**Ejemplo en `.env`:**
```env
GEMINI_API_KEY=tu-api-key-principal
GEMINI_TEXT_API_KEY=tu-api-key-para-texto
GEMINI_IMAGE_API_KEY=tu-api-key-para-imagenes
```

Esto te permite usar diferentes proyectos de Google Cloud o gestionar cuotas por separado.

### MongoDB Atlas (opcional)

Si defines estas variables de entorno, la API usará MongoDB Atlas para guardar y consultar sesiones (en lugar del archivo JSON):

- `MONGODB_URI`: cadena de conexión de MongoDB Atlas.
- `MONGODB_DB` (opcional, por defecto `ai_dreams`): nombre de la base.
- `MONGODB_COLLECTION` (opcional, por defecto `sessions`): colección de sesiones.

Ejemplo en PowerShell (sin modificar tu `.env` existente):

```powershell
$env:MONGODB_URI = "mongodb+srv://<user>:<pass>@<cluster>/...?retryWrites=true&w=majority"
$env:MONGODB_DB = "ai_dreams"
$env:MONGODB_COLLECTION = "sessions"
uvicorn app:app --reload --port 8000
```

Notas:
- Los endpoints `/sessions`, `/sessions/{id}` y `POST /sessions/{id}/followup` priorizan Mongo cuando está configurado; si no, usan el almacenamiento JSON existente.
- `POST /interpret-file` seguirá guardando la interpretación en disco (si aplica) y, además, reflejará la sesión en Mongo cuando esté disponible.