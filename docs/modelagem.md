# Modelagem — Planejador de Viagens Inteligentes

## Domínio (origem explícita)

A viagem é definida obrigatoriamente por **origem**, **destino** e **janelas temporais** (ida e volta). A origem não é apenas um ponto geográfico implícito: ela entra no contrato da API (`SolicitacaoPlanejamento.origem`), na resolução de endereços do serviço de rota (`GET /rota?origem=...`) e no agregado de clima na **volta** (previsão na coordenada resolvida da origem).

| Conceito | Descrição |
|----------|-----------|
| Origem | Local de partida informado pelo usuário (texto livre, geocodificado). |
| Destino | Local de chegada na ida; base para clima na data de ida. |
| Rota | Distância e duração estimadas (OSRM) com fallback por Haversine. |
| Combustível | Custo médio a partir da distância **ida + volta** e parâmetros econômicos. |

## Arquitetura lógica (distribuída)

```mermaid
flowchart LR
  U[Usuário] --> G[Gateway]
  G --> R[Redis idempotência]
  G --> C[Clima]
  G --> O[Rota]
  G --> F[Combustível]
  O --> N[Nominatim]
  O --> M[OSRM]
  C --> W[Open-Meteo]
```

## Sequência do planejamento

```mermaid
sequenceDiagram
  participant U as Usuário
  participant G as Gateway
  participant Rd as Redis
  participant Rt as Rota
  participant Cl as Clima
  participant Cb as Combustível
  U->>G: POST planejamento origem destino datas
  G->>Rd: GET idempotency key
  alt cache hit
    Rd-->>G: JSON salvo
    G-->>U: 200 replay
  else miss
    G->>Rt: GET /rota origem destino
    Rt-->>G: coords + distância
    par clima ida destino
      G->>Cl: GET /clima destino data_ida
    and clima volta origem
      G->>Cl: GET /clima origem data_volta
    and combustível
      G->>Cb: POST 2x distância
    end
    G->>Rd: SET resposta + hash corpo
    G-->>U: 200 commit
  end
```

## Políticas de resiliência no gateway

| Mecanismo | Onde | Comportamento |
|-----------|------|----------------|
| Timeout | Chamadas HTTP aos microsserviços | Falha rápida; evita filas internas longas. |
| Retry | Transporte/timeout | Até N tentativas com backoff. |
| Fallback | Clima, rota, combustível | Resposta parcial marcada `degradado` ou estimativa simplificada. |
| Idempotência | Redis | Mesma chave + mesmo corpo = mesma resposta; chave + corpo diferente = conflito. |

Esta modelagem amarra o requisito acadêmico de **origem** ao contrato, ao fluxo de dados e ao comportamento degradado quando integrações externas falham.
