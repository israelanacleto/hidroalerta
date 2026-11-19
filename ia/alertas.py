"""Automação de alertas em linguagem simples e acessível.

Regras documentadas (ver docs/ia-prompts-e-regras.md):
  - Frases curtas, voz ativa, sem jargão técnico ("cm", "mm/h" só como apoio).
  - Sempre: O QUE está acontecendo, ONDE, e O QUE FAZER.
  - ALTO   -> ação imediata (evitar o local, buscar ponto alto, telefone da Defesa Civil 199).
  - MEDIO  -> atenção e preparação.
  - BAIXO  -> sem alerta.
O texto é gerado por template determinístico — funciona offline e é auditável.
"""
from __future__ import annotations

DEFESA_CIVIL = "199"

MODELOS = {
    "ALTO": ("PERIGO: risco alto de alagamento em {local} ({bairro}) nos próximos 30 minutos. "
             "Não passe por lá a pé nem de carro. Se estiver perto, vá para um lugar mais alto. "
             "Emergência: Defesa Civil {tel}."),
    "MEDIO": ("Atenção: a água está subindo em {local} ({bairro}). "
              "Evite o trajeto se puder e fique de olho nos próximos alertas."),
}


def texto_alerta(leitura: dict) -> str:
    risco = leitura.get("risco_previsto") or leitura.get("risco")
    if risco not in MODELOS:
        return ""
    texto = MODELOS[risco].format(local=leitura.get("ponto_nome", leitura.get("ponto_id")),
                                  bairro=leitura.get("bairro", ""), tel=DEFESA_CIVIL)
    nivel, chuva = leitura.get("nivel_cm"), leitura.get("chuva_mm_h")
    if nivel is not None and chuva is not None:
        texto += f" (nível {float(nivel):.0f} cm, chuva {float(chuva):.0f} mm/h)"
    return texto
