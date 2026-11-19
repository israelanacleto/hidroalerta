// Tela 3 — dashboard com KPIs e filtros (medidas calculadas em GET /api/kpis).
const graficos = {};
const EIXOS = { x: { ticks: { color: "#8b9bab", maxTicksLimit: 10 } }, y: { ticks: { color: "#8b9bab" }, beginAtZero: true } };

function desenharGrafico(id, config) {
  if (typeof Chart === "undefined") return;
  if (graficos[id]) graficos[id].destroy();
  graficos[id] = new Chart(document.getElementById(id), config);
}

async function carregar() {
  const f = new FormData(document.getElementById("filtros"));
  const q = new URLSearchParams([...f].filter(([, v]) => v));
  const [k, al] = await Promise.all([
    api(`/api/kpis?${q}`),
    api(`/api/alertas?${new URLSearchParams([...f].filter(([n, v]) => v && ["bairro", "severidade"].includes(n)))}&limite=200`),
  ]);

  document.getElementById("k-critico").textContent = `${k.pct_leituras_criticas}%`;
  document.getElementById("k-critico-sub").textContent = `${k.pontos_em_nivel_critico} ponto(s) chegaram ao nível crítico`;
  document.getElementById("k-disp").textContent = `${k.disponibilidade_media_pct}%`;
  document.getElementById("k-disp-sub").textContent = `pior momento: ${k.disponibilidade_minima_pct}% das vias`;
  document.getElementById("k-ant").textContent = `${k.antecedencia_media_min} min`;
  document.getElementById("k-ant-sub").textContent = `${k.eventos_alagamento} alagamento(s) · sem o sistema: 0 min`;
  document.getElementById("k-alertas").textContent = k.total_alertas;
  document.getElementById("k-alertas-sub").textContent = `${k.alertas_por_severidade.ALTO} alto · ${k.alertas_por_severidade.MEDIO} médio`;

  desenharGrafico("c-bairro", { type: "bar",
    data: { labels: Object.keys(k.pct_critico_por_bairro),
      datasets: [{ label: "% leituras ≥ 80 cm", data: Object.values(k.pct_critico_por_bairro), backgroundColor: "#ef4444" }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: EIXOS } });
  desenharGrafico("c-disp", { type: "line",
    data: { labels: k.serie_disponibilidade.ts,
      datasets: [{ label: "% vias liberadas", data: k.serie_disponibilidade.pct, borderColor: "#38bdf8", pointRadius: 0, fill: false }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false } },
      scales: { ...EIXOS, y: { ...EIXOS.y, max: 100 } } } });
  desenharGrafico("c-sev", { type: "doughnut",
    data: { labels: ["Médio", "Alto"],
      datasets: [{ data: [k.alertas_por_severidade.MEDIO, k.alertas_por_severidade.ALTO], backgroundColor: ["#f59e0b", "#ef4444"] }] },
    options: { maintainAspectRatio: false, plugins: { legend: { labels: { color: "#e6edf3" } } } } });

  const ini = f.get("inicio") || "00:00", fim = f.get("fim") || "23:59";
  const tb = document.querySelector("#tabela tbody");
  tb.replaceChildren(...al.filter(a => hora(a.ts) >= ini && hora(a.ts) <= fim).map(a => el("tr", {},
    el("td", { text: hora(a.ts) }), el("td", { text: a.ponto }), el("td", { text: a.bairro }),
    el("td", {}, tagRisco(a.severidade)))));
}

async function iniciar() {
  const meta = await api("/api/meta");
  const sel = document.querySelector("select[name=bairro]");
  meta.bairros.forEach(b => sel.append(el("option", { value: b, text: b })));
  document.getElementById("filtros").addEventListener("submit", e => { e.preventDefault(); carregar(); });
  document.getElementById("limpar").addEventListener("click", () => {
    const form = document.getElementById("filtros");
    form.bairro.value = ""; form.severidade.value = ""; form.inicio.value = "00:00"; form.fim.value = "23:55";
    carregar();
  });
  carregar();
}

iniciar().catch(e => document.querySelector("main").append(el("p", { class: "erro", text: `Erro: ${e.message}` })));
