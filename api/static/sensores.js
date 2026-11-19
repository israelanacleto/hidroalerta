// Tela 2 — painel de sensores e alertas.
let grafico;

async function iniciar() {
  const meta = await api("/api/meta");
  const sel = document.getElementById("ponto");
  meta.pontos.forEach(p => sel.append(el("option", { value: p.id, text: `${p.nome} (${p.bairro})` })));
  sel.value = "P4";
  sel.addEventListener("change", () => serie(sel.value, meta.nivel_alagamento_cm));
  serie(sel.value, meta.nivel_alagamento_cm);

  const pico = meta.timestamps.find(t => hora(t) === "17:30") || meta.timestamps.at(-1);
  document.getElementById("hora-pico").textContent = hora(pico);
  const est = await api(`/api/estado?ts=${encodeURIComponent(pico)}`);
  const tb = document.querySelector("#tabela tbody");
  est.pontos.forEach(p => tb.append(el("tr", {},
    el("td", { text: p.nome }), el("td", { text: p.bairro }), el("td", { text: p.nivel_cm }),
    el("td", { text: p.chuva_mm_h }), el("td", {}, tagRisco(p.risco)))));

  const al = await api("/api/alertas?limite=8");
  const box = document.getElementById("alertas");
  al.forEach(a => box.append(el("div", { class: `alerta ${a.severidade}` },
    el("strong", { text: `${hora(a.ts)} · ` }), a.alerta)));

  aoVivo();
  setInterval(aoVivo, 2000);
}

async function serie(pontoId, limite) {
  const s = await api(`/api/series?ponto_id=${pontoId}`);
  if (typeof Chart === "undefined") return;
  const dados = {
    labels: s.ts,
    datasets: [
      { label: "Nível d'água (cm)", data: s.nivel_cm, borderColor: "#38bdf8", pointRadius: 0, yAxisID: "y" },
      { label: "Chuva (mm/h)", data: s.chuva_mm_h, borderColor: "#a78bfa", pointRadius: 0, yAxisID: "y2" },
      { label: `Limite de alagamento (${limite} cm)`, data: s.ts.map(() => limite), borderColor: "#ef4444",
        borderDash: [6, 4], pointRadius: 0, yAxisID: "y" },
    ],
  };
  if (grafico) grafico.destroy();
  grafico = new Chart(document.getElementById("grafico"), {
    type: "line", data: dados,
    options: { maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
      plugins: { legend: { labels: { color: "#e6edf3" } } },
      scales: { x: { ticks: { color: "#8b9bab", maxTicksLimit: 12 } },
        y: { title: { display: true, text: "cm", color: "#8b9bab" }, ticks: { color: "#8b9bab" } },
        y2: { position: "right", title: { display: true, text: "mm/h", color: "#8b9bab" },
          ticks: { color: "#8b9bab" }, grid: { drawOnChartArea: false } } } },
  });
}

async function aoVivo() {
  const dados = await api("/api/ao-vivo").catch(() => []);
  const tabela = document.getElementById("vivo"), vazio = document.getElementById("vivo-vazio");
  const comRisco = dados.filter(d => d.risco);
  tabela.hidden = !comRisco.length; vazio.hidden = !!comRisco.length;
  const tb = tabela.querySelector("tbody");
  tb.replaceChildren(...comRisco.map(d => el("tr", {},
    el("td", { text: d.nome }), el("td", { text: d.ts.slice(11, 19) }), el("td", { text: `${d.nivel_cm} cm` }),
    el("td", { text: `${d.chuva_mm_h} mm/h` }), el("td", { text: `${d.tendencia_15min_cm > 0 ? "+" : ""}${d.tendencia_15min_cm} cm` }),
    el("td", {}, tagRisco(d.risco)), el("td", { text: d.alerta || "—" }))));
}

iniciar().catch(e => document.querySelector("main").append(el("p", { class: "erro", text: `Erro: ${e.message}` })));
