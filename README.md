# SECOP 2 Agent — Monitor de Contratación Pública

Bot conversacional de Telegram que monitorea SECOP 2 (Colombia) y envía alertas
automáticamente y genera borradores de propuestas con IA.

---

## Requisitos del sistema

- Windows 10/11 o Linux (Ubuntu 20.04+)
- Python 3.10 o superior
- 2 GB RAM mínimo, 4 GB recomendado
- 1 GB de espacio en disco
- Conexión a internet estable

---

## Instalación

### 1. Clonar/copiar el proyecto

Coloca toda la carpeta `SECOP2` en el equipo o VPS.

### 2. Crear entorno virtual de Python

**Windows:**
```powershell
cd "ruta\al\proyecto\SECOP2"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux:**
```bash
cd /ruta/al/proyecto/SECOP2
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
playwright install chromium
```

(Playwright es opcional — el bot funciona sin él pero pierde la capacidad de leer PDFs)

### 4. Configurar credenciales

Copia `.env.example` a `.env` y completa estos valores:

```env
TELEGRAM_TOKEN=tu_token_de_BotFather
TELEGRAM_CHAT_ID=tu_chat_id_o_lista_separada_por_comas
ANTHROPIC_API_KEY=sk-ant-api03-...
SOCRATA_APP_TOKEN=opcional_pero_recomendado
```

**Cómo obtener cada credencial:**

- **TELEGRAM_TOKEN**: Habla con `@BotFather` en Telegram, usa `/newbot` y copia el token
- **TELEGRAM_CHAT_ID**: Escríbele al bot y consulta `https://api.telegram.org/bot<TOKEN>/getUpdates`
- **ANTHROPIC_API_KEY**: Crea cuenta en https://console.anthropic.com → API Keys
- **SOCRATA_APP_TOKEN**: (Opcional) Crea cuenta en https://www.datos.gov.co → Developer Settings → New App Token. Sin token funciona pero con límite de peticiones.

### 5. Personalizar el contexto de la empresa

Edita `config/empresa.json` con los datos reales:

```json
{
  "razon_social": "TU EMPRESA S.A.S.",
  "nit": "900123456-7",
  "representante_legal": "Nombre completo",
  "municipio": "Rivera",
  "departamento": "Huila",
  "direccion": "Calle 1 # 2-3",
  "telefono": "+57 300 000 0000",
  "email": "contacto@empresa.com",
  ...
}
```

Cuanto más completo, mejores documentos genera el bot.

### 6. Personalizar palabras clave

Edita `config/keywords.json` para ajustar las categorías y palabras de búsqueda
al tipo de contratos que le interesan a la empresa.

---

## Cómo correr

### Windows (manera fácil)

Doble clic en `start.bat` — activa el entorno e inicia el bot con su programador.

### Manual (Windows o Linux)

```bash
python main.py --check   # diagnóstico: credenciales, tokens, configuración, base de datos
python main.py
```
El bot queda escuchando en Telegram y corre las búsquedas automáticas a las 08:00, 14:00 y 20:00.

---

## Cómo usar el bot

El bot funciona con **lenguaje natural** en Telegram. Ejemplos:

- *"busca procesos de esta semana"* → corre búsqueda en SECOP
- *"¿cuál fue el último proceso?"* → consulta DB
- *"¿qué hay de mantenimiento?"* → filtra por categoría
- *"olvida todo"* → resetea la conversación
- *"olvida que dije que no tenemos RUP"* → borra un hecho específico

### Búsquedas automáticas
- **08:00, 14:00, 20:00** → busca procesos publicados en los últimos 3 días
- **07:30, 13:30** → revisa procesos a punto de cerrar
- **07:00** → resumen diario al chat
- **Lunes 08:30** → ranking semanal
- **02:00** → backup automático de la DB

---

## Costos esperados (Claude API)

- Mensaje conversacional: ~$0.002
- Búsqueda + scoring de 50 procesos: ~$0.05
- Generación de documento Word: ~$0.30

**Uso típico de una empresa pequeña:** $5-10 USD/mes
Cap diario configurado en `cost_tracker.py` (default $5/día)

---

## Estructura del proyecto

```
SECOP2/
├── main.py              ← Bot Telegram + scheduler
├── secop_scraper.py     ← API Socrata (datos.gov.co)
├── relevance_scorer.py  ← Scoring con Claude Haiku
├── doc_generator.py     ← Generación Word con Claude Sonnet
├── secop_playwright.py  ← (Opcional) Lectura de PDFs
├── db_manager.py        ← SQLite con WAL mode
├── cost_tracker.py      ← Control de gasto Claude
├── research/            ← Scripts de investigación a la medida
├── config/
│   ├── empresa.json     ← Datos de la empresa cliente
│   └── keywords.json    ← Palabras clave de búsqueda
├── secop.db             ← Base de datos (se crea sola)
├── output/
│   ├── docs/            ← Word generados
│   └── reports/         ← Excel
├── backups/             ← Backups automáticos
└── logs/                ← Logs rotatorios
```

---

## Limitaciones conocidas

1. **Lectura de PDFs adjuntos**: SECOP 2 usa Vortal anti-bot que bloquea
   descargas automáticas. El bot trabaja con los datos de la API oficial
   (que es información completa y actualizada).

2. **Modalidad de contratación**: Configurado para Mínima Cuantía. Para
   otras modalidades, edita `config/keywords.json`.

3. **Cobertura geográfica**: Configurado para Huila. Para otros
   departamentos cambia `departamento_filter` en `keywords.json`.

---

## Soporte y mantenimiento

Para problemas técnicos:
- Revisa `logs/secop.log` (los últimos errores aparecen ahí)
- Revisa que `.env` tenga todas las credenciales correctas
- Revisa la cuota de la API key de Anthropic

---

## Stack técnico

- **Python 3** + pyTelegramBotAPI
- **Claude Haiku 4.5** → conversación + scoring (rápido y económico)
- **Claude Sonnet 4.6** → generación de documentos jurídicos
- **SQLite WAL** → persistencia
- **Socrata API** → consulta oficial SECOP 2
- **Playwright** (opcional) → lectura de PDFs (limitado por anti-bot)
