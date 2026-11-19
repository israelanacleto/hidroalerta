# Dashboard: indicadores, filtros e medidas analíticas

O dashboard (tela `/dashboard`) lê a camada **gold** através de `GET /api/kpis`.
As medidas estão implementadas em Python (`api/main.py`, função `kpis`) e foram escritas com a mesma lógica de medidas DAX.
Abaixo, cada uma com o equivalente DAX, para quem quiser montar o mesmo painel no Power BI a partir de `bigdata/lake/gold/*.csv`.

**Filtros:** bairro · severidade do alerta · janela de horário (início/fim).

| # | Indicador | Decisão que apoia |
|---|---|---|
| 1 | % de leituras em nível crítico, por bairro | Onde priorizar limpeza de bueiro e obra de drenagem |
| 2 | Disponibilidade média (e mínima) de rotas | Quanto da mobilidade do bairro a chuva derruba e quando |
| 3 | Antecedência média do alerta | Se o sistema dá tempo de o cidadão reagir |
| 4 | Alertas emitidos por severidade | Carga operacional da Defesa Civil |

## Medidas (equivalente DAX)

Tabelas: `leituras_risco` (fato ponto × instante), `disponibilidade_rotas`, `alertas`, `antecedencia`.

```dax
Leituras Criticas % =
DIVIDE(
    CALCULATE(COUNTROWS(leituras_risco), leituras_risco[nivel_cm] >= 80),
    COUNTROWS(leituras_risco)
)

Pontos em Nivel Critico =
CALCULATE(DISTINCTCOUNT(leituras_risco[ponto_id]), leituras_risco[nivel_cm] >= 80)

Disponibilidade Media % = AVERAGE(disponibilidade_rotas[disponibilidade_pct])

Disponibilidade Minima % = MIN(disponibilidade_rotas[disponibilidade_pct])

Antecedencia Media (min) = AVERAGE(antecedencia[antecedencia_min])

Alertas Emitidos = COUNTROWS(alertas)

Alertas Alto = CALCULATE([Alertas Emitidos], alertas[severidade] = "ALTO")

Ganho de Antecedencia vs Reativo (min) = [Antecedencia Media (min)] - 0
    -- sistema reativo só avisa quando a via já alagou (antecedência 0)
```

Equivalente em Python (trecho de `api/main.py`):

```python
pct_criticas  = (g["nivel_cm"] >= 80).mean() * 100
disp_media    = disp["disponibilidade_pct"].mean()
antecedencia  = ant["antecedencia_min"].mean()
por_severidade = alertas["severidade"].value_counts()
critico_bairro = gold.assign(c=gold.nivel_cm >= 80).groupby("bairro")["c"].mean() * 100
```

## Leitura do dia simulado (dia inteiro, todos os bairros)

Os valores exibidos no dashboard saem da gold atual. Tire o print depois de rodar o pipeline, para garantir que batem com o código entregue.
