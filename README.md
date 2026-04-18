# Planejador de Viagens Inteligentes

Sistema distribuído em microsserviços: o usuário informa **origem**, **destino**, **data de ida** e **data de volta**; o **API Gateway** orquestra **clima** (Open-Meteo), **rota** (Nominatim + OSRM público) e **combustível** (cálculo local com preço e consumo configuráveis).

## Resiliência e segurança (gateway)

- **Timeout** HTTP configurável (`HTTP_TIMEOUT_SECONDS`, padrão 12s).
- **Retry** com backoff exponencial (`HTTP_MAX_RETRIES`, padrão 3).
- **Fallback** degradado quando serviços externos falham (clima/rota/combustível retornam `degradado: true` ou estimativas aproximadas na rota).
- **Idempotência** com Redis: cabeçalho `Idempotency-Key` (ou hash do corpo); mesma chave + mesmo corpo devolve a mesma resposta; chave repetida com corpo diferente → HTTP 409.
- **Entrada**: tamanho máximo de strings e validação de datas (Pydantic).

## Execução local (uma máquina)

Pré-requisito: Docker Desktop.

```bash
docker compose up --build
```

- UI: [http://localhost:8000/](http://localhost:8000/) (redireciona para `/ui/`)
- API: `POST http://localhost:8000/api/v1/planejamento`
- OpenAPI: [http://localhost:8000/docs](http://localhost:8000/docs)

Exemplo de corpo:

```json
{
  "origem": "São Paulo, SP",
  "destino": "Curitiba, PR",
  "data_ida": "2026-04-20",
  "data_volta": "2026-04-25"
}
```

O custo de combustível usa **ida e volta** (`2 ×` distância unidirecional da rota).

## Três máquinas (Docker)

Cada VM deve ter Docker e portas liberadas entre os hosts.

| Máquina | Papéis sugeridos | Portas |
|--------|-------------------|--------|
| **1** | API Gateway | 8000 |
| **2** | Serviços de clima + rota | 8001, 8002 |
| **3** | Redis + serviço de combustível | 6379, 8003 |

1. Copie o repositório para as três máquinas (ou use uma e `scp` das imagens).
2. Nas máquinas 2 e 3, suba os stacks de `deploy/` ajustando os IPs em `deploy/env/three-nodes.env.example` (copie para `three-nodes.env` e preencha).
3. Na máquina 1, suba apenas o gateway apontando para os URLs das outras.

Arquivos de referência:

- `deploy/docker-compose.maquina1-gateway.yml`
- `deploy/docker-compose.maquina2-servicos.yml`
- `deploy/docker-compose.maquina3-dados.yml`

Rede: os hosts precisam alcançar uns aos outros pelos IPs/hostname nas variáveis `CLIMA_SERVICE_URL`, `ROTA_SERVICE_URL`, `COMBUSTIVEL_SERVICE_URL` e `REDIS_URL`.

## Modelagem (origem no domínio)

Ver `docs/modelagem.md` — entidade de viagem com **origem** e **destino** explícitos, diagramas e fluxo distribuído.

## Observações

- APIs públicas (Nominatim/OSRM/Open-Meteo) têm políticas de uso; para produção use instâncias próprias ou contratos comerciais.
- Previsão além do horizonte gratuito do Open-Meteo pode falhar; o gateway aplica **fallback** de clima degradado.
