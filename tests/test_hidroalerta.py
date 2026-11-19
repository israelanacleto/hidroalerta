"""Plano de testes automatizado (ver docs/plano-de-testes.md para a descrição de cada caso)."""
import os

os.environ.setdefault("HIDRO_API_TOKEN", "token-de-teste")

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from bigdata.pipeline import adicionar_features, raw_para_silver, rotular_risco_real
from ia import alertas, modelo, rotas
from iot.sensor_sim import gerar_dia

TOKEN = os.environ["HIDRO_API_TOKEN"]


@pytest.fixture(scope="module")
def client():
    from api.main import app
    return TestClient(app)


def _leitura(**over):
    base = {"sensor_id": "P4-NV", "ponto_id": "P4", "tipo": "nivel", "valor": 60.0,
            "unidade": "cm", "ts": "2026-11-19T18:00:00"}
    return {**base, **over}


# CT01 — IoT: o simulador gera os 2 tipos de sensor para os 8 pontos, o dia inteiro
def test_ct01_simulador_gera_dois_sensores_por_ponto():
    df = pd.DataFrame(gerar_dia(seed=1, falhas=False))
    assert set(df["tipo"]) == {"nivel", "chuva"}
    assert df["ponto_id"].nunique() == 8
    assert len(df) == 8 * 2 * 288


# CT02 — Big Data: a camada silver remove nulos, negativos, picos e duplicatas
def test_ct02_silver_limpa_dados_sujos():
    raw = pd.DataFrame([
        {"sensor_id": "P1-NV", "ponto_id": "P1", "tipo": "nivel", "valor": 10.0, "unidade": "cm", "ts": "2026-11-19T00:00:00"},
        {"sensor_id": "P1-NV", "ponto_id": "P1", "tipo": "nivel", "valor": 10.0, "unidade": "cm", "ts": "2026-11-19T00:00:00"},
        {"sensor_id": "P1-PL", "ponto_id": "P1", "tipo": "chuva", "valor": None, "unidade": "mm/h", "ts": "2026-11-19T00:00:00"},
        {"sensor_id": "P1-PL", "ponto_id": "P1", "tipo": "chuva", "valor": -5.0, "unidade": "mm/h", "ts": "2026-11-19T00:05:00"},
        {"sensor_id": "P1-NV", "ponto_id": "P1", "tipo": "nivel", "valor": 999.0, "unidade": "cm", "ts": "2026-11-19T00:05:00"},
        {"sensor_id": "P1-PL", "ponto_id": "P1", "tipo": "chuva", "valor": 3.0, "unidade": "mm/h", "ts": "2026-11-19T00:10:00"},
        {"sensor_id": "P1-NV", "ponto_id": "P1", "tipo": "nivel", "valor": 12.0, "unidade": "cm", "ts": "2026-11-19T00:10:00"},
    ])
    raw["valor"] = raw["valor"].astype("float64")
    silver, q = raw_para_silver(raw)
    assert q["removidas_nulas"] == 1
    assert q["removidas_fora_da_faixa"] == 2
    assert q["removidas_duplicadas"] == 1
    assert silver["nivel_cm"].max() < 400 and silver["chuva_mm_h"].min() >= 0


# CT03 — IA: o modelo supera o sistema reativo no recall de risco ALTO e dá antecedência
def test_ct03_ia_supera_baseline_reativo():
    m = modelo.metricas()
    assert m["ia"]["recall_ALTO"] > m["baseline_reativo"]["recall_ALTO"]
    assert m["ia"]["recall_ALTO"] >= 0.85
    assert m["antecedencia"]["ia_media_min"] > m["antecedencia"]["reativo_media_min"]


# CT04 — IA: rótulo e previsão — chuva forte com nível subindo rápido é ALTO
def test_ct04_classifica_situacao_de_perigo():
    clf = modelo.carregar_ou_treinar()
    perigo = pd.DataFrame([{"nivel_cm": 78, "chuva_mm_h": 70, "chuva_acum_1h_mm": 50, "tendencia_15min_cm": 18}])
    seco = pd.DataFrame([{"nivel_cm": 9, "chuva_mm_h": 0, "chuva_acum_1h_mm": 0, "tendencia_15min_cm": 0}])
    assert modelo.prever(clf, perigo)[0] == "ALTO"
    assert modelo.prever(clf, seco)[0] == "BAIXO"


# CT05 — Rota: a rota segura desvia de ponto com risco ALTO
def test_ct05_rota_desvia_de_via_alagada():
    comum = rotas.menor_caminho("P1", "P6", {}, evitar_risco=False)
    assert "P4" in comum["caminho"]                      # caminho curto passa pela Ponte Velha
    segura = rotas.menor_caminho("P1", "P6", {"P4": "ALTO"})
    assert segura["caminho"] and "P4" not in segura["caminho"]
    assert segura["minutos"] >= comum["minutos"]


# CT06 — Alerta: texto em linguagem simples, com local e orientação
def test_ct06_alerta_linguagem_simples():
    txt = alertas.texto_alerta({"risco": "ALTO", "ponto_nome": "Ponte Velha", "bairro": "Jardim Várzea",
                                "nivel_cm": 90, "chuva_mm_h": 60})
    assert "Ponte Velha" in txt and "199" in txt and "Não passe" in txt
    assert alertas.texto_alerta({"risco": "BAIXO"}) == ""


# CT07 — Segurança: escrita sem token é recusada (401)
def test_ct07_ingest_sem_token_recusado(client):
    assert client.post("/api/ingest", json=_leitura()).status_code == 401
    assert client.post("/api/ingest", json=_leitura(), headers={"X-API-Token": "errado"}).status_code == 401


# CT08 — Segurança: validação de entrada rejeita dados inválidos/maliciosos (422)
@pytest.mark.parametrize("ruim", [
    _leitura(valor=-10), _leitura(valor=5000), _leitura(ponto_id="P9"),
    _leitura(sensor_id="<script>alert(1)</script>"), _leitura(unidade="mm/h"),
    _leitura(sensor_id="P1-NV"),  # sensor de outro ponto
])
def test_ct08_validacao_de_entrada(client, ruim):
    r = client.post("/api/ingest", json=ruim, headers={"X-API-Token": TOKEN})
    assert r.status_code == 422


# CT09 — Fluxo ponta a ponta: leitura válida entra, é classificada e aparece no painel ao vivo
def test_ct09_fluxo_ingest_classifica(client):
    h = {"X-API-Token": TOKEN}
    assert client.post("/api/ingest", json=_leitura(tipo="chuva", sensor_id="P4-PL", unidade="mm/h", valor=70), headers=h).status_code == 200
    r = client.post("/api/ingest", json=_leitura(valor=85), headers=h)
    assert r.status_code == 200 and r.json()["risco"] == "ALTO"
    assert any(p["ponto_id"] == "P4" for p in client.get("/api/ao-vivo").json())


# CT10 — Dashboard: KPIs respondem e filtros são validados
def test_ct10_kpis_e_filtros(client):
    k = client.get("/api/kpis").json()
    for campo in ("pct_leituras_criticas", "disponibilidade_media_pct", "antecedencia_media_min", "total_alertas"):
        assert campo in k
    assert client.get("/api/kpis", params={"bairro": "Centro"}).status_code == 200
    assert client.get("/api/kpis", params={"bairro": "'; DROP TABLE x;--"}).status_code == 422
    assert client.get("/api/kpis", params={"inicio": "25:99"}).status_code == 422


# CT11 — Telas: as 4 telas carregam com cabeçalhos de segurança
@pytest.mark.parametrize("pagina", ["/", "/sensores", "/dashboard", "/historico"])
def test_ct11_telas_carregam(client, pagina):
    r = client.get(pagina)
    assert r.status_code == 200 and "HidroAlerta" in r.text
    assert r.headers["X-Content-Type-Options"] == "nosniff"
