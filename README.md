# Market Dashboard

Panel de precios en vivo, estilo TradingView, construido con **Flask**
(arquitectura **MVC**) y **UV** para la gestión del proyecto/dependencias.
Descarga los precios de **Yahoo Finance** (vía `yfinance`) y los dibuja con
[lightweight-charts](https://github.com/tradingview/lightweight-charts), la
propia librería open-source de gráficos de TradingView.

![sidebar](https://img.shields.io/badge/UI-sidebar%20izquierdo-2962ff)

## Arquitectura

```
config.py               # Configuración (variables de entorno)
run.py                   # Punto de entrada: `uv run run.py`
app/
  __init__.py            # Application factory: create_app()
  models/                # MODEL: acceso a datos, sin Flask
    apps.py                 # Registro de "apps" de primer nivel del sidebar
    watchlists.py            # Registro de watchlists de la app "Gráficas"
    market_data.py            # Descarga + caché de precios/velas (yfinance)
    analysis.py                # Volatilidad mensual + histogramas (seaborn)
  services/                # Integraciones de más alto nivel (no acceso crudo a datos)
    resumen_service.py         # Resumen de un activo (reutiliza market_data)
    email_service.py            # Envío del resumen por correo (Resend)
  controllers/            # CONTROLLER: blueprints de Flask
    home.py                   # "/" -> redirige a la app por defecto
    graficas.py                # App "Gráficas": sidebar de watchlists + gráfico
    varianza.py                 # App "Análisis de Varianza" (placeholder)
    resumen.py                   # Vista "Resumen por correo" (GET /resumen)
    api.py                       # API JSON que consume el JavaScript (incluye POST /api/resumen)
  views/                   # VIEW: plantillas Jinja2
    base.html                 # Layout con el sidebar
    dashboard.html             # Cabecera + toolbar + contenedor del gráfico
    varianza.html               # Página en blanco de Análisis de Varianza
    resumen.html                 # Vista "Resumen por correo" (standalone, sin sidebar)
    partials/sidebar.html
  static/
    css/style.css
    js/app.js                 # Fetch a la API + render con lightweight-charts
    js/vendor/lightweight-charts.standalone.production.js
tests/                   # pytest (modelos + rutas, con datos simulados)
```

- **Model**: `app/models/market_data.py` es el único lugar que habla con
  `yfinance`; expone `Quote` (precio actual) y velas OHLC ya cacheadas.
  `app/models/apps.py` registra las secciones de primer nivel del sidebar
  y `app/models/watchlists.py` las watchlists dentro de la app "Gráficas".
- **View**: plantillas Jinja2 en `app/views` (sí, la carpeta se llama
  `views` y no `templates`, configurado explícitamente en la app factory).
- **Controller**: un blueprint por app (`home`, `graficas`, `varianza`) más
  `api`, que sirve JSON al frontend (para refrescar precios sin recargar
  la página).

## Cómo extenderla

El sidebar tiene dos niveles:

1. **Apps** (`app/models/apps.py`): las secciones de primer nivel, cada
   una con su propio blueprint. Para añadir una nueva (por ejemplo
   "Backtesting"):

   ```python
   App(slug="backtesting", name="Backtesting", icon="🧪", endpoint="backtesting.index", kind="blank"),
   ```

   y crear `app/controllers/backtesting.py` con un blueprint que renderice
   su propia plantilla, registrado en `app/__init__.py`. Con `kind="blank"`
   no hace falta tocar el sidebar: solo aparece el enlace.

2. **Watchlists** (`app/models/watchlists.py`), anidadas dentro de la app
   "Gráficas" (`kind="watchlists"`). Para añadir una nueva sección de
   tickers (por ejemplo "Bancos"):

   ```python
   Watchlist(
       slug="bancos",
       name="Bancos",
       icon="🏦",
       symbols=(
           Symbol("JPM", "JPMorgan"),
           Symbol("BAC", "Bank of America"),
       ),
   ),
   ```

   No hace falta tocar plantillas, controladores ni JavaScript: la nueva
   sección aparece automáticamente en el sidebar, con su propia ruta
   `/graficas/w/bancos` y su propio endpoint `/api/watchlist/bancos/quotes`.

### Análisis de Varianza

Además de la tabla de precios, esta app calcula la **volatilidad mensual
anualizada** (desviación estándar de los retornos diarios dentro de cada
mes calendario, multiplicada por `sqrt(252)`) de uno o varios tickers y
muestra, por cada uno, un histograma con la distribución de esas
volatilidades a lo largo del período elegido. El histograma se genera en
el servidor con **seaborn/matplotlib** (`app/models/analysis.py`) y se
sirve como PNG desde `GET /api/volatility-chart?tickers=AAPL,MSFT&period=5y`.

## Resumen por correo (Resend)

La vista **`/resumen`** es independiente del dashboard: el usuario escribe el
ticker de un activo, el correo de cualquier persona y **su propia API Key de
Resend**, hace click en **"Obtener resumen"** y la app:

1. Descarga el resumen del activo (precio actual, cambio del día, máximo y
   mínimo del día, volumen, máximo/mínimo de 52 semanas y rendimiento de los
   últimos 30 días) reutilizando `app/models/market_data.py`.
2. Lo muestra en pantalla, en una tarjeta junto al formulario.
3. Lo envía por correo en HTML, usando [Resend](https://resend.com) **con la
   API Key que la persona acaba de escribir** (no una key compartida del
   servidor), al correo indicado. Si el envío tiene éxito se muestra el
   mensaje "¡Gracias! Tu resumen ya ha sido enviado a [correo]".

Cada persona trae su propia API Key para que el envío no dependa de (ni
agote) una única key configurada en el servidor, y para que no falle con
"API key is invalid" si esa key compartida no está configurada. La key
viaja solo en la petición de ese envío; el servidor no la guarda ni la
registra en ningún log.

Puedes llegar a esta vista desde el enlace "✉️ Resumen por correo" al pie del
sidebar del dashboard, desde la landing pública, o entrando directamente a
`/resumen`.

### Cómo probarlo

1. Crea una cuenta gratuita en [resend.com](https://resend.com).
2. Ve a **API Keys** y genera una nueva clave (empieza con `re_`).
3. Entra a `/resumen`, escribe un ticker (p. ej. `AAPL`), tu propio correo
   (el mismo con el que creaste la cuenta de Resend) y pega esa API Key en
   el campo "Tu API Key de Resend".
4. Click en "Obtener resumen".

**Importante:** con el remitente de pruebas `onboarding@resend.dev`
(configurado por defecto en `RESEND_FROM`), Resend solo permite enviar
correos al email con el que se creó la cuenta dueña de esa API Key (el
modo "sandbox"). Por eso, con una API Key personal, cada persona solo podrá
enviarse el resumen **a sí misma**. Para poder enviarlo a **cualquier
persona**, quien use esa API Key necesita
[verificar un dominio propio en Resend](https://resend.com/docs/dashboard/domains/introduction)
y la app debería cambiar `RESEND_FROM` por una dirección de ese dominio (por
ejemplo `resumen@tu-dominio.com`).

`RESEND_API_KEY` en `.env` queda como respaldo opcional (solo se usa si
el formulario no trae una API Key), útil para pruebas locales del
desarrollador. Ninguna API key, propia o de respaldo, debe subirse al
repositorio: `.env` está en `.gitignore` y solo `.env.example` (sin
valores reales) se versiona.

## Puesta en marcha

Requiere [uv](https://docs.astral.sh/uv/) y Python 3.12+.

```bash
uv sync                 # instala dependencias (y crea el .venv)
cp .env.example .env    # opcional: ajustar TTLs de caché, etc.
uv run run.py           # http://localhost:5000
```

## Tests

```bash
uv run pytest
```

## Notas

- Los precios se cachean en memoria (`QUOTE_CACHE_TTL` / `CANDLE_CACHE_TTL`
  en `.env`) para no saturar Yahoo Finance; ajusta los valores según lo
  necesites.
- El servidor de desarrollo de Flask no es apto para producción; para
  desplegar, sirve `app` (la factory `create_app()`) con Gunicorn/uWSGI
  detrás de un proxy.
