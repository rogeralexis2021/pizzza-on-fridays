"""Controlador de la vista "Resumen por correo": página con el formulario."""
from __future__ import annotations

from flask import Blueprint, render_template

bp = Blueprint("resumen", __name__)


@bp.get("/resumen")
def index():
    return render_template("resumen.html")
