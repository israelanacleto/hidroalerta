"""API e front-end do HidroAlerta (FastAPI).

Rotas de leitura são públicas (informação ao cidadão). Rotas de escrita
(ingestão de sensor e disparo de simulação) exigem token no header X-API-Token.

Rodar:  uvicorn api.main:app --reload
"""
from __future__ import annotations

import json
import os
import secrets
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from bigdata import pipeline
from core.bairro import BAIRROS, INTERVALO_MIN, NIVEL_ALAGAMENTO_CM, PONTOS, VIAS
from ia import alertas, modelo, rotas

STATIC = Path(__file__).resolve().parent / "static"
API_TOKEN = os.environ.get("HIDRO_API_TOKEN", "troque-este-token")
PONTO_RE = r"^P[1-8]$"
Severidade = Literal["BAIXO", "MEDIO", "ALTO"]

app = FastAPI(title="HidroAlerta & Rota Segura", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ------------------------------------------------------------------ segurança
@app.middleware("http")
async def cabecalhos_seguranca(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:")
    return resp


def exigir_token(x_api_token: str | None = Header(default=None)) -> None:
    """Controle de acesso: compara em tempo constante para não vazar o token por timing."""
    if not x_api_token or not secrets.compare_digest(x_api_token, API_TOKEN):
        raise HTTPException(status_code=401, detail="token ausente ou inválido")


# ------------------------------------------------------------------ estado em memória
class Estado:
    gold: pd.DataFrame
    alertas: pd.DataFrame
    disponibilidade: pd.DataFrame
    antecedencia: pd.DataFrame
    ao_vivo: dict[str, deque] = {}

    def recarregar(self) -> None:
        gold = pipeline.GOLD
        if not (gold / "leituras_risco.csv").exists():
            pipeline.executar()
        self.gold = pd.read_csv(gold / "leituras_risco.csv", parse_dates=["ts"])
        self.alertas = pd.read_csv(gold / "alertas.csv", parse_dates=["ts"])
        self.disponibilidade = pd.read_csv(gold / "disponibilidade_rotas.csv", parse_dates=["ts"])
        self.antecedencia = pd.read_csv(gold / "antecedencia.csv")
        self.timestamps = sorted(self.gold["ts"].unique())


estado = Estado()
estado.recarregar()


def _resolver_ts(ts: str | None) -> pd.Timestamp:
    if not ts:
        return pd.Timestamp(estado.timestamps[-1])
    try:
        alvo = pd.Timestamp(datetime.fromisoformat(ts))
    except ValueError:
        raise HTTPException(status_code=422, detail="ts deve estar em ISO 8601, ex.: 2026-11-19T17:30:00")
    anteriores = [t for t in estado.timestamps if t <= alvo]
    return pd.Timestamp(anteriores[-1] if anteriores else estado.timestamps[0])


def _foto(ts: pd.Timestamp) -> pd.DataFrame:
    return estado.gold[estado.gold["ts"] == ts]


def _filtrar(df: pd.DataFrame, bairro: str | None, inicio: str | None, fim: str | None) -> pd.DataFrame:
    if bairro:
        df = df[df["bairro"] == bairro]
    if inicio:
        df = df[df["ts"].dt.strftime("%H:%M") >= inicio]
    if fim:
        df = df[df["ts"].dt.strftime("%H:%M") <= fim]
    return df


def _validar_bairro(bairro: str | None) -> str | None:
    if bairro and bairro not in BAIRROS:
        raise HTTPException(status_code=422, detail=f"bairro inválido; use um de {BAIRROS}")
    return bairro


HORA_RE = r"^([01]\d|2[0-3]):[0-5]\d$"


# ------------------------------------------------------------------ páginas
@app.get("/", include_in_schema=False)
def pagina_mapa():
    return FileResponse(STATIC / "index.html")


@app.get("/{pagina}", include_in_schema=False)
def paginas(pagina: Literal["sensores", "dashboard", "historico"]):
    return FileResponse(STATIC / f"{pagina}.html")


# ------------------------------------------------------------------ leitura
@app.get("/api/meta")
def meta():
    return {
        "pontos": [{"id": pid, "nome": n, "bairro": b, "x": x, "y": y} for pid, (n, b, x, y, _) in PONTOS.items()],
        "vias": [{"a": a, "b": b, "minutos": m} for a, b, m in VIAS],
        "bairros": BAIRROS,
        "timestamps": [pd.Timestamp(t).isoformat() for t in estado.timestamps],
        "nivel_alagamento_cm": NIVEL_ALAGAMENTO_CM,
    }


@app.get("/api/estado")
def estado_no_instante(ts: str | None = None):
    t = _resolver_ts(ts)
    foto = _foto(t)
    risco = dict(zip(foto["ponto_id"], foto["risco_previsto"]))
    bloqueadas = rotas.vias_bloqueadas(risco)
    pontos = [{
        "id": r.ponto_id, "nome": r.ponto_nome, "bairro": r.bairro,
        "nivel_cm": round(r.nivel_cm, 1), "chuva_mm_h": round(r.chuva_mm_h, 1),
        "tendencia_15min_cm": round(r.tendencia_15min_cm, 1),
        "risco": r.risco_previsto, "alerta": r.alerta if isinstance(r.alerta, str) else "",
    } for r in foto.itertuples()]
    return {"ts": t.isoformat(), "pontos": pontos,
            "vias_bloqueadas": [{"a": a, "b": b} for a, b in bloqueadas],
            "disponibilidade_pct": round(100 * (1 - len(bloqueadas) / len(VIAS)), 1)}


@app.get("/api/rota")
def rota(origem: str = Query(pattern=PONTO_RE), destino: str = Query(pattern=PONTO_RE), ts: str | None = None):
    t = _resolver_ts(ts)
    foto = _foto(t)
    risco = dict(zip(foto["ponto_id"], foto["risco_previsto"]))
    return {"ts": t.isoformat(),
            "rota_segura": rotas.menor_caminho(origem, destino, risco, evitar_risco=True),
            "rota_comum": rotas.menor_caminho(origem, destino, risco, evitar_risco=False)}


@app.get("/api/series")
def series(ponto_id: str = Query(pattern=PONTO_RE)):
    df = estado.gold[estado.gold["ponto_id"] == ponto_id]
    return {"ponto_id": ponto_id, "nome": PONTOS[ponto_id][0],
            "ts": df["ts"].dt.strftime("%H:%M").tolist(),
            "nivel_cm": df["nivel_cm"].round(1).tolist(),
            "chuva_mm_h": df["chuva_mm_h"].round(1).tolist(),
            "risco": df["risco_previsto"].tolist()}


@app.get("/api/kpis")
def kpis(bairro: str | None = None, severidade: Severidade | None = None,
         inicio: str | None = Query(default=None, pattern=HORA_RE),
         fim: str | None = Query(default=None, pattern=HORA_RE)):
    _validar_bairro(bairro)
    g = _filtrar(estado.gold, bairro, inicio, fim)
    al = _filtrar(estado.alertas, bairro, inicio, fim)
    if severidade:
        al = al[al["severidade"] == severidade]
    disp = estado.disponibilidade.copy()
    if inicio:
        disp = disp[disp["ts"].dt.strftime("%H:%M") >= inicio]
    if fim:
        disp = disp[disp["ts"].dt.strftime("%H:%M") <= fim]
    ant = estado.antecedencia
    if bairro:
        ant = ant[ant["ponto_id"].map(lambda p: PONTOS[p][1]) == bairro]

    critico = (estado.gold.assign(critico=estado.gold["nivel_cm"] >= NIVEL_ALAGAMENTO_CM)
               .pipe(_filtrar, None, inicio, fim)
               .groupby("bairro")["critico"].mean().mul(100).round(1))
    return {
        "filtros": {"bairro": bairro, "severidade": severidade, "inicio": inicio, "fim": fim},
        "pct_leituras_criticas": round(100 * float((g["nivel_cm"] >= NIVEL_ALAGAMENTO_CM).mean()), 1) if len(g) else 0.0,
        "pontos_em_nivel_critico": int(g.loc[g["nivel_cm"] >= NIVEL_ALAGAMENTO_CM, "ponto_id"].nunique()),
        "disponibilidade_media_pct": round(float(disp["disponibilidade_pct"].mean()), 1) if len(disp) else 100.0,
        "disponibilidade_minima_pct": round(float(disp["disponibilidade_pct"].min()), 1) if len(disp) else 100.0,
        "antecedencia_media_min": round(float(ant["antecedencia_min"].mean()), 1) if len(ant) else 0.0,
        "eventos_alagamento": int(len(ant)),
        "total_alertas": int(len(al)),
        "alertas_por_severidade": al["severidade"].value_counts().reindex(["MEDIO", "ALTO"], fill_value=0).to_dict(),
        "pct_critico_por_bairro": {b: float(critico.get(b, 0.0)) for b in BAIRROS},
        "serie_disponibilidade": {"ts": disp["ts"].dt.strftime("%H:%M").tolist(),
                                  "pct": disp["disponibilidade_pct"].tolist()},
    }


@app.get("/api/alertas")
def listar_alertas(bairro: str | None = None, severidade: Severidade | None = None,
                   limite: int = Query(default=50, ge=1, le=500)):
    _validar_bairro(bairro)
    al = _filtrar(estado.alertas, bairro, None, None)
    if severidade:
        al = al[al["severidade"] == severidade]
    al = al.sort_values("ts", ascending=False).head(limite)
    return [{"ts": r.ts.isoformat(), "ponto": r.ponto_nome, "bairro": r.bairro, "severidade": r.severidade,
             "alerta": r.alerta} for r in al.itertuples()]


@app.get("/api/metricas")
def metricas():
    qualidade_path = pipeline.SILVER / "qualidade.json"
    qualidade = json.loads(qualidade_path.read_text(encoding="utf-8")) if qualidade_path.exists() else {}
    return {"modelo": modelo.metricas(), "qualidade_dados": qualidade}


# ------------------------------------------------------------------ escrita (protegida)
class Leitura(BaseModel):
    sensor_id: str = Field(pattern=r"^P[1-8]-(NV|PL)$")
    ponto_id: str = Field(pattern=PONTO_RE)
    tipo: Literal["nivel", "chuva"]
    valor: float = Field(ge=0, le=400)
    unidade: Literal["cm", "mm/h"]
    ts: datetime

    @field_validator("unidade")
    @classmethod
    def unidade_coerente(cls, v, info):
        esperado = {"nivel": "cm", "chuva": "mm/h"}.get(info.data.get("tipo"))
        if esperado and v != esperado:
            raise ValueError(f"unidade deve ser {esperado} para este tipo")
        return v


class PedidoSimulacao(BaseModel):
    intensidade: float = Field(default=1.0, ge=0.3, le=2.0)
    seed: int = Field(default=42, ge=1, le=9999)


@app.post("/api/ingest", dependencies=[Depends(exigir_token)])
def ingerir(leitura: Leitura):
    if not leitura.sensor_id.startswith(leitura.ponto_id + "-"):
        raise HTTPException(status_code=422, detail="sensor_id não pertence ao ponto_id")
    pipeline.RAW.mkdir(parents=True, exist_ok=True)
    with (pipeline.RAW / "ao_vivo.jsonl").open("a", encoding="utf-8") as f:
        f.write(leitura.model_dump_json() + "\n")

    hist = estado.ao_vivo.setdefault(leitura.ponto_id, deque(maxlen=60 // INTERVALO_MIN + 1))
    ultimo = dict(hist[-1]) if hist else {"nivel_cm": None, "chuva_mm_h": 0.0}
    campo = "nivel_cm" if leitura.tipo == "nivel" else "chuva_mm_h"
    if hist and hist[-1].get("_ts") == leitura.ts.isoformat():
        hist[-1][campo] = leitura.valor
    else:
        ultimo.update({campo: leitura.valor, "_ts": leitura.ts.isoformat()})
        hist.append(ultimo)
    return _classificar_ao_vivo(leitura.ponto_id)


def _classificar_ao_vivo(ponto_id: str) -> dict:
    hist = list(estado.ao_vivo.get(ponto_id, []))
    atual = hist[-1] if hist else {}
    if atual.get("nivel_cm") is None:
        return {"ponto_id": ponto_id, "risco": None, "motivo": "aguardando leitura de nível"}
    chuva_acum = sum((h.get("chuva_mm_h") or 0) * INTERVALO_MIN / 60 for h in hist[-(60 // INTERVALO_MIN):])
    anterior = hist[-4]["nivel_cm"] if len(hist) >= 4 and hist[-4].get("nivel_cm") is not None else atual["nivel_cm"]
    linha = pd.DataFrame([{"nivel_cm": atual["nivel_cm"], "chuva_mm_h": atual.get("chuva_mm_h") or 0.0,
                           "chuva_acum_1h_mm": chuva_acum, "tendencia_15min_cm": atual["nivel_cm"] - anterior}])
    risco = str(modelo.prever(modelo.carregar_ou_treinar(), linha)[0])
    nome, bairro = PONTOS[ponto_id][0], PONTOS[ponto_id][1]
    texto = alertas.texto_alerta({"risco": risco, "ponto_nome": nome, "bairro": bairro, **linha.iloc[0].to_dict()})
    atual.update({"risco": risco, "alerta": texto})
    return {"ponto_id": ponto_id, "nome": nome, "bairro": bairro, "ts": atual["_ts"], "risco": risco,
            "alerta": texto, **{k: round(float(v), 1) for k, v in linha.iloc[0].items()}}


@app.get("/api/ao-vivo")
def ao_vivo():
    return [_classificar_ao_vivo(pid) for pid in sorted(estado.ao_vivo)]


@app.post("/api/simular", dependencies=[Depends(exigir_token)])
def simular(pedido: PedidoSimulacao):
    qualidade = pipeline.executar(regerar=True, intensidade=pedido.intensidade, seed=pedido.seed)
    estado.recarregar()
    return {"ok": True, "intensidade": pedido.intensidade, "seed": pedido.seed, "qualidade_dados": qualidade}
