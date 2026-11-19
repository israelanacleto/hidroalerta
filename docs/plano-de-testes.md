# Plano de testes

Automatizados com `pytest` em `tests/test_hidroalerta.py`. Rodam localmente (`python -m pytest -v`) e no CI (GitHub Actions) a cada push.

| ID | Área | Caso | Entrada | Resultado esperado |
|---|---|---|---|---|
| CT01 | IoT | Simulador gera 2 sensores × 8 pontos × dia inteiro | `gerar_dia(seed=1)` | 4.608 leituras, tipos `nivel` e `chuva` |
| CT02 | Big Data | Silver limpa dados sujos | nulo, negativo, pico de 999 cm, duplicata | 1 nulo, 2 fora da faixa e 1 duplicata removidos |
| CT03 | IA | IA supera o sistema reativo | dias de teste | recall ALTO da IA > reativo e ≥ 85%; antecedência > 0 |
| CT04 | IA | Classificação de casos-limite (com limiar P(ALTO) ≥ 0,2) | nível 78 cm subindo 18 cm/15 min · tempo seco | `ALTO` · `BAIXO` |
| CT05 | IA / rota | Rota desvia de ponto em risco ALTO | P1 → P6 com Ponte Velha (P4) em ALTO | caminho sem P4; tempo ≥ rota comum |
| CT06 | IA / alerta | Alerta em linguagem simples | risco ALTO na Ponte Velha | texto com local, "Não passe" e 199; BAIXO = sem alerta |
| CT07 | Segurança | Escrita sem token | `POST /api/ingest` sem token / token errado | HTTP 401 |
| CT08 | Segurança | Validação de entrada (6 variações) | valor −10 e 5000, ponto P9, `<script>`, unidade errada, sensor de outro ponto | HTTP 422 |
| CT09 | Fluxo ponta a ponta | Leitura ao vivo é classificada | chuva 70 mm/h + nível 85 cm em P4 | HTTP 200, risco `ALTO`, aparece em `/api/ao-vivo` |
| CT10 | Dashboard | KPIs e filtros | sem filtro, `bairro=Centro`, bairro com SQL injection, hora 25:99 | 4 KPIs presentes; 200; 422; 422 |
| CT11 | MVP | As 4 telas carregam com cabeçalhos de segurança | `/`, `/sensores`, `/dashboard`, `/historico` | HTTP 200 e `X-Content-Type-Options: nosniff` |

**Total:** 11 casos, 19 execuções (CT08 e CT11 são parametrizados).

## Evidência

- Execução local: [`evidencias/pytest-execucao.txt`](evidencias/pytest-execucao.txt): **19 passed**.
- CI: aba *Actions* do repositório. O relatório JUnit fica publicado como artefato `relatorio-testes`.
