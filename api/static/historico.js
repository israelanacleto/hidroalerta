// Tela 4 — histórico, métricas da IA e disparo de simulação.
const NOMES_QUALIDADE = {
  lidas: "Leituras brutas recebidas", removidas_nulas: "Removidas: valor nulo (perda de pacote)",
  removidas_fora_da_faixa: "Removidas: fora da faixa física (negativo / pico espúrio)",
  removidas_duplicadas: "Removidas: duplicadas", lacunas_preenchidas: "Lacunas curtas preenchidas",
  linhas_silver: "Linhas na camada silver (ponto × instante)",
};

async function carregar() {
  const { modelo, qualidade_dados } = await api("/api/metricas");

  document.querySelector("#qualidade tbody").replaceChildren(...Object.entries(qualidade_dados).map(([k, v]) =>
    el("tr", {}, el("td", { text: NOMES_QUALIDADE[k] || k }), el("td", { text: v }))));

  const ia = modelo.ia, re = modelo.baseline_reativo, ant = modelo.antecedencia;
  const pct = x => `${(100 * x).toFixed(1)}%`;
  const linhas = [
    ["Recall de risco ALTO", pct(ia.recall_ALTO), pct(re.recall_ALTO)],
    ["Precisão de risco ALTO", pct(ia.precisao_ALTO), pct(re.precisao_ALTO)],
    ["Acurácia geral", pct(ia.acuracia), pct(re.acuracia)],
    ["Antecedência média do alerta", `${ant.ia_media_min} min`, `${ant.reativo_media_min} min`],
    ["Alagamentos avisados antes", `${ant.ia_eventos_com_alerta_previo_pct}%`, "0%"],
  ];
  document.querySelector("#comparacao tbody").replaceChildren(...linhas.map(l =>
    el("tr", {}, ...l.map(c => el("td", { text: c })))));

  const m = ia.matriz_confusao;
  document.getElementById("matriz").replaceChildren(
    el("thead", {}, el("tr", {}, el("th", { text: "" }), ...m.labels.map(l => el("th", { text: l })))),
    el("tbody", {}, ...m.valores.map((linha, i) => el("tr", {}, el("th", { text: m.labels[i] }),
      ...linha.map(v => el("td", { text: v }))))));
}

document.getElementById("form-sim").addEventListener("submit", async e => {
  e.preventDefault();
  const f = new FormData(e.target), status = document.getElementById("sim-status");
  status.className = "muted"; status.textContent = "Simulando sensores, reprocessando o lake e retreinando a IA…";
  try {
    const r = await api("/api/simular", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Token": f.get("token") },
      body: JSON.stringify({ intensidade: +f.get("intensidade"), seed: +f.get("seed") }),
    });
    status.className = "ok";
    status.textContent = `Pronto: cenário intensidade ${r.intensidade}, semente ${r.seed}. Abra o Mapa ou o Dashboard para ver.`;
    carregar();
  } catch (err) {
    status.className = "erro"; status.textContent = `Falhou: ${err.message}`;
  }
});

carregar().catch(e => document.querySelector("main").append(el("p", { class: "erro", text: `Erro: ${e.message}` })));
