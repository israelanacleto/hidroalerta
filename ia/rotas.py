"""Rota segura: menor caminho (Dijkstra) evitando vias com risco ALTO.

Uma via é bloqueada se qualquer uma de suas pontas está com risco ALTO.
Vias com risco MEDIO ficam liberadas, mas com custo dobrado (o algoritmo
prefere evitá-las quando houver alternativa razoável).
"""
from __future__ import annotations

import heapq

from core.bairro import PONTOS, VIAS


def vias_bloqueadas(risco: dict[str, str]) -> list[tuple[str, str]]:
    return [(a, b) for a, b, _ in VIAS if risco.get(a) == "ALTO" or risco.get(b) == "ALTO"]


def _grafo(risco: dict[str, str], evitar_risco: bool) -> dict[str, list[tuple[str, float]]]:
    bloqueio = set(vias_bloqueadas(risco)) if evitar_risco else set()
    g: dict[str, list[tuple[str, float]]] = {p: [] for p in PONTOS}
    for a, b, minutos in VIAS:
        if (a, b) in bloqueio:
            continue
        custo = float(minutos)
        if evitar_risco and "MEDIO" in (risco.get(a), risco.get(b)):
            custo *= 2
        g[a].append((b, custo))
        g[b].append((a, custo))
    return g


def menor_caminho(origem: str, destino: str, risco: dict[str, str] | None = None,
                  evitar_risco: bool = True) -> dict:
    """Retorna {'caminho': [...], 'minutos': x} ou caminho vazio se não houver rota segura."""
    risco = risco or {}
    if evitar_risco and (risco.get(origem) == "ALTO" or risco.get(destino) == "ALTO"):
        return {"caminho": [], "minutos": None, "motivo": "origem ou destino em área de risco alto"}
    g = _grafo(risco, evitar_risco)
    dist = {origem: 0.0}
    anterior: dict[str, str] = {}
    fila = [(0.0, origem)]
    while fila:
        d, no = heapq.heappop(fila)
        if no == destino:
            break
        if d > dist.get(no, float("inf")):
            continue
        for viz, custo in g[no]:
            nd = d + custo
            if nd < dist.get(viz, float("inf")):
                dist[viz], anterior[viz] = nd, no
                heapq.heappush(fila, (nd, viz))
    if destino not in dist:
        return {"caminho": [], "minutos": None, "motivo": "nenhuma rota segura disponível"}
    caminho = [destino]
    while caminho[-1] != origem:
        caminho.append(anterior[caminho[-1]])
    caminho.reverse()
    minutos_reais = sum(next(m for a, b, m in VIAS if {a, b} == {x, y}) for x, y in zip(caminho, caminho[1:]))
    return {"caminho": caminho, "minutos": minutos_reais, "motivo": None}
