// Utilitários compartilhados pelas 4 telas.
const CORES = { BAIXO: "#22c55e", MEDIO: "#f59e0b", ALTO: "#ef4444" };
const ROTULO = { BAIXO: "Baixo", MEDIO: "Médio", ALTO: "Alto" };

async function api(caminho, opcoes) {
  const r = await fetch(caminho, opcoes);
  const corpo = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(corpo.detail ? JSON.stringify(corpo.detail) : `HTTP ${r.status}`);
  return corpo;
}

// Cria elementos sem innerHTML: todo texto vindo da API entra como textContent (evita XSS).
function el(tag, attrs = {}, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v; else if (k === "text") e.textContent = v; else e.setAttribute(k, v);
  }
  for (const f of filhos) e.append(f instanceof Node ? f : document.createTextNode(String(f)));
  return e;
}

function tagRisco(risco) {
  return el("span", { class: `tag ${risco}`, text: ROTULO[risco] || risco });
}

function hora(iso) { return iso.slice(11, 16); }

function marcarNav() {
  const atual = location.pathname;
  document.querySelectorAll("nav a").forEach(a => {
    if (a.getAttribute("href") === atual) { a.classList.add("ativo"); a.setAttribute("aria-current", "page"); }
  });
}
document.addEventListener("DOMContentLoaded", marcarNav);
