# 🗺️ Planejador de Viagens Inteligentes

> Sistema distribuído em microsserviços que agrega, em uma única requisição, **rota viária real**, **previsão do tempo** e **custo estimado de combustível** para qualquer viagem de carro no Brasil.

---

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Serviços](#serviços)
- [Recursos e Resiliência](#recursos-e-resiliência)
- [Início Rápido](#início-rápido)
- [API Reference](#api-reference)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Deploy em 3 Máquinas](#deploy-em-3-máquinas)
- [Modelagem do Domínio](#modelagem-do-domínio)
- [Observações](#observações)

---

## Visão Geral

O usuário informa **origem**, **destino**, **data de ida** e **data de volta**. O sistema retorna:

| Dado | Fonte |
|------|-------|
| Rota viária (distância, duração, traçado) | [OSRM](https://project-osrm.org/) + [Nominatim/OSM](https://nominatim.org/) |
| Previsão do tempo (máx, mín, chuva) | [Open-Meteo](https://open-meteo.com/) |
| Custo estimado de combustível | Cálculo local configurável |

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                        Usuário (Browser)                     │
│                     http://localhost:8000                    │
└───────────────────────────┬─────────────────────────────────┘
                            │ POST /api/v1/planejamento
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway :8000                       │
│  • Orquestração paralela dos serviços                       │
│  • Cache de idempotência (Redis · TTL 24h)                  │
│  • Retry + Backoff Exponencial                              │
│  • Fallback degradado em caso de falha                      │
│  • Validação de entrada (Pydantic)                          │
└──────────┬───────────────┬────────────────┬─────────────────┘
           │               │                │
           ▼               ▼                ▼
   ┌───────────┐   ┌───────────┐   ┌───────────────┐
   │  Clima    │   │   Rota    │   │  Combustível  │
   │  :8001    │   │   :8002   │   │    :8003      │
   │           │   │           │   │               │
   │Open-Meteo │   │Nominatim  │   │  Cálculo      │
   │    API    │   │  + OSRM   │   │   local       │
   └───────────┘   └───────────┘   └───────────────┘
                        │
                  ┌─────┴──────┐
                  │   Redis    │
                  │   :6379    │
                  └────────────┘
```

---

## Serviços

| Serviço | Porta | Responsabilidade |
|---------|-------|-----------------|
| **gateway** | `8000` | Orquestrador principal, UI, cache |
| **clima** | `8001` | Previsão do tempo via Open-Meteo |
| **rota** | `8002` | Geocodificação (Nominatim) e roteamento (OSRM) |
| **combustivel** | `8003` | Estimativa de custo de combustível |
| **redis** | `6379` | Cache de idempotência |

---

## Recursos e Resiliência

### Gateway
- **Orquestração paralela**: clima (ida e volta), rota e combustível são chamados de forma assíncrona
- **Cache Redis**: respostas são armazenadas por 24h; chamadas idênticas não reprocessam
- **Retry com backoff exponencial**: até 3 tentativas configuráveis (`HTTP_MAX_RETRIES`)
- **Timeout HTTP configurável**: padrão 12s (`HTTP_TIMEOUT_SECONDS`)
- **Modo degradado**: se um serviço falhar, o planejamento retorna com `degradado: true` em vez de erro total

### Serviço de Rota
- Geocodificação de texto livre em coordenadas via Nominatim
- Roteamento viário real com geometria GeoJSON via OSRM público
- Fallback automático: se OSRM falhar, estima distância via fórmula Haversine ajustada (×1.35)

### Serviço de Clima
- Previsão agregada por período (temperatura máx, mín e precipitação média)
- Consultado duas vezes: clima no destino na ida, clima na origem na volta

---

## Início Rápido

**Pré-requisito**: [Docker Desktop](https://www.docker.com/products/docker-desktop/)

```bash
# Clone o repositório
git clone <url-do-repositorio>
cd planejadorDeViagens

# Suba todos os serviços
docker compose up --build
```

Acesse:
- **Interface Web**: [http://localhost:8000](http://localhost:8000)
- **Documentação OpenAPI (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **API REST**: `POST http://localhost:8000/api/v1/planejamento`

---

## API Reference

### `POST /api/v1/planejamento`

Gera um planejamento completo de viagem.

**Request Body**
```json
{
  "origem": "São Paulo, SP",
  "destino": "Curitiba, PR",
  "data_ida": "2026-04-25",
  "data_volta": "2026-04-30"
}
```

**Response `200 OK`**
```json
{
  "solicitacao": {
    "origem": "São Paulo, SP",
    "destino": "Curitiba, PR",
    "data_ida": "2026-04-25",
    "data_volta": "2026-04-30"
  },
  "rota": {
    "distancia_km": 403.79,
    "duracao_segundos": 20470,
    "origem_resolvida": "São Paulo, Região Sudeste, Brasil",
    "destino_resolvido": "Curitiba, Paraná, Região Sul, Brasil",
    "resumo": "Rota viária: ~403.8 km, ~5h41min.",
    "geometria": { "type": "LineString", "coordinates": [...] },
    "degradado": false
  },
  "clima_ida": {
    "periodo": "ida — clima no destino",
    "temperatura_max_media_c": 27.0,
    "temperatura_min_media_c": 15.8,
    "precipitacao_mm_media": 0.0,
    "degradado": false
  },
  "clima_volta": {
    "periodo": "volta — clima na origem",
    "temperatura_max_media_c": 25.7,
    "temperatura_min_media_c": 19.9,
    "precipitacao_mm_media": 1.2,
    "degradado": false
  },
  "combustivel": {
    "custo_medio_reais": 417.25,
    "distancia_km": 807.58,
    "preco_litro_reais": 6.2,
    "consumo_km_por_litro": 12.0,
    "degradado": false
  },
  "meta": {
    "idempotencia": "commit",
    "nota_combustivel": "Custo médio estimado para ida e volta (2x distância unidirecional)."
  }
}
```

> **Nota**: `meta.idempotencia` retorna `"commit"` (processamento novo) ou `"replay"` (resultado do cache Redis).

---

## Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto para sobrescrever os padrões:

| Variável | Serviço | Padrão | Descrição |
|----------|---------|--------|-----------|
| `OPEN_METEO_URL` | clima | `https://api.open-meteo.com/v1/forecast` | URL da API de clima |
| `NOMINATIM_URL` | rota | `https://nominatim.openstreetmap.org/search` | URL do geocodificador |
| `OSRM_URL` | rota | `https://router.project-osrm.org/route/v1/driving` | URL do servidor de rotas |
| `NOMINATIM_USER_AGENT` | rota | `PlanejadorViagensInteligentes/1.0` | Identificação para o Nominatim |
| `PRECO_GASOLINA_LITRO_REAIS` | combustivel | `6.20` | Preço do litro de gasolina |
| `CONSUMO_KM_POR_LITRO` | combustivel | `12.0` | Consumo médio do veículo |
| `REDIS_URL` | gateway | `redis://redis:6379/0` | URL de conexão do Redis |
| `HTTP_TIMEOUT_SECONDS` | gateway | `12` | Timeout para chamadas entre serviços |
| `HTTP_MAX_RETRIES` | gateway | `3` | Número de tentativas por serviço |

---

## Deploy em 3 Máquinas

Para um ambiente distribuído, distribua os serviços entre três VMs com Docker instalado e rede entre elas.

| Máquina | Serviços | Portas |
|---------|----------|--------|
| **VM 1** | `gateway` | `8000` |
| **VM 2** | `clima`, `rota` | `8001`, `8002` |
| **VM 3** | `redis`, `combustivel` | `6379`, `8003` |

**Configuração**

1. Copie o repositório para as três máquinas.
2. Ajuste os IPs em `deploy/env/three-nodes.env.example` e salve como `three-nodes.env`.
3. Suba cada stack com o compose correspondente:

```bash
# VM 1
docker compose -f deploy/docker-compose.maquina1-gateway.yml up -d

# VM 2
docker compose -f deploy/docker-compose.maquina2-servicos.yml up -d

# VM 3
docker compose -f deploy/docker-compose.maquina3-dados.yml up -d
```

As variáveis `CLIMA_SERVICE_URL`, `ROTA_SERVICE_URL`, `COMBUSTIVEL_SERVICE_URL` e `REDIS_URL` no Gateway devem apontar para os IPs/hostnames das outras máquinas.

---

## Modelagem do Domínio

Consulte [`docs/modelagem.md`](docs/modelagem.md) para diagramas e o fluxo distribuído completo da requisição, incluindo a definição das entidades **Viagem**, **Origem** e **Destino**.

---

## Observações

- As APIs públicas (**Nominatim**, **OSRM**, **Open-Meteo**) possuem políticas de uso justo. Para produção, considere instâncias próprias ou contratos comerciais.
- A previsão do tempo está limitada a ~15 dias à frente (limite da camada gratuita do Open-Meteo). Datas além do horizonte retornam com `degradado: true`.
- O custo de combustível considera **ida e volta** (2× a distância unidirecional da rota).
