from datetime import datetime, timedelta, timezone

import pytest
import resend

from app.models import analysis, market_data
from app.services import email_service, resumen_service


def _fake_candles(n=40):
    """~40 días de precios diarios sintéticos (sin llamar a Yahoo Finance)."""
    candles = []
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    price = 100.0
    for i in range(n):
        date = start + timedelta(days=i)
        price *= 1.001
        candles.append(
            {
                "time": int(date.timestamp()),
                "open": price * 0.995,
                "high": price * 1.01,
                "low": price * 0.98,
                "close": price,
                "volume": 1000 + i,
            }
        )
    return candles


def _fake_quote(ticker):
    return market_data.Quote(
        symbol=ticker,
        name=f"{ticker} Inc.",
        price=100.0,
        previous_close=95.0,
        change=5.0,
        change_percent=5.26,
        currency="USD",
    )


def _fake_resumen(ticker="AAPL"):
    return {
        "ticker": ticker,
        "nombre": f"{ticker} Inc.",
        "moneda": "USD",
        "fecha_ultimo_dato": "2024-02-09",
        "precio_actual": 232.14,
        "cambio_dia": 4.12,
        "cambio_pct_dia": 1.81,
        "maximo_dia": 235.0,
        "minimo_dia": 230.0,
        "volumen": 123456789,
        "maximo_52_semanas": 250.0,
        "minimo_52_semanas": 150.0,
        "rendimiento_30d_pct": 5.5,
    }


# ---------------------------------------------------------------------
# app/services/resumen_service.py
# ---------------------------------------------------------------------


def test_obtener_resumen_ticker_vacio_lanza_value_error():
    with pytest.raises(ValueError):
        resumen_service.obtener_resumen("   ")


def test_obtener_resumen_sin_datos_lanza_value_error(monkeypatch):
    monkeypatch.setattr(resumen_service.market_data, "get_candles", lambda *a, **k: [])
    with pytest.raises(ValueError):
        resumen_service.obtener_resumen("NOEXISTE")


def test_obtener_resumen_devuelve_los_campos_esperados(monkeypatch):
    monkeypatch.setattr(resumen_service.market_data, "get_candles", lambda *a, **k: _fake_candles())
    monkeypatch.setattr(resumen_service.market_data, "get_quote", _fake_quote)

    resumen = resumen_service.obtener_resumen("aapl")

    assert resumen["ticker"] == "AAPL"
    assert resumen["nombre"] == "AAPL Inc."
    assert resumen["moneda"] == "USD"
    for campo in (
        "fecha_ultimo_dato",
        "precio_actual",
        "cambio_dia",
        "cambio_pct_dia",
        "maximo_dia",
        "minimo_dia",
        "volumen",
        "maximo_52_semanas",
        "minimo_52_semanas",
        "rendimiento_30d_pct",
    ):
        assert campo in resumen


def test_obtener_resumen_usa_valores_por_defecto_si_falla_nombre_o_moneda(monkeypatch):
    monkeypatch.setattr(resumen_service.market_data, "get_candles", lambda *a, **k: _fake_candles())

    def _boom(ticker):
        raise RuntimeError("yfinance no disponible")

    monkeypatch.setattr(resumen_service.market_data, "get_quote", _boom)

    resumen = resumen_service.obtener_resumen("xyz")
    assert resumen["nombre"] == "XYZ"
    assert resumen["moneda"] == "USD"


# ---------------------------------------------------------------------
# app/services/email_service.py
# ---------------------------------------------------------------------


def test_enviar_resumen_llama_a_resend_con_destinatario_asunto_y_html(app, monkeypatch):
    monkeypatch.setattr(analysis.market_data, "get_candles", lambda *a, **k: _fake_candles())
    captured = {}

    def fake_send(payload):
        captured.update(payload)
        return {"id": "email-123"}

    monkeypatch.setattr(resend.Emails, "send", fake_send)
    app.config["RESEND_API_KEY"] = "test-key"
    app.config["RESEND_FROM"] = "onboarding@resend.dev"

    with app.app_context():
        email_id = email_service.enviar_resumen("destino@correo.com", _fake_resumen())

    assert email_id == "email-123"
    assert captured["to"] == ["destino@correo.com"]
    assert captured["from"] == "Market Dashboard <onboarding@resend.dev>"
    assert captured["subject"] == "Resumen de AAPL: 232.14 USD"
    assert "AAPL" in captured["html"]
    assert "data:image/png;base64," in captured["html"]


def test_enviar_resumen_usa_la_api_key_del_usuario_en_vez_de_la_del_servidor(app, monkeypatch):
    monkeypatch.setattr(analysis.market_data, "get_candles", lambda *a, **k: _fake_candles())
    captured = {}
    monkeypatch.setattr(resend.Emails, "send", lambda payload: captured.update({"api_key_usada": resend.api_key}) or {"id": "email-456"})
    app.config["RESEND_API_KEY"] = "key-del-servidor"

    with app.app_context():
        email_service.enviar_resumen("destino@correo.com", _fake_resumen(), api_key="key-del-usuario")

    assert captured["api_key_usada"] == "key-del-usuario"


def test_enviar_resumen_sin_api_key_lanza_error(app):
    app.config["RESEND_API_KEY"] = ""

    with app.app_context():
        with pytest.raises(RuntimeError):
            email_service.enviar_resumen("destino@correo.com", _fake_resumen())


def test_enviar_resumen_sin_id_en_la_respuesta_lanza_error(app, monkeypatch):
    monkeypatch.setattr(analysis.market_data, "get_candles", lambda *a, **k: _fake_candles())
    monkeypatch.setattr(resend.Emails, "send", lambda payload: {})
    app.config["RESEND_API_KEY"] = "test-key"

    with app.app_context():
        with pytest.raises(RuntimeError):
            email_service.enviar_resumen("destino@correo.com", _fake_resumen())


def test_construir_html_resumen_incrusta_el_grafico_como_imagen(monkeypatch):
    monkeypatch.setattr(analysis.market_data, "get_candles", lambda *a, **k: _fake_candles())
    html = email_service.construir_html_resumen(_fake_resumen())
    assert "data:image/png;base64," in html


def test_construir_html_resumen_sin_grafico_si_falla_su_generacion(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("yfinance no disponible")

    monkeypatch.setattr(analysis.market_data, "get_candles", _boom)
    html = email_service.construir_html_resumen(_fake_resumen())
    assert "data:image/png;base64," not in html
    assert "AAPL" in html


# ---------------------------------------------------------------------
# Rutas: GET /resumen y POST /api/resumen
# ---------------------------------------------------------------------


def test_resumen_page_is_reachable(client):
    response = client.get("/resumen")
    assert response.status_code == 200
    assert b'id="resumen-form"' in response.data
    assert b'id="ticker-input"' in response.data
    assert b'id="correo-input"' in response.data
    assert b'id="api-key-input"' in response.data
    assert b'id="resumen-chart-container"' in response.data


def test_api_resumen_ticker_vacio_es_400(client):
    response = client.post(
        "/api/resumen", json={"ticker": "", "correo": "destino@correo.com", "api_key": "re_test_123"}
    )
    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_api_resumen_correo_invalido_es_400(client):
    response = client.post(
        "/api/resumen", json={"ticker": "AAPL", "correo": "no-es-un-correo", "api_key": "re_test_123"}
    )
    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_api_resumen_sin_api_key_es_400(client):
    response = client.post("/api/resumen", json={"ticker": "AAPL", "correo": "destino@correo.com"})
    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_api_resumen_ticker_inexistente_es_404(client, monkeypatch):
    def _fake_obtener_resumen(ticker):
        raise ValueError(f'No se encontraron datos para el ticker "{ticker}".')

    monkeypatch.setattr("app.controllers.api.resumen_service.obtener_resumen", _fake_obtener_resumen)

    response = client.post(
        "/api/resumen", json={"ticker": "NOEXISTE", "correo": "destino@correo.com", "api_key": "re_test_123"}
    )
    assert response.status_code == 404
    assert response.get_json()["ok"] is False


def test_api_resumen_envio_exitoso_devuelve_200_y_mensaje_exacto(client, monkeypatch):
    monkeypatch.setattr("app.controllers.api.resumen_service.obtener_resumen", lambda ticker: _fake_resumen(ticker))

    captured_api_key = {}

    def _fake_enviar_resumen(destinatario, resumen, api_key=None):
        captured_api_key["value"] = api_key
        return "email-123"

    monkeypatch.setattr("app.controllers.api.email_service.enviar_resumen", _fake_enviar_resumen)

    response = client.post(
        "/api/resumen", json={"ticker": "AAPL", "correo": "destino@correo.com", "api_key": "re_test_123"}
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["mensaje"] == "¡Gracias! Tu resumen ya ha sido enviado a destino@correo.com"
    assert payload["email_id"] == "email-123"
    assert payload["resumen"]["ticker"] == "AAPL"
    assert captured_api_key["value"] == "re_test_123"


def test_api_resumen_fallo_de_resend_es_502_sin_mensaje_de_gracias(client, monkeypatch):
    monkeypatch.setattr("app.controllers.api.resumen_service.obtener_resumen", lambda ticker: _fake_resumen(ticker))

    def _fake_enviar_resumen(destinatario, resumen, api_key=None):
        raise RuntimeError("Resend no confirmó el envío del correo.")

    monkeypatch.setattr("app.controllers.api.email_service.enviar_resumen", _fake_enviar_resumen)

    response = client.post(
        "/api/resumen", json={"ticker": "AAPL", "correo": "destino@correo.com", "api_key": "re_test_123"}
    )

    assert response.status_code == 502
    payload = response.get_json()
    assert payload["ok"] is False
    assert "mensaje" not in payload
    assert "Gracias" not in payload.get("error", "")
    assert payload["resumen"]["ticker"] == "AAPL"
