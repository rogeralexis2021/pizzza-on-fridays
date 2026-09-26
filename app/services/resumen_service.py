"""Servicio: resumen de un activo para la vista "Resumen por correo".

Reutiliza los datos ya cacheados por ``app.models.market_data`` (mismo
proveedor, Yahoo Finance vía ``yfinance``) en vez de volver a hablar con
``yfinance`` directamente.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import market_data

DEFAULT_CURRENCY = "USD"

# Ventana usada para calcular máximo/mínimo de 52 semanas y el rendimiento
# de 30 días; un año de velas diarias cubre ambos cálculos.
_RANGE = "1y"
_INTERVAL = "1d"

_SECONDS_PER_DAY = 86400


def obtener_resumen(ticker: str) -> dict[str, Any]:
    """Devuelve un diccionario con el resumen de ``ticker``.

    Lanza ``ValueError`` (mensaje en español) si el ticker está vacío o si
    Yahoo Finance no devuelve datos para él.
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        raise ValueError("Indica el ticker de un activo.")

    candles = market_data.get_candles(ticker, range_=_RANGE, interval=_INTERVAL)
    if not candles:
        raise ValueError(f'No se encontraron datos para el ticker "{ticker}". Verifica que sea correcto.')

    try:
        quote = market_data.get_quote(ticker)
        nombre = quote.name or ticker
        moneda = quote.currency or DEFAULT_CURRENCY
        cierre_previo_quote = quote.previous_close
    except Exception:
        nombre = ticker
        moneda = DEFAULT_CURRENCY
        cierre_previo_quote = None

    ultimo = candles[-1]
    anterior = candles[-2] if len(candles) > 1 else None

    precio_actual = ultimo["close"]
    cierre_anterior = anterior["close"] if anterior else (cierre_previo_quote or precio_actual)
    cambio_dia = precio_actual - cierre_anterior
    cambio_pct_dia = (cambio_dia / cierre_anterior * 100) if cierre_anterior else 0.0

    maximo_52_semanas = max(c["high"] for c in candles)
    minimo_52_semanas = min(c["low"] for c in candles)

    umbral_30d = ultimo["time"] - 30 * _SECONDS_PER_DAY
    candle_30d = next((c for c in reversed(candles) if c["time"] <= umbral_30d), candles[0])
    rendimiento_30d_pct = (
        (precio_actual - candle_30d["close"]) / candle_30d["close"] * 100 if candle_30d["close"] else 0.0
    )

    fecha_ultimo_dato = datetime.fromtimestamp(ultimo["time"], tz=timezone.utc).strftime("%Y-%m-%d")

    return {
        "ticker": ticker,
        "nombre": nombre,
        "moneda": moneda,
        "fecha_ultimo_dato": fecha_ultimo_dato,
        "precio_actual": round(precio_actual, 4),
        "cambio_dia": round(cambio_dia, 4),
        "cambio_pct_dia": round(cambio_pct_dia, 4),
        "maximo_dia": round(ultimo["high"], 4),
        "minimo_dia": round(ultimo["low"], 4),
        "volumen": ultimo["volume"],
        "maximo_52_semanas": round(maximo_52_semanas, 4),
        "minimo_52_semanas": round(minimo_52_semanas, 4),
        "rendimiento_30d_pct": round(rendimiento_30d_pct, 4),
    }
