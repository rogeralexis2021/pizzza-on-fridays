"""Controlador: API JSON (y de imágenes) que consume el JavaScript del panel."""
from __future__ import annotations

import re

from flask import Blueprint, Response, jsonify, request

from app.models import analysis, market_data
from app.models.watchlists import get_watchlist
from app.services import email_service, resumen_service

bp = Blueprint("api", __name__, url_prefix="/api")

ALLOWED_INTERVALS = {"1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"}
ALLOWED_RANGES = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"}
MAX_VOLATILITY_TICKERS = 6

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@bp.get("/quote/<ticker>")
def quote(ticker: str):
    return jsonify(market_data.get_quote(ticker).to_dict())


@bp.get("/candles/<ticker>")
def candles(ticker: str):
    range_ = request.args.get("range", "6mo")
    interval = request.args.get("interval", "1d")
    if range_ not in ALLOWED_RANGES or interval not in ALLOWED_INTERVALS:
        return jsonify({"error": "range o interval inválidos"}), 400
    return jsonify(market_data.get_candles(ticker, range_, interval))


@bp.get("/watchlist/<slug>/quotes")
def watchlist_quotes(slug: str):
    """Precios de todos los símbolos de una watchlist, para pintar el sidebar."""
    watchlist = get_watchlist(slug)
    if watchlist is None:
        return jsonify({"error": "watchlist no encontrada"}), 404
    quotes = {s.ticker: market_data.get_quote(s.ticker).to_dict() for s in watchlist.symbols}
    return jsonify(quotes)


@bp.get("/volatility-chart")
def volatility_chart():
    """Histograma (PNG) de la volatilidad mensual de uno o varios tickers.

    ?tickers=AAPL,MSFT,GOOG&period=5y
    """
    tickers = [t.strip().upper() for t in request.args.get("tickers", "").split(",") if t.strip()]
    period = request.args.get("period", "5y")

    if not tickers:
        return jsonify({"error": "Indica al menos un ticker"}), 400
    if len(tickers) > MAX_VOLATILITY_TICKERS:
        return jsonify({"error": f"Máximo {MAX_VOLATILITY_TICKERS} tickers a la vez"}), 400
    if period not in ALLOWED_RANGES:
        return jsonify({"error": "period inválido"}), 400

    png_bytes = analysis.render_volatility_histograms(tickers, period)
    return Response(png_bytes, mimetype="image/png")


@bp.post("/resumen")
def resumen():
    """Obtiene el resumen de un activo y lo envía por correo con Resend.

    Body JSON: {"ticker": "AAPL", "correo": "persona@ejemplo.com", "api_key": "re_..."}

    ``api_key`` es la API Key de Resend de quien hace la petición: cada
    persona trae la suya para no depender de (ni agotar) una única key
    configurada en el servidor.
    """
    payload = request.get_json(silent=True) or {}
    ticker = (payload.get("ticker") or "").strip()
    correo = (payload.get("correo") or "").strip()
    api_key = (payload.get("api_key") or "").strip()

    if not ticker:
        return jsonify({"ok": False, "error": "Indica el ticker de un activo."}), 400
    if not correo or not EMAIL_RE.match(correo):
        return jsonify({"ok": False, "error": "Indica un correo electrónico válido."}), 400
    if not api_key:
        return jsonify({"ok": False, "error": "Indica tu API Key de Resend."}), 400

    try:
        datos_resumen = resumen_service.obtener_resumen(ticker)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404

    try:
        email_id = email_service.enviar_resumen(correo, datos_resumen, api_key=api_key)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc), "resumen": datos_resumen}), 502

    return jsonify(
        {
            "ok": True,
            "mensaje": f"¡Gracias! Tu resumen ya ha sido enviado a {correo}",
            "resumen": datos_resumen,
            "email_id": email_id,
        }
    )
