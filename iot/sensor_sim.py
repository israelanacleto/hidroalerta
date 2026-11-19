"""Simulador de sensores IoT (mock) — nível d'água (cm) e pluviômetro (mm/h).

Cada ponto do bairro tem 2 sensores. O simulador gera um dia de leituras a cada
5 minutos com um evento de chuva forte e injeta falhas típicas de campo
(leitura nula, valor negativo, pico espúrio, duplicata) para que a camada
silver do pipeline tenha o que limpar.

Uso:
  python -m iot.sensor_sim                       # gera bigdata/lake/raw/leituras.jsonl
  python -m iot.sensor_sim --intensidade 1.5     # chuva mais forte
  python -m iot.sensor_sim --post http://localhost:8000 --token SEU_TOKEN --passos 30
                                                 # envia leituras ao vivo para a API
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from core.bairro import INTERVALO_MIN, PONTOS

RAIZ = Path(__file__).resolve().parents[1]
RAW_DIR = RAIZ / "bigdata" / "lake" / "raw"
INICIO_PADRAO = datetime(2026, 11, 19, 0, 0)

DECAIMENTO = 0.93     # drenagem: fração do nível que permanece a cada 5 min
GANHO_CHUVA = 0.085   # cm de nível por (mm/h) de chuva, antes da suscetibilidade
NIVEL_BASE = 8.0      # cm em tempo seco


def perfil_chuva(passo: int, intensidade: float, rng: random.Random) -> float:
    """Chuva (mm/h) no passo: garoa de fundo + tempestade principal no fim da tarde."""
    hora = passo * INTERVALO_MIN / 60
    garoa = max(0.0, rng.gauss(1.0, 1.0)) if 6 <= hora <= 10 else 0.0
    tempestade = 70 * intensidade * math.exp(-((hora - 17.5) ** 2) / (2 * 0.6 ** 2))
    pancada = 25 * intensidade * math.exp(-((hora - 13.0) ** 2) / (2 * 0.3 ** 2))
    return max(0.0, garoa + tempestade + pancada)


def gerar_dia(intensidade: float = 1.0, seed: int = 42, inicio: datetime = INICIO_PADRAO,
              falhas: bool = True) -> list[dict]:
    """Gera as leituras brutas (formato do dispositivo) de um dia inteiro."""
    rng = random.Random(seed)
    passos = 24 * 60 // INTERVALO_MIN
    niveis = {pid: NIVEL_BASE for pid in PONTOS}
    leituras: list[dict] = []

    for passo in range(passos):
        ts = (inicio + timedelta(minutes=passo * INTERVALO_MIN)).isoformat()
        chuva_regional = perfil_chuva(passo, intensidade, rng)
        for pid, (_, _, _, _, susc) in PONTOS.items():
            chuva = max(0.0, chuva_regional * rng.uniform(0.85, 1.15))
            niveis[pid] = (NIVEL_BASE + (niveis[pid] - NIVEL_BASE) * DECAIMENTO
                           + chuva * GANHO_CHUVA * susc)
            nivel = niveis[pid] + rng.gauss(0, 1.2)

            for tipo, valor, unidade in (("nivel", nivel, "cm"), ("chuva", chuva, "mm/h")):
                registro = {
                    "sensor_id": f"{pid}-{'NV' if tipo == 'nivel' else 'PL'}",
                    "ponto_id": pid,
                    "tipo": tipo,
                    "valor": round(valor, 2),
                    "unidade": unidade,
                    "ts": ts,
                }
                if falhas:
                    sorteio = rng.random()
                    if sorteio < 0.01:
                        registro["valor"] = None            # perda de pacote
                    elif sorteio < 0.015:
                        registro["valor"] = -abs(registro["valor"] or 1)  # sensor descalibrado
                    elif sorteio < 0.018 and tipo == "nivel":
                        registro["valor"] = 999.0           # pico espúrio
                    elif sorteio < 0.028:
                        leituras.append(dict(registro))     # duplicata
                leituras.append(registro)
    return leituras


def salvar_raw(leituras: list[dict], nome: str = "leituras.jsonl") -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    destino = RAW_DIR / nome
    with destino.open("w", encoding="utf-8") as f:
        for r in leituras:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return destino


def enviar_ao_vivo(url: str, token: str, leituras: list[dict], passos: int, pausa: float) -> None:
    """Envia leituras para POST /api/ingest, simulando o dispositivo em campo."""
    # No Windows, "localhost" tenta IPv6 (::1) primeiro e espera ~2 s por requisição
    # quando o servidor só escuta em IPv4. Usar o IP direto evita a espera.
    url = url.replace("://localhost", "://127.0.0.1")
    por_ts: dict[str, list[dict]] = {}
    for r in leituras:
        if r["valor"] is not None:
            por_ts.setdefault(r["ts"], []).append(r)
    # começa um pouco antes do pico da tempestade para a demo ficar interessante
    chaves = sorted(por_ts)[200:200 + passos]
    for ts in chaves:
        agora = datetime.now().isoformat(timespec="seconds")  # leitura "ao vivo" carimbada com o relógio atual
        for r in por_ts[ts]:
            r = {**r, "ts": agora}
            req = urllib.request.Request(
                f"{url.rstrip('/')}/api/ingest",
                data=json.dumps(r).encode(),
                headers={"Content-Type": "application/json", "X-API-Token": token},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    resp.read()
            except urllib.error.HTTPError as e:
                # leitura com falha de campo (negativa, pico) é barrada pela validação da API
                print(f"[sensor_sim] {r['sensor_id']} valor={r['valor']} recusado pela API: HTTP {e.code}", flush=True)
                if e.code == 401:
                    raise SystemExit("token inválido — confira --token / HIDRO_API_TOKEN")
        print(f"[sensor_sim] enviado passo do cenário {ts[11:16]} como leitura {agora}", flush=True)
        time.sleep(pausa)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--intensidade", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--post", help="URL da API para envio ao vivo")
    ap.add_argument("--token", default="")
    ap.add_argument("--passos", type=int, default=24)
    ap.add_argument("--pausa", type=float, default=1.0)
    args = ap.parse_args()

    leituras = gerar_dia(args.intensidade, args.seed)
    if args.post:
        enviar_ao_vivo(args.post, args.token, leituras, args.passos, args.pausa)
    else:
        destino = salvar_raw(leituras)
        print(f"[sensor_sim] {len(leituras)} leituras brutas -> {destino}")


if __name__ == "__main__":
    main()
