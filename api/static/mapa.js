// Tela 1 — mapa de risco + rota segura.
const SVG_NS = "http://www.w3.org/2000/svg";
let META, timer = null;

function svg(tag, attrs) {
  const e = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}

async function iniciar() {
  META = await api("/api/meta");
  const tempo = document.getElementById("tempo");
  tempo.max = META.timestamps.length - 1;
  // começa às 16:30, pouco antes da tempestade, para a demonstração
  const idx = META.timestamps.findIndex(t => hora(t) === "16:30");
  tempo.value = idx >= 0 ? idx : META.timestamps.length - 1;

  for (const id of ["origem", "destino"]) {
    const s = document.getElementById(id);
    META.pontos.forEach(p => s.append(el("option", { value: p.id, text: `${p.nome} (${p.bairro})` })));
  }
  document.getElementById("origem").value = "P1";
  document.getElementById("destino").value = "P6";

  tempo.addEventListener("input", atualizar);
  document.getElementById("origem").addEventListener("change", atualizar);
  document.getElementById("destino").addEventListener("change", atualizar);
  document.getElementById("play").addEventListener("click", alternarPlay);
  atualizar();
}

function alternarPlay() {
  const b = document.getElementById("play"), tempo = document.getElementById("tempo");
  if (timer) { clearInterval(timer); timer = null; b.textContent = "▶ Reproduzir"; b.setAttribute("aria-pressed", "false"); return; }
  b.textContent = "❚❚ Pausar"; b.setAttribute("aria-pressed", "true");
  timer = setInterval(() => {
    if (+tempo.value >= +tempo.max) { alternarPlay(); return; }
    tempo.value = +tempo.value + 1; atualizar();
  }, 400);
}

async function atualizar() {
  const ts = META.timestamps[+document.getElementById("tempo").value];
  const o = document.getElementById("origem").value, d = document.getElementById("destino").value;
  const [est, rota] = await Promise.all([
    api(`/api/estado?ts=${encodeURIComponent(ts)}`),
    api(`/api/rota?origem=${o}&destino=${d}&ts=${encodeURIComponent(ts)}`),
  ]);
  document.getElementById("relogio").textContent = hora(est.ts);
  document.getElementById("disp").textContent = `${est.disponibilidade_pct}% das vias liberadas`;
  desenhar(est, rota.rota_segura.caminho, o, d);
  mostrarRota(rota);
  mostrarAlertas(est);
}

function desenhar(est, caminho, origem, destino) {
  const mapa = document.getElementById("mapa");
  mapa.replaceChildren();
  const pos = Object.fromEntries(META.pontos.map(p => [p.id, p]));
  const risco = Object.fromEntries(est.pontos.map(p => [p.id, p]));
  const bloq = new Set(est.vias_bloqueadas.map(v => [v.a, v.b].sort().join("-")));
  const naRota = new Set(caminho.slice(1).map((p, i) => [caminho[i], p].sort().join("-")));

  for (const v of META.vias) {
    const chave = [v.a, v.b].sort().join("-");
    const a = pos[v.a], b = pos[v.b];
    mapa.append(svg("line", {
      x1: a.x, y1: a.y, x2: b.x, y2: b.y,
      stroke: naRota.has(chave) ? "#38bdf8" : bloq.has(chave) ? "#ef4444" : "#3b4b5e",
      "stroke-width": naRota.has(chave) ? 7 : 4,
      "stroke-dasharray": bloq.has(chave) ? "8 6" : "none", "stroke-linecap": "round",
    }));
  }
  for (const p of META.pontos) {
    const r = risco[p.id]?.risco || "BAIXO";
    const g = svg("g", {});
    const titulo = svg("title", {});
    titulo.textContent = `${p.nome}: risco ${ROTULO[r]}, nível ${risco[p.id]?.nivel_cm} cm`;
    g.append(titulo);
    g.append(svg("circle", { cx: p.x, cy: p.y, r: 16, fill: CORES[r], stroke: "#0f1720", "stroke-width": 3 }));
    if (p.id === origem || p.id === destino) {
      g.append(svg("circle", { cx: p.x, cy: p.y, r: 23, fill: "none", stroke: "#38bdf8", "stroke-width": 3 }));
    }
    const t = svg("text", { x: p.x, y: p.y + 38, "text-anchor": "middle", fill: "#e6edf3", "font-size": 13 });
    t.textContent = p.nome;
    const n = svg("text", { x: p.x, y: p.y + 5, "text-anchor": "middle", fill: "#0b0f14", "font-size": 12, "font-weight": 700 });
    n.textContent = Math.round(risco[p.id]?.nivel_cm ?? 0);
    g.append(t, n);
    mapa.append(g);
  }
}

function mostrarRota(rota) {
  const box = document.getElementById("rota");
  box.replaceChildren();
  const nome = id => META.pontos.find(p => p.id === id).nome;
  const seg = rota.rota_segura, com = rota.rota_comum;
  if (!seg.caminho.length) {
    box.append(el("div", { class: "alerta ALTO", text: `Sem rota segura agora: ${seg.motivo}. Aguarde em local alto e seguro.` }));
    return;
  }
  box.append(el("p", {}, el("strong", { text: "Caminho seguro: " }), seg.caminho.map(nome).join(" → ")));
  box.append(el("p", { class: "muted", text: `Tempo estimado a pé: ${seg.minutos} min` }));
  if (com.caminho.join() !== seg.caminho.join()) {
    box.append(el("div", { class: "alerta", text:
      `O caminho mais curto (${com.caminho.map(nome).join(" → ")}, ${com.minutos} min) passa por área de risco e foi evitado.` }));
  }
}

function mostrarAlertas(est) {
  const box = document.getElementById("alertas");
  box.replaceChildren();
  const ativos = est.pontos.filter(p => p.alerta).sort((a, b) => (b.risco === "ALTO") - (a.risco === "ALTO"));
  if (!ativos.length) { box.append(el("p", { class: "ok", text: "Nenhum alerta ativo. Bom deslocamento!" })); return; }
  ativos.forEach(p => box.append(el("div", { class: `alerta ${p.risco}`, text: p.alerta })));
}

iniciar().catch(e => document.querySelector("main").append(el("p", { class: "erro", text: `Erro: ${e.message}` })));
