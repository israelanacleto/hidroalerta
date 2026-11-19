# Guia do grupo: PDF de entregáveis, pitch e .txt

## Checklist da entrega (−1 ponto por item faltando)

- [ ] `.zip` com o código (esta pasta **sem** `.venv/`) + README
- [ ] PDF de entregáveis (roteiro abaixo)
- [ ] `integrantes.txt`: nome do grupo, RM e nome de cada integrante, **link do pitch**
- [ ] Link do pitch também no `README.md` (linha "Vídeo pitch")
- [ ] Link testado em **aba anônima**
- [ ] Seção "Uso de IA generativa" do README preenchida
- [ ] Enviado até **19/11, 23h55** (meta: 23h30)

## Roteiro do PDF (uma seção por área da rubrica)

1. **Capa:** nome do projeto, grupo, integrantes e RMs, link do pitch.
2. **Problema e cidadão:** quem é beneficiado, o problema, ODS 11/13/9 e como contribuímos. Ecossistema: cidadão, Defesa Civil/CGE e prefeitura.
3. **Arquitetura:** diagrama de `docs/arquitetura.md`. Renderizar o mermaid em https://mermaid.live e exportar PNG.
4. **MVP, IoT e experiência digital (4 pts):**
   - print das 4 telas
   - print do terminal rodando `python -m iot.sensor_sim --post ...` + print da tabela "Ao vivo" preenchida
   - fluxo ponta a ponta: chuva começa → sensor sobe → IA marca ALTO → via bloqueada → rota recalculada (sequência de 3 prints do mapa em 16:30, 17:10 e 17:45)
5. **IA e automação (4 pts):** copiar de `docs/ia-regras-e-prompts.md` a tabela de entrada/saída, as regras do alerta, a tabela de métricas e a matriz de confusão. Incluir print da tela "Histórico e simulação".
6. **Big Data e visualização (4 pts):**
   - estrutura do lake: print das pastas `bigdata/lake/raw`, `silver`, `gold`
   - ingestão e processamento: print do terminal com `python -m bigdata.pipeline --regerar` + tabela de qualidade (raw → silver)
   - dashboard: print com filtro aplicado (ex.: bairro "Jardim Várzea", 16:00–20:00)
   - medidas: copiar de `docs/dashboard-medidas.md`
7. **DevOps, segurança e qualidade (3 pts):**
   - print do repositório no GitHub (estrutura por módulos + commits)
   - print do `docker compose up` rodando e/ou da aba Actions verde
   - segurança: seção do README + print do 401 sem token
   - testes: tabela de `docs/plano-de-testes.md` + print de `python -m pytest -v` (19 passed)

## Roteiro do pitch (≤ 3:00, sem slides, site rodando)

| Tempo | O que mostrar | Fala (sugestão) |
|---|---|---|
| 0:00–0:30 | Problema (pode ter 1 imagem de rua alagada + dado real) | "Toda chuva forte, alguém descobre que a rua alagou quando já está dentro da água. `<<dado real: nº de pontos de alagamento / ano na cidade>>`." |
| 0:30–0:50 | Tela do mapa às 16:30, tudo verde | "O HidroAlerta usa sensores de nível d'água e chuva para prever o alagamento antes de acontecer e desviar o cidadão do perigo." |
| 0:50–1:30 | Mapa: dar ▶ Reproduzir; pontos ficam laranja e vermelhos; rota muda; alerta aparece | "Às 17:05 a IA já marcou a Praça do Córrego como risco alto, com 43 cm. A rua só alagou às 17:40: foram 35 minutos de antecedência. A rota desviou sozinha." |
| 1:30–1:50 | Sensores: terminal enviando leituras ao vivo + tabela "Ao vivo" | "Esses são os sensores enviando dados agora; cada leitura é classificada na hora." |
| 1:50–2:10 | Dashboard com filtro de bairro + tela de métricas | "A Defesa Civil vê onde a drenagem falha. A IA avisa 97% das situações de perigo, em média 28 minutos antes; o sistema de hoje avisa 71%, e sempre com a rua já alagada." |
| 2:10–2:40 | Voltar ao mapa com rota segura | "Quem ganha: o morador, o pedestre e quem depende de ônibus. ODS 11, 13 e 9." |
| 2:40–3:00 | Fechamento | "Próximo passo: reporte do cidadão e rotas acessíveis para PcD. HidroAlerta: o aviso que chega antes da água." |

Dica: deixe o app aberto e o sensor ao vivo pronto **antes** de gravar. Grave a tela em 1080p (OBS ou Xbox Game Bar: Win+G) e suba no YouTube como **não listado**.

## `integrantes.txt` (modelo)

```
Grupo: <<nome do grupo>>
Projeto: HidroAlerta & Rota Segura

RM00000 - Nome Completo
RM00000 - Nome Completo
RM00000 - Nome Completo
RM00000 - Nome Completo

Vídeo pitch: <<link público>>
Repositório: <<link do GitHub, se for público>>
```
