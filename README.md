# HidroAlerta & Rota Segura

**CitizenTech · FIAP Global Solution 2026/2 · Engenharia de Software (4ESOA)**

Plataforma que antecipa alagamentos em bairros com drenagem crítica, avisa o cidadão em linguagem simples
e recalcula o caminho evitando vias que vão alagar.

- **Cidadão beneficiado:** quem mora ou circula por áreas sujeitas a alagamento (pedestres, motoristas, usuários de ônibus, PcD).
- **Problema:** a chuva forte alaga vias em minutos e o cidadão só descobre quando já está na água. Não há alerta antecipado nem rota alternativa.
- **ODS:** 11 (Cidades e comunidades sustentáveis), 13 (Ação contra a mudança do clima), 9 (Indústria, inovação e infraestrutura).
- **Vídeo pitch:** `<<COLAR LINK PÚBLICO AQUI>>`

---

## Como rodar

### Opção A — Docker (recomendado)

```bash
docker compose up --build
```

Abra http://localhost:8000. O container processa o data lake, treina a IA e sobe a API.
O token de operador padrão é `troque-este-token`. Para usar outro: `HIDRO_API_TOKEN=meu-token docker compose up --build`.

### Opção B — Python local (3.10+)

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
python -m bigdata.pipeline --regerar
uvicorn api.main:app --reload
```

Abra http://localhost:8000.

### Sensores ao vivo (IoT)

Com a API rodando, em outro terminal:

```bash
python -m iot.sensor_sim --post http://localhost:8000 --token troque-este-token --passos 30
```

As leituras aparecem em tempo real na tela **Sensores e alertas**, já classificadas pela IA.

### Testes

```bash
python -m pytest -v
```

---

## Estrutura (um módulo por área)

| Pasta | Área da rubrica | O que tem |
|---|---|---|
| `iot/` | MVP, IoT | `sensor_sim.py`: 2 sensores mock por ponto (nível d'água + pluviômetro), com falhas de campo e modo ao vivo |
| `bigdata/` | Big Data | `pipeline.py`: data lake `lake/raw` → `lake/silver` → `lake/gold` |
| `ia/` | IA e automação | `modelo.py` (classificador de risco + métricas), `alertas.py` (texto acessível), `rotas.py` (rota segura) |
| `api/` | MVP, experiência digital | FastAPI + 4 telas em `api/static/` |
| `core/` | — | Território simulado (pontos, vias, limites) |
| `tests/` | DevOps, qualidade | 11 casos de teste (19 execuções) |
| `.github/workflows/` | DevOps | CI: pipeline → testes → build Docker → smoke test |
| `docs/` | Todas | Arquitetura, regras da IA, medidas do dashboard, plano de testes e evidências |

## As 4 telas

1. **Mapa e rota segura** (`/`): linha do tempo da chuva, risco por ponto, vias bloqueadas e o caminho seguro recalculado.
2. **Sensores e alertas** (`/sensores`): leituras ao vivo, série histórica por sensor e alertas emitidos.
3. **Dashboard** (`/dashboard`): 4 KPIs com filtros por bairro, severidade e horário, mais 3 gráficos.
4. **Histórico e simulação** (`/historico`): o operador gera um novo cenário de chuva e vê a qualidade dos dados e as métricas da IA.

## Resultados da IA (dias de teste, não usados no treino)

| Métrica | IA | Sistema reativo (hoje) |
|---|---|---|
| Recall de risco ALTO | **97,5%** | 71,5% |
| Antecedência média do alerta | **28,6 min** | 0 min |
| Alagamentos avisados antes de acontecer | **91%** (10 de 11) | 0% |

Detalhes em [docs/ia-regras-e-prompts.md](docs/ia-regras-e-prompts.md).

## Segurança

1. **Controle de acesso:** as rotas de escrita (`POST /api/ingest`, `POST /api/simular`) exigem o header `X-API-Token`, comparado em tempo constante.
2. **Validação e sanitização de entrada:** schemas Pydantic com faixa física, padrões de ID e coerência sensor×ponto e unidade×tipo. Os filtros usam lista branca (bairro) e regex (hora).
3. **Proteção no front:** todo texto vindo da API é inserido via `textContent` (sem `innerHTML`), o que evita XSS. Há cabeçalhos `Content-Security-Policy`, `X-Content-Type-Options` e `X-Frame-Options`.
4. **Container sem root** e token fora do código (variável de ambiente).

## Uso de IA generativa (declaração)

| Ferramenta | Para quê |
|---|---|
| `<<preencher pelo grupo>>` | `<<ex.: apoio na estruturação do código, revisão de texto, explicação de erros>>` |

Todo o código foi revisado e é explicável pelo grupo.

## Integrantes

Ver `integrantes.txt`.
