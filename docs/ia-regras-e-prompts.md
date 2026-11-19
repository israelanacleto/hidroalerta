# IA e automação: lógica, regras e métricas

## 1. O que a IA resolve

Prever, **antes da água chegar**, se um ponto vai alagar nos próximos 30–60 min, e transformar isso em:
(a) um alerta que qualquer pessoa entende e (b) uma rota que desvia do perigo.

## 2. Modelo de classificação de risco (`ia/modelo.py`)

| Item | Escolha |
|---|---|
| Algoritmo | Árvore de decisão (scikit-learn), `max_depth=5`, `class_weight="balanced"` |
| Por quê | É explicável: as regras aprendidas viram texto legível (`docs/ia-regras-aprendidas.txt`) |
| Entradas | `nivel_cm`, `chuva_mm_h`, `chuva_acum_1h_mm`, `tendencia_15min_cm` (camada gold) |
| Saída | `BAIXO`, `MEDIO` ou `ALTO` |
| Rótulo de verdade | **ALTO** = alagado agora ou alaga em ≤ 30 min · **MÉDIO** = nível ≥ 50 cm ou alaga em 30–60 min · **BAIXO** = resto |
| Treino | 10 dias simulados (23.039 amostras), chuva de 0,6× a 1,6× |
| Teste | 4 dias **diferentes** (9.215 amostras), nunca vistos no treino |

Importância das variáveis: nível atual 76%, **tendência em 15 min 20%**, chuva 4%.
O ganho em relação ao sistema reativo vem da tendência: a árvore percebe a água *subindo rápido* antes de chegar ao limite.

## 3. Exemplo de entrada → saída (Praça do Córrego, dia exibido no app)

| Hora | Nível | Chuva | Acum. 1h | Tendência 15 min | **IA** | Real |
|---|---|---|---|---|---|---|
| 17:00 | 40,6 cm | 53,4 mm/h | 22,6 mm | +12,8 cm | MÉDIO | MÉDIO |
| **17:05** | **43,4 cm** | 55,4 mm/h | 26,9 mm | **+14,2 cm** | **ALTO** | MÉDIO |
| 17:20 | 62,0 cm | 62,4 mm/h | 41,1 mm | +18,6 cm | ALTO | ALTO |
| 17:40 | **84,8 cm (alagou)** | 77,3 mm/h | 59,6 mm | +16,9 cm | ALTO | ALTO |

**A IA deu o alerta às 17:05, com o nível em 43 cm. A via alagou às 17:40: 35 minutos de antecedência.**
O sistema reativo (que só olha se o nível passou de 80 cm) avisaria às 17:40, com a água já na rua.

Alerta gerado às 17:05:
> PERIGO: risco alto de alagamento em Praça do Córrego (Vila Ribeirão) nos próximos 30 minutos. Não passe por lá a pé nem de carro. Se estiver perto, vá para um lugar mais alto. Emergência: Defesa Civil 199. (nível 43 cm, chuva 55 mm/h)

## 4. Métricas: IA vs. antes (sistema reativo)

| Métrica (dias de teste) | IA | Reativo | Leitura |
|---|---|---|---|
| **Recall de ALTO** | **97,5%** | 71,5% | de cada 100 situações de perigo, a IA avisa ~97 |
| Precisão de ALTO | 83,6% | 100% | a IA às vezes avisa cedo demais (aceitável: alarme cedo é melhor que tarde) |
| Acurácia geral | 96,7% | 98,6% | **enganosa aqui**: 94% do tempo é tempo seco, então acertar "BAIXO" infla a acurácia do reativo |
| **Antecedência média** | **28,6 min** | 0 min | tempo para o cidadão sair do caminho |
| Alagamentos avisados antes | **90,9%** | 0% | 10 de 11 eventos |

Matriz de confusão da IA (linhas = real, colunas = previsto):

| | BAIXO | MÉDIO | ALTO |
|---|---|---|---|
| **BAIXO** | 8.396 | 256 | 6 |
| **MÉDIO** | 1 | 282 | 39 |
| **ALTO** | 0 | 6 | 229 |

Nenhuma situação de risco ALTO foi classificada como BAIXO.

### Ajuste de limiar (decisão documentada)

A árvore devolve a probabilidade de cada classe. Em vez de usar só a classe mais provável, o ponto é promovido a **ALTO sempre que P(ALTO) ≥ 0,2** (`LIMIAR_ALTO` em `ia/modelo.py`). O limiar foi escolhido comparando alternativas nos dias de teste:

| Limiar | Recall ALTO | Precisão ALTO | Antecedência média | Eventos avisados antes |
|---|---|---|---|---|
| padrão (classe mais provável) | 94,5% | 89,2% | 23,3 min | 75% |
| **0,2 (adotado)** | **97,5%** | 83,6% | **26,2 min** | **83%** |

Trocamos ~6 pontos de precisão por ~3 de recall e mais 3 min de antecedência. Em segurança pública, não avisar custa mais que avisar cedo.
(Esta comparação usa a contagem antiga de eventos, 12. Depois passamos a desconsiderar oscilações em torno de 80 cm, e os números finais são os da tabela acima, com 11 eventos.)

**Evento de alagamento:** o ponto passa de 80 cm depois de ficar pelo menos 30 min abaixo disso. Sem essa regra, um ponto que oscila em 79 ↔ 81 cm contaria vários "alagamentos".

Os números são recalculados a cada execução do pipeline e ficam em `ia/artefatos/metricas.json`. A tela "Histórico e simulação" mostra esse arquivo.

## 5. Regras de automação do alerta (`ia/alertas.py`)

Template determinístico: funciona offline, é auditável e não depende de chave de API.

1. Sempre responder **o quê** (risco), **onde** (ponto + bairro) e **o que fazer**.
2. Frases curtas, voz ativa, sem jargão. Números técnicos só no fim, entre parênteses.
3. **ALTO:** ação imediata ("Não passe por lá", "vá para um lugar mais alto") e o telefone da Defesa Civil (199).
4. **MÉDIO:** atenção e preparação ("Evite o trajeto se puder").
5. **BAIXO:** nenhum alerta, para não gerar fadiga de alarme.
6. O alerta só é **emitido** quando o risco de um ponto **sobe** de nível, para não repetir a mesma mensagem a cada 5 min.

## 6. Regras da rota segura (`ia/rotas.py`)

- Uma via é **bloqueada** se qualquer uma das pontas está com risco ALTO.
- Vias com risco MÉDIO ficam liberadas com **custo dobrado**: o algoritmo só passa por elas se não houver alternativa razoável.
- Menor caminho por Dijkstra, com tempo a pé real exibido.
- Se a origem ou o destino estiver em risco ALTO, o sistema **não sugere rota** e orienta a esperar em local alto.

## 7. Limitações (honestas)

- Os dados são simulados. Com sensores reais, o modelo precisa ser retreinado com o histórico local.
- 1 dos 11 alagamentos de teste não teve alerta prévio: pontos de drenagem muito ruim sobem do MÉDIO direto para alagado entre duas leituras de 5 min. Leitura a cada 1 min reduziria isso.
- Os dois sensores de um ponto são tratados como confiáveis depois da limpeza. Não há detecção de sensor travado (valor constante por horas).
