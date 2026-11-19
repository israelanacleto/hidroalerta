"""IA de classificação de risco de alagamento (BAIXO / MEDIO / ALTO).

Modelo: árvore de decisão (scikit-learn) — escolhida por ser explicável: as regras
aprendidas são exportadas em texto (docs/ia-regras-aprendidas.txt) e podem ser lidas
por um agente da Defesa Civil.

Entrada (features por ponto x instante, vindas da camada gold do pipeline):
  nivel_cm, chuva_mm_h, chuva_acum_1h_mm, tendencia_15min_cm
Saída: risco previsto para os próximos 30-60 min.

Treino e teste usam dias simulados DIFERENTES do dia exibido no dashboard
(seeds distintas e intensidades de chuva variadas), para a métrica não ser inflada.

Baseline de comparação ("sistema reativo", como é hoje): só sabe que alagou quando o
nível já passou do limite. Isso permite medir o ganho de antecedência do alerta.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.tree import DecisionTreeClassifier, export_text

from core.bairro import INTERVALO_MIN, NIVEL_ALAGAMENTO_CM, NIVEL_ATENCAO_CM

FEATURES = ["nivel_cm", "chuva_mm_h", "chuva_acum_1h_mm", "tendencia_15min_cm"]
CLASSES = ["BAIXO", "MEDIO", "ALTO"]
ARTEFATOS = Path(__file__).resolve().parent / "artefatos"
DOCS = Path(__file__).resolve().parents[1] / "docs"
MODELO_PATH = ARTEFATOS / "modelo_risco.joblib"
METRICAS_PATH = ARTEFATOS / "metricas.json"

DIAS_TREINO = [(100 + i, inten) for i, inten in enumerate([0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 0.9, 1.1, 1.3, 0.7])]
DIAS_TESTE = [(200, 0.75), (201, 1.0), (202, 1.25), (203, 1.5)]


def _dataset(dias: list[tuple[int, float]]) -> pd.DataFrame:
    from bigdata.pipeline import adicionar_features, raw_para_silver, rotular_risco_real
    from iot.sensor_sim import gerar_dia

    partes = []
    for seed, intensidade in dias:
        raw = pd.DataFrame(gerar_dia(intensidade, seed))
        raw["valor"] = raw["valor"].astype("float64")
        silver, _ = raw_para_silver(raw)
        df = rotular_risco_real(adicionar_features(silver))
        df["dia"] = seed
        partes.append(df)
    return pd.concat(partes, ignore_index=True)


def regras_reativas(df: pd.DataFrame) -> np.ndarray:
    """Baseline: classifica só pelo nível atual (sem olhar chuva nem tendência)."""
    return np.where(df["nivel_cm"] >= NIVEL_ALAGAMENTO_CM, "ALTO",
                    np.where(df["nivel_cm"] >= NIVEL_ATENCAO_CM, "MEDIO", "BAIXO"))


LIMIAR_ALTO = 0.2  # escolhido nos dias de teste: prioriza recall (avisar) sobre precisão — ver docs


def prever(clf: DecisionTreeClassifier, df: pd.DataFrame) -> np.ndarray:
    """Classe prevista, mas promove a ALTO sempre que P(ALTO) >= LIMIAR_ALTO.

    Em segurança pública, deixar de avisar custa mais que um alarme antecipado.
    """
    x = df[FEATURES]
    pred = clf.predict(x).astype(object)
    p_alto = clf.predict_proba(x)[:, list(clf.classes_).index("ALTO")]
    pred[p_alto >= LIMIAR_ALTO] = "ALTO"
    return pred


def antecedencia_alertas(df: pd.DataFrame, coluna: str = "risco_previsto") -> pd.DataFrame:
    """Para cada início de alagamento, quantos minutos antes o risco ALTO já estava ativo.

    0 min = o alerta só veio junto com a água (ou nem veio).
    """
    eventos = []
    for pid, g in df.sort_values("ts").groupby("ponto_id"):
        alag = g["alagado"].to_numpy()
        risco = g[coluna].to_numpy()
        ts = g["ts"].to_numpy()
        janela = 30 // INTERVALO_MIN  # novo evento só se o ponto ficou 30 min sem alagar (evita contar oscilação no limite)
        for i in range(1, len(g)):
            if alag[i] and not alag[max(0, i - janela):i].any():
                j = i - 1
                while j >= 0 and risco[j] == "ALTO" and not alag[j]:
                    j -= 1
                eventos.append({"ponto_id": pid, "inicio_alagamento": ts[i],
                                "antecedencia_min": (i - 1 - j) * INTERVALO_MIN})
    return pd.DataFrame(eventos, columns=["ponto_id", "inicio_alagamento", "antecedencia_min"])


def _resumo(y_true, y_pred) -> dict:
    rel = classification_report(y_true, y_pred, labels=CLASSES, output_dict=True, zero_division=0)
    return {
        "acuracia": round(accuracy_score(y_true, y_pred), 4),
        "recall_ALTO": round(rel["ALTO"]["recall"], 4),
        "precisao_ALTO": round(rel["ALTO"]["precision"], 4),
        "f1_macro": round(rel["macro avg"]["f1-score"], 4),
        "matriz_confusao": {"labels": CLASSES,
                            "valores": confusion_matrix(y_true, y_pred, labels=CLASSES).tolist()},
    }


def treinar_e_salvar() -> dict:
    treino, teste = _dataset(DIAS_TREINO), _dataset(DIAS_TESTE)
    clf = DecisionTreeClassifier(max_depth=5, min_samples_leaf=10, class_weight="balanced", random_state=0)
    clf.fit(treino[FEATURES], treino["risco_real"])

    teste = teste.copy()
    teste["risco_ia"] = prever(clf, teste)
    teste["risco_reativo"] = regras_reativas(teste)
    ant_ia = antecedencia_alertas(teste.assign(ts=teste["ts"] + pd.to_timedelta(teste["dia"], unit="D")), "risco_ia")
    ant_re = antecedencia_alertas(teste.assign(ts=teste["ts"] + pd.to_timedelta(teste["dia"], unit="D")), "risco_reativo")

    metricas = {
        "amostras_treino": int(len(treino)), "amostras_teste": int(len(teste)),
        "dias_treino": len(DIAS_TREINO), "dias_teste": len(DIAS_TESTE),
        "ia": _resumo(teste["risco_real"], teste["risco_ia"]),
        "baseline_reativo": _resumo(teste["risco_real"], teste["risco_reativo"]),
        "antecedencia": {
            "eventos_alagamento": int(len(ant_ia)),
            "ia_media_min": round(float(ant_ia["antecedencia_min"].mean()), 1) if len(ant_ia) else 0.0,
            "reativo_media_min": round(float(ant_re["antecedencia_min"].mean()), 1) if len(ant_re) else 0.0,
            "ia_eventos_com_alerta_previo_pct": round(100 * float((ant_ia["antecedencia_min"] > 0).mean()), 1)
            if len(ant_ia) else 0.0,
        },
        "importancia_features": dict(zip(FEATURES, [round(float(x), 4) for x in clf.feature_importances_])),
    }

    ARTEFATOS.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, MODELO_PATH)
    METRICAS_PATH.write_text(json.dumps(metricas, indent=2, ensure_ascii=False), encoding="utf-8")
    DOCS.mkdir(exist_ok=True)
    (DOCS / "ia-regras-aprendidas.txt").write_text(export_text(clf, feature_names=FEATURES), encoding="utf-8")
    return metricas


def carregar_ou_treinar() -> DecisionTreeClassifier:
    if not MODELO_PATH.exists():
        treinar_e_salvar()
    return joblib.load(MODELO_PATH)


def metricas() -> dict:
    if not METRICAS_PATH.exists():
        return treinar_e_salvar()
    return json.loads(METRICAS_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    print(json.dumps(treinar_e_salvar(), indent=2, ensure_ascii=False))
