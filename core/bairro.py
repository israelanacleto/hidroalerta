"""Modelo do território simulado: pontos monitorados (nós) e vias (arestas).

Bairros fictícios — não representam um mapa real. Cada ponto tem um par de
sensores (nível d'água + pluviômetro) e um fator de suscetibilidade de drenagem
(quanto maior, mais rápido alaga com a mesma chuva).
"""

PONTOS = {
    # id: (nome, bairro, x, y, suscetibilidade)
    "P1": ("Escola Municipal", "Vila Ribeirão", 80, 80, 0.6),
    "P2": ("Praça do Córrego", "Vila Ribeirão", 260, 120, 1.6),
    "P3": ("Rua das Palmeiras", "Vila Ribeirão", 120, 250, 0.9),
    "P4": ("Ponte Velha", "Jardim Várzea", 420, 90, 1.8),
    "P5": ("Mercado Popular", "Jardim Várzea", 400, 260, 1.2),
    "P6": ("Terminal de Ônibus", "Centro", 600, 120, 0.5),
    "P7": ("UBS Central", "Centro", 580, 300, 0.7),
    "P8": ("Avenida Baixa", "Jardim Várzea", 280, 330, 1.4),
}

# Vias (não direcionadas): (origem, destino, minutos de deslocamento a pé)
VIAS = [
    ("P1", "P2", 6), ("P1", "P3", 5), ("P2", "P4", 5), ("P2", "P5", 7),
    ("P3", "P8", 6), ("P3", "P5", 9), ("P4", "P6", 6), ("P5", "P6", 8),
    ("P5", "P7", 6), ("P8", "P7", 10), ("P6", "P7", 5), ("P8", "P5", 4),
]

BAIRROS = sorted({p[1] for p in PONTOS.values()})

NIVEL_ALAGAMENTO_CM = 80   # acima disso a via no ponto é considerada alagada
NIVEL_ATENCAO_CM = 50
INTERVALO_MIN = 5          # leituras a cada 5 minutos


def bairro_de(ponto_id: str) -> str:
    return PONTOS[ponto_id][1]


def nome_de(ponto_id: str) -> str:
    return PONTOS[ponto_id][0]
