/**
 * Vista "Resumen por correo": envía ticker + correo a la API, muestra el
 * resumen del activo en pantalla y el mensaje de confirmación del envío.
 */
(function () {
  "use strict";

  const form = document.getElementById("resumen-form");
  if (!form) return; // esta página no está montada

  const tickerInput = document.getElementById("ticker-input");
  const correoInput = document.getElementById("correo-input");
  const apiKeyInput = document.getElementById("api-key-input");
  const btn = document.getElementById("resumen-btn");
  const messageEl = document.getElementById("resumen-message");
  const messageIconEl = document.getElementById("resumen-message-icon");
  const messageTextEl = document.getElementById("resumen-message-text");
  const card = document.getElementById("resumen-card");
  const cardName = document.getElementById("card-name");
  const cardTicker = document.getElementById("card-ticker");
  const cardPrice = document.getElementById("card-price");
  const cardChange = document.getElementById("card-change");
  const cardTable = document.getElementById("card-table");
  const chartSection = document.getElementById("resumen-chart-section");
  const chartTitle = document.getElementById("resumen-chart-title");
  const chartContainer = document.getElementById("resumen-chart-container");

  let chart = null;
  let candleSeries = null;

  function ensureChart() {
    if (chart) return;
    chart = LightweightCharts.createChart(chartContainer, {
      layout: { background: { color: "#131a24" }, textColor: "#7c8a9e" },
      grid: { vertLines: { color: "#1b2431" }, horzLines: { color: "#1b2431" } },
      rightPriceScale: { borderColor: "#232c3a" },
      timeScale: { borderColor: "#232c3a", timeVisible: true, secondsVisible: false },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    });
    candleSeries = chart.addCandlestickSeries({
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderVisible: false,
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
    });
    new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      chart.applyOptions({ width, height });
    }).observe(chartContainer);
  }

  function loadChart(ticker) {
    ensureChart();
    chartTitle.textContent = `Evolución de precio · ${ticker} (6 meses)`;

    fetch(`/api/candles/${encodeURIComponent(ticker)}?range=6mo&interval=1d`)
      .then((res) => res.json())
      .then((candles) => {
        if (!Array.isArray(candles) || candles.length === 0) {
          chartSection.hidden = true;
          return;
        }
        candleSeries.setData(candles);
        chartSection.hidden = false;
        chart.timeScale().fitContent();
      })
      .catch(() => {
        chartSection.hidden = true;
      });
  }

  function fmt(value) {
    return Number(value).toLocaleString("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function setMessage(text, type) {
    messageEl.hidden = !text;
    messageEl.classList.remove("is-success", "is-error");
    if (!text) {
      messageIconEl.textContent = "";
      messageTextEl.textContent = "";
      return;
    }
    if (type === "success") {
      messageEl.classList.add("is-success");
      messageIconEl.textContent = "✅";
    } else if (type === "error") {
      messageEl.classList.add("is-error");
      messageIconEl.textContent = "⚠️";
    }
    messageTextEl.textContent = text;
  }

  function addRow(label, value) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    cardTable.appendChild(dt);
    cardTable.appendChild(dd);
  }

  function renderCard(resumen) {
    const moneda = resumen.moneda;
    const isUp = resumen.cambio_dia >= 0;
    const signo = isUp ? "+" : "";

    cardName.textContent = resumen.nombre;
    cardTicker.textContent = resumen.ticker;
    cardPrice.textContent = `${fmt(resumen.precio_actual)} ${moneda}`;
    cardChange.textContent = `${signo}${fmt(resumen.cambio_dia)} (${signo}${fmt(resumen.cambio_pct_dia)}%) hoy`;
    cardChange.classList.toggle("is-up", isUp);
    cardChange.classList.toggle("is-down", !isUp);

    cardTable.replaceChildren();
    addRow("Fecha del último dato", resumen.fecha_ultimo_dato);
    addRow("Máximo del día", `${fmt(resumen.maximo_dia)} ${moneda}`);
    addRow("Mínimo del día", `${fmt(resumen.minimo_dia)} ${moneda}`);
    addRow("Volumen", Number(resumen.volumen).toLocaleString("es-ES"));
    addRow("Máximo 52 semanas", `${fmt(resumen.maximo_52_semanas)} ${moneda}`);
    addRow("Mínimo 52 semanas", `${fmt(resumen.minimo_52_semanas)} ${moneda}`);
    addRow("Rendimiento 30 días", `${resumen.rendimiento_30d_pct >= 0 ? "+" : ""}${fmt(resumen.rendimiento_30d_pct)}%`);

    card.hidden = false;
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();

    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    const ticker = tickerInput.value.trim().toUpperCase();
    const correo = correoInput.value.trim();
    const apiKey = apiKeyInput.value.trim();

    btn.disabled = true;
    btn.textContent = "Enviando...";
    setMessage("", null);

    fetch("/api/resumen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, correo, api_key: apiKey }),
    })
      .then(async (res) => {
        const payload = await res.json().catch(() => ({}));
        return payload;
      })
      .then((payload) => {
        if (payload.resumen) {
          renderCard(payload.resumen);
          loadChart(payload.resumen.ticker);
        }
        if (payload.ok) {
          setMessage(payload.mensaje, "success");
        } else {
          setMessage(payload.error || "Ocurrió un error al procesar la solicitud.", "error");
        }
      })
      .catch(() => {
        setMessage("Ocurrió un error de conexión. Inténtalo de nuevo.", "error");
      })
      .finally(() => {
        btn.disabled = false;
        btn.textContent = "Obtener resumen";
      });
  });
})();
