# PRD enxuto — HidroAlerta & Rota Segura (GS 2026/2 · CitizenTech)

> Status: **rascunho para sign-off** · Prazo de entrega: **19/11/2026, 23h55** (sem prorrogação)
> Janela real de trabalho: ~18h → ~23h (≈5h úteis + 30 min de buffer para zip/upload)
> Base: ideia do Matheus + rubrica do PDF "4ESOA - Global Solution 2026-2"

---

## 1. Problema

Chuva forte em bairros com drenagem crítica alaga vias em minutos. Morador, pedestre e
motorista só descobrem quando já estão na água: não existe alerta antecipado
local nem sugestão de caminho seguro. Resultado: risco físico, carro perdido, horas no trânsito.

- **Cidadão beneficiado:** morador e quem circula por bairro sujeito a alagamento (pedestre,
  motorista, usuário de ônibus, PcD).
- **Ecossistema:** cidadão (recebe alerta / reporta), Defesa Civil / CGE (consome o painel),
  prefeitura (decide manutenção de bueiro/drenagem a partir do histórico).
- **Dado real para abrir o pitch:** ⚠️ *pendente* — buscar 1 número público (ex.: pontos de
  alagamento registrados pelo CGE-SP em um ano). Não inventar.

## 2. Critérios de sucesso (= rubrica)

| Área | Pts | "Pronto" significa |
|---|---|---|
| IA e automação | 4 | Classificador de risco roda sobre dados do pipeline; regras/prompt documentados; exemplo entrada→saída; tabela de acerto + ganho de antecedência |
| Big Data e visualização | 4 | Camadas raw → silver → gold geradas por script; dashboard com 3+ KPIs e filtro por bairro; medidas documentadas (equivalente a DAX) |
| MVP, IoT e experiência | 4 | 4 telas web funcionais; 2 sensores simulados alimentando tudo; fluxo ponta a ponta; diagrama de arquitetura |
| DevOps, segurança, qualidade | 3 | Repo Git por módulos; Dockerfile + compose rodando; workflow CI (GitHub Actions); 2 práticas de segurança; 5+ testes com evidência |
| Vídeo pitch | 5 | ≤ 3 min, site rodando (sem slides), roteiro 0:00/0:30/0:50/2:10/2:40, link público testado em aba anônima |
| Entrega | −1 se falhar | .zip com código + README de execução + PDF de entregáveis + .txt (grupo, RMs, nomes, link do pitch) |

**Regra que manda em tudo:** área que não roda pelo README **zera**. Cada módulo sobe com 1–2 comandos.

## 3. Escopo

### Dentro
- **Bairro fictício** com 8 nós/vias (ex.: "Vila Ribeirão") — não usar mapa real.
- **Sensores simulados (2 obrigatórios):** nível d'água em córrego/bueiro (cm) e pluviômetro (mm/h),
  por ponto do bairro, gerando série temporal com cenário de chuva forte.
- **Pipeline medallion:** `raw/` (leituras brutas JSON) → `silver/` (limpo, tipado, sem outlier/duplicata)
  → `gold/` (agregados por bairro/janela + rótulo de risco).
- **IA:** classificador de risco (BAIXO/MÉDIO/ALTO) — árvore de decisão (scikit-learn) treinada
  em dados simulados rotulados, com fallback por regras explícitas. Alerta em linguagem simples
  gerado por template documentado como "prompt" (LLM opcional, nunca obrigatório para rodar).
- **Rota segura:** grafo do bairro; arestas com risco ALTO são bloqueadas; caminho recalculado (Dijkstra).
- **4 telas:** (1) Mapa de risco + rota segura · (2) Painel de sensores/alertas ·
  (3) Dashboard de indicadores com filtro · (4) Histórico/simulação (disparar cenário de chuva).
- **Segurança (2+):** validação/sanitização de entrada na API (Pydantic) + autenticação simples
  por token nas rotas de escrita (ingestão de sensor / disparo de simulação).
- **Testes:** 5+ casos pytest (validação de leitura, transformação silver, classificação, rota
  bloqueando via alagada, auth negando sem token) + print da execução.

### Fora (cortado de propósito)
- Tela de **Reporte cidadão/Acessibilidade** da proposta original → vira menção de roadmap no pitch.
- Mapa/roteamento real (OSM, Google), app mobile, push notification real, deploy em nuvem, hardware físico.
- LLM como dependência obrigatória (exige chave/API — risco de "não roda pelo README").

## 4. Restrições

- **Prazo:** ~5h de execução. Uma pessoa fazendo as 4 áreas (ver Questões abertas).
- **"Tecnologia fora do conteúdo não pontua":** o PDF não lista a linguagem. Menções explícitas:
  Arduino/TinkerCad/mock (IoT), DAX (funções analíticas), Docker/CI-CD/Jenkins (DevOps), data lake.
- **Uso de IA generativa:** permitido com declaração no README (seção listando ferramentas e para quê);
  proibido entregar código sem entender. Quem apresenta precisa saber explicar cada módulo.
- Ambiente local: Windows, Python 3.10, Docker 29 disponíveis.

## 5. Stack recomendada (assunção — confirmar)

**Python em tudo**, por ser a forma mais rápida de cobrir IoT simulado + pipeline + IA numa linguagem só:

| Camada | Escolha | Por quê |
|---|---|---|
| Sensores | script Python (mock) | Rubrica aceita mock explicitamente |
| Pipeline | pandas, arquivos em pastas raw/silver/gold | Simula data lake sem infra |
| IA | scikit-learn (DecisionTree) + regras | Explicável, métrica fácil (acurácia/matriz de confusão) |
| API | FastAPI + Pydantic | Validação de entrada "de graça" (prática de segurança) |
| Front | HTML/JS estático servido pela API + Chart.js | Sem build step → menos chance de quebrar no README |
| Dashboard | dentro do web app (tela 3); **Power BI opcional** lendo `gold/*.csv` com DAX se der tempo | DAX é citado no PDF; Power BI não roda via Docker, então é bônus, não dependência |
| DevOps | Dockerfile + docker-compose + GitHub Actions (pytest no push) | Cobre "Docker" e "CI/CD" |

Alternativa descartada: Spring Boot + Angular (base do Sutura) — conhecida, mas build mais pesado
e duas linguagens para o mesmo resultado em 5h.

## 6. Arquitetura (alto nível)

```
[sensor_sim.py] --POST /ingest (token)--> [FastAPI]
                                             |
                                       raw/*.json
                                             | pipeline.py
                                       silver/*.csv
                                             | pipeline.py
                                       gold/*.csv ----> [modelo de risco] --> alertas + grafo/rota
                                             |                                   |
                                             +--> GET /kpis  ----------------> [Web: 4 telas]
                                             +--> (opcional) Power BI/DAX
GitHub Actions: push -> pytest -> docker build
```

## 7. Plano (time-box)

| Janela | Entrega | Corte se atrasar |
|---|---|---|
| 18:15–18:45 | Repo + estrutura por módulos + sensor_sim + pipeline raw→gold | — |
| 18:45–19:30 | Modelo de risco + métricas + gerador de alerta + rota (Dijkstra) | Só regras, sem árvore |
| 19:30–20:45 | API + 4 telas + dashboard (3 KPIs + filtro) | Tela 4 vira só botão "simular chuva" |
| 20:45–21:30 | Docker/compose, Actions, 5+ testes, auth por token, prints | Actions só com pytest |
| 21:30–22:15 | Gravar pitch (site rodando) + subir link público | Uma tomada só |
| 22:15–23:15 | PDF de entregáveis, README, .txt, zip, teste do README do zero | — |
| 23:15–23:55 | **Buffer** — enviar até 23:30 | — |

**KPIs do dashboard (proposta):** % de pontos em nível crítico por bairro · índice de disponibilidade
de rotas (vias livres / total) · tempo médio de antecedência do alerta (min antes do pico) ·
nº de alertas por severidade. Filtros: bairro, janela de tempo, severidade.

**Métrica de ganho da IA:** acurácia/recall da classe ALTO no conjunto de teste simulado + antecedência
média do alerta vs. baseline "sem sistema" (descobre na hora = 0 min).

## 8. Questões abertas

1. **Grupo:** são quantos? Se forem 3–5 pessoas, *pelo menos* o PDF de entregáveis, o .txt (RMs) e a
   gravação/edição do pitch devem sair de outra pessoa **em paralelo**. Fazer tudo sozinho em 5h é o maior risco do projeto.
2. **Python foi dado até a fase 7?** Se não, a stack muda (e o plano encolhe).
3. **Power BI** está instalado aqui e entra como bônus, ou fica só o dashboard web?
4. **Quem grava/narra o pitch** e onde sobe (YouTube não listado é o mais seguro)?
5. **Dado real do problema** para os 0:00–0:30 do pitch — alguém do grupo busca, ou eu procuro uma fonte pública?
6. **Repo:** novo repositório no GitHub (necessário para o Actions rodar de verdade) — quem cria e em qual conta?
