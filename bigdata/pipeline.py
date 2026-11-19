"""Pipeline do data lake em camadas: raw (bronze) -> silver (trusted) -> gold (refined).

  raw/    leituras brutas dos sensores (JSON Lines, uma leitura por linha, como o dispositivo envia)
  silver/ dado limpo e tipado: sem nulos, negativos, picos espúrios e duplicatas;
          uma linha por ponto x instante, com nível e chuva lado a lado
  gold/   dado pronto para decisão: features, risco previsto pela IA, alertas,
          disponibilidade de rotas e indicadores agregados por bairro

Uso:
  python -m bigdata.pipeline              # gera raw (se não existir), silver, gold e treina a IA
  python -m bigdata.pipeline --regerar    # força nova simulação dos sensores
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from core.bairro import NIVEL_ALAGAMENTO_CM, NIVEL_ATENCAO_CM, PONTOS, INTERVALO_MIN
from iot import sensor_sim

LAKE = Path(__file__).resolve().parent / "lake"
RAW, SILVER, GOLD = LAKE / "raw", LAKE / "silver", LAKE / "gold"

LIMITES = {"nivel": (0.0, 400.0), "chuva": (0.0, 300.0)}  # faixas fisicamente plausíveis
PASSOS_30MIN = 30 // INTERVALO_MIN
PASSOS_60MIN = 60 // INTERVALO_MIN


# ---------------------------------------------------------------- raw -> silver
def carregar_raw(caminho: Path) -> pd.DataFrame:
    return pd.read_json(caminho, lines=True, dtype={"valor": "float64"})


def raw_para_silver(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    qualidade = {"lidas": int(len(raw))}
    df = raw.copy()

    df = df[df["ponto_id"].isin(PONTOS) & df["tipo"].isin(LIMITES)]
    nulos = df["valor"].isna()
    qualidade["removidas_nulas"] = int(nulos.sum())
    df = df[~nulos]

    fora = pd.Series(False, index=df.index)
    for tipo, (lo, hi) in LIMITES.items():
        m = df["tipo"] == tipo
        fora |= m & ((df["valor"] < lo) | (df["valor"] > hi))
    qualidade["removidas_fora_da_faixa"] = int(fora.sum())
    df = df[~fora]

    antes = len(df)
    df = df.drop_duplicates(subset=["sensor_id", "ts"])
    qualidade["removidas_duplicadas"] = int(antes - len(df))

    df["ts"] = pd.to_datetime(df["ts"])
    silver = (df.pivot_table(index=["ponto_id", "ts"], columns="tipo", values="valor", aggfunc="mean")
                .rename(columns={"nivel": "nivel_cm", "chuva": "chuva_mm_h"})
                .reset_index())
    silver.columns.name = None

    # completa a grade ponto x instante e preenche lacunas curtas (até 2 leituras) com a anterior
    grade = pd.MultiIndex.from_product(
        [sorted(PONTOS), pd.date_range(silver["ts"].min(), silver["ts"].max(), freq=f"{INTERVALO_MIN}min")],
        names=["ponto_id", "ts"])
    silver = silver.set_index(["ponto_id", "ts"]).reindex(grade).reset_index()
    lacunas = int(silver[["nivel_cm", "chuva_mm_h"]].isna().any(axis=1).sum())
    silver[["nivel_cm", "chuva_mm_h"]] = (silver.groupby("ponto_id")[["nivel_cm", "chuva_mm_h"]]
                                           .ffill(limit=2))
    silver = silver.dropna(subset=["nivel_cm", "chuva_mm_h"])
    qualidade["lacunas_preenchidas"] = lacunas
    qualidade["linhas_silver"] = int(len(silver))

    silver["bairro"] = silver["ponto_id"].map(lambda p: PONTOS[p][1])
    silver["ponto_nome"] = silver["ponto_id"].map(lambda p: PONTOS[p][0])
    return silver.sort_values(["ponto_id", "ts"]).reset_index(drop=True), qualidade


# ---------------------------------------------------------------- silver -> gold
def adicionar_features(silver: pd.DataFrame) -> pd.DataFrame:
    df = silver.sort_values(["ponto_id", "ts"]).copy()
    g = df.groupby("ponto_id")
    # mm/h amostrado a cada 5 min -> mm acumulados na última hora
    df["chuva_acum_1h_mm"] = g["chuva_mm_h"].transform(
        lambda s: (s * INTERVALO_MIN / 60).rolling(PASSOS_60MIN, min_periods=1).sum())
    df["tendencia_15min_cm"] = g["nivel_cm"].transform(lambda s: s.diff(3).fillna(0))
    df["alagado"] = df["nivel_cm"] >= NIVEL_ALAGAMENTO_CM
    return df


def rotular_risco_real(df: pd.DataFrame) -> pd.DataFrame:
    """Rótulo de verdade (só possível olhando o futuro — usado para treinar e medir a IA).

    ALTO  : o ponto está alagado agora ou vai alagar nos próximos 30 min
    MEDIO : nível de atenção agora ou vai alagar entre 30 e 60 min
    BAIXO : caso contrário
    """
    df = df.sort_values(["ponto_id", "ts"]).copy()
    g = df.groupby("ponto_id")["alagado"]

    def futuro(s: pd.Series, passos: int) -> pd.Series:
        return s[::-1].astype(int).rolling(passos + 1, min_periods=1).max()[::-1].astype(bool)

    alaga_30 = g.transform(lambda s: futuro(s, PASSOS_30MIN))
    alaga_60 = g.transform(lambda s: futuro(s, PASSOS_60MIN))
    df["risco_real"] = "BAIXO"
    df.loc[(df["nivel_cm"] >= NIVEL_ATENCAO_CM) | alaga_60, "risco_real"] = "MEDIO"
    df.loc[df["alagado"] | alaga_30, "risco_real"] = "ALTO"
    return df


def construir_gold(features: pd.DataFrame) -> dict[str, pd.DataFrame]:
    from ia import alertas, modelo, rotas

    clf = modelo.carregar_ou_treinar()
    df = features.copy()
    df["risco_previsto"] = modelo.prever(clf, df)
    df["alerta"] = [alertas.texto_alerta(r) for r in df.to_dict("records")]

    # disponibilidade de rotas: % de vias liberadas em cada instante
    disp = []
    for ts, grupo in df.groupby("ts"):
        risco = dict(zip(grupo["ponto_id"], grupo["risco_previsto"]))
        bloqueadas = rotas.vias_bloqueadas(risco)
        disp.append({"ts": ts, "vias_bloqueadas": len(bloqueadas),
                     "disponibilidade_pct": round(100 * (1 - len(bloqueadas) / len(rotas.VIAS)), 1)})
    disponibilidade = pd.DataFrame(disp)

    # alertas emitidos: toda vez que o risco previsto de um ponto sobe de nível
    ordem = {"BAIXO": 0, "MEDIO": 1, "ALTO": 2}
    df["_nivel"] = df["risco_previsto"].map(ordem)
    subiu = df.groupby("ponto_id")["_nivel"].diff().fillna(0) > 0
    alertas_df = df.loc[subiu, ["ts", "ponto_id", "ponto_nome", "bairro", "risco_previsto",
                                "nivel_cm", "chuva_mm_h", "alerta"]].rename(columns={"risco_previsto": "severidade"})
    df = df.drop(columns="_nivel")

    antecedencias = modelo.antecedencia_alertas(df)
    return {"leituras_risco": df, "disponibilidade_rotas": disponibilidade,
            "alertas": alertas_df, "antecedencia": antecedencias}


def executar(regerar: bool = False, intensidade: float = 1.0, seed: int = 42) -> dict:
    from ia import modelo

    raw_path = RAW / "leituras.jsonl"
    if regerar or not raw_path.exists():
        sensor_sim.salvar_raw(sensor_sim.gerar_dia(intensidade, seed))

    silver, qualidade = raw_para_silver(carregar_raw(raw_path))
    SILVER.mkdir(parents=True, exist_ok=True)
    silver.to_csv(SILVER / "leituras.csv", index=False)
    (SILVER / "qualidade.json").write_text(json.dumps(qualidade, indent=2, ensure_ascii=False), encoding="utf-8")

    modelo.treinar_e_salvar()  # treina em outros dias simulados (seeds diferentes)

    features = rotular_risco_real(adicionar_features(silver))
    gold = construir_gold(features)
    GOLD.mkdir(parents=True, exist_ok=True)
    for nome, tabela in gold.items():
        tabela.to_csv(GOLD / f"{nome}.csv", index=False)
    print(f"[pipeline] qualidade: {qualidade}")
    print(f"[pipeline] gold: {', '.join(f'{k}={len(v)}' for k, v in gold.items())}")
    return qualidade


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--regerar", action="store_true")
    ap.add_argument("--intensidade", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    executar(a.regerar, a.intensidade, a.seed)
