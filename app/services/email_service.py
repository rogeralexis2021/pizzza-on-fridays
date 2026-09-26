"""Servicio: envío del resumen de un activo por correo, usando Resend."""
from __future__ import annotations

from typing import Any

import resend
from flask import current_app

_UP_COLOR = "#26a69a"
_DOWN_COLOR = "#ef5350"


def _fmt(value: Any) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def construir_html_resumen(resumen: dict[str, Any]) -> str:
    """HTML del correo, con estilos inline (compatible con clientes de correo)."""
    is_up = (resumen.get("cambio_dia") or 0) >= 0
    color = _UP_COLOR if is_up else _DOWN_COLOR
    signo = "+" if is_up else ""
    moneda = resumen.get("moneda", "USD")

    filas = [
        ("Fecha del último dato", resumen.get("fecha_ultimo_dato", "—")),
        ("Máximo del día", f"{_fmt(resumen.get('maximo_dia'))} {moneda}"),
        ("Mínimo del día", f"{_fmt(resumen.get('minimo_dia'))} {moneda}"),
        ("Volumen", f"{resumen.get('volumen', 0):,}"),
        ("Máximo 52 semanas", f"{_fmt(resumen.get('maximo_52_semanas'))} {moneda}"),
        ("Mínimo 52 semanas", f"{_fmt(resumen.get('minimo_52_semanas'))} {moneda}"),
        ("Rendimiento 30 días", f"{signo}{_fmt(resumen.get('rendimiento_30d_pct'))}%"),
    ]
    filas_html = "".join(
        f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #232c3a;color:#7c8a9e;font-size:13px;">{etiqueta}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #232c3a;color:#d7dde5;font-size:13px;text-align:right;">{valor}</td>
        </tr>
        """
        for etiqueta, valor in filas
    )

    return f"""
    <div style="background:#0d1117;padding:32px 16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
      <div style="max-width:480px;margin:0 auto;background:#131a24;border:1px solid #232c3a;border-radius:12px;overflow:hidden;">
        <div style="padding:20px 24px;border-bottom:1px solid #232c3a;">
          <p style="margin:0;color:#7c8a9e;font-size:13px;font-weight:600;">{resumen.get('nombre', resumen.get('ticker'))}</p>
          <p style="margin:2px 0 0;color:#d7dde5;font-size:20px;font-weight:700;">{resumen.get('ticker')}</p>
        </div>
        <div style="padding:20px 24px;">
          <p style="margin:0;font-size:32px;font-weight:700;color:#d7dde5;">
            {_fmt(resumen.get('precio_actual'))} {moneda}
          </p>
          <p style="margin:6px 0 0;font-size:15px;font-weight:600;color:{color};">
            {signo}{_fmt(resumen.get('cambio_dia'))} ({signo}{_fmt(resumen.get('cambio_pct_dia'))}%) hoy
          </p>
        </div>
        <table style="width:100%;border-collapse:collapse;">
          {filas_html}
        </table>
        <div style="padding:16px 24px;">
          <p style="margin:0;color:#7c8a9e;font-size:11px;">Datos de Yahoo Finance.</p>
        </div>
      </div>
    </div>
    """


def enviar_resumen(destinatario: str, resumen: dict[str, Any], api_key: str | None = None) -> str:
    """Envía el resumen por correo con Resend y devuelve el id confirmado por su API.

    ``api_key`` es la API Key de Resend de quien solicita el envío (cada persona
    trae la suya, para no depender de una única key del servidor). Si no se
    indica, se usa ``RESEND_API_KEY`` de la configuración como respaldo.
    """
    api_key = (api_key or "").strip() or current_app.config.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("Falta indicar tu API Key de Resend para poder enviar el correo.")

    resend.api_key = api_key
    remitente = current_app.config.get("RESEND_FROM", "onboarding@resend.dev")
    asunto = f"Resumen de {resumen['ticker']}: {_fmt(resumen.get('precio_actual'))} {resumen.get('moneda', 'USD')}"

    respuesta = resend.Emails.send(
        {
            "from": f"Market Dashboard <{remitente}>",
            "to": [destinatario],
            "subject": asunto,
            "html": construir_html_resumen(resumen),
        }
    )

    email_id = respuesta.get("id") if isinstance(respuesta, dict) else getattr(respuesta, "id", None)
    if not email_id:
        raise RuntimeError("Resend no confirmó el envío del correo.")
    return email_id
