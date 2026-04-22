import asyncio
import hashlib
import json
import os
import sys
from datetime import date, timedelta
from typing import Any, Optional

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from shared.schemas import (
    RespostaCombustivel,
    RespostaPlanejamento,
    RespostaRota,
    SolicitacaoPlanejamento,
    TrechoClima,
)

CLIMA_URL = os.getenv("CLIMA_SERVICE_URL", "http://localhost:8001")
ROTA_URL = os.getenv("ROTA_SERVICE_URL", "http://localhost:8002")
COMBUSTIVEL_URL = os.getenv("COMBUSTIVEL_SERVICE_URL", "http://localhost:8003")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

REQUEST_TIMEOUT = float(os.getenv("HTTP_TIMEOUT_SECONDS", "12"))
MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "3"))
IDEMPOTENCY_TTL = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", "86400"))

app = FastAPI(title="Planejador de Viagens Inteligentes — API Gateway", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATIC = os.path.join(os.path.dirname(__file__), "static")


def _idempotency_body_hash(body: dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


_redis_client = None

async def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


async def _call_with_retry(
    method: str,
    url: str,
    *,
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
) -> httpx.Response:
    last: Optional[BaseException] = None
    async with httpx.AsyncClient() as client:
        for attempt in range(MAX_RETRIES):
            try:
                r = await client.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    timeout=REQUEST_TIMEOUT,
                )
                if r.status_code in (502, 503, 504) and attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(0.35 * (2**attempt))
                    continue
                return r
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(0.35 * (2**attempt))
        assert last is not None
        raise last


async def _fetch_rota(origem: str, destino: str) -> RespostaRota:
    url = f"{ROTA_URL}/rota"
    try:
        r = await _call_with_retry("GET", url, params={"origem": origem, "destino": destino})
        r.raise_for_status()
        data = r.json()
        return RespostaRota.model_validate(data)
    except Exception:
        return RespostaRota(
            distancia_km=0.0,
            duracao_segundos=0,
            origem_resolvida=origem,
            destino_resolvido=destino,
            origem_lat=0.0,
            origem_lon=0.0,
            destino_lat=0.0,
            destino_lon=0.0,
            resumo="Rota indisponível após retentativas; informe origem/destino mais específicos.",
            degradado=True,
        )


async def _fetch_clima_trecho(
    lat: float,
    lon: float,
    inicio: date,
    fim: date,
    rotulo: str,
) -> TrechoClima:
    if lat == 0.0 and lon == 0.0:
        return TrechoClima(
            periodo=rotulo,
            fonte="fallback",
            degradado=True,
        )
    url = f"{CLIMA_URL}/clima"
    params = {
        "lat": lat,
        "lon": lon,
        "data_inicio": inicio.isoformat(),
        "data_fim": fim.isoformat(),
    }
    try:
        r = await _call_with_retry("GET", url, params=params)
        r.raise_for_status()
        d = r.json()
        return TrechoClima(
            periodo=rotulo,
            temperatura_max_media_c=d.get("temperatura_max_media_c"),
            temperatura_min_media_c=d.get("temperatura_min_media_c"),
            precipitacao_mm_media=d.get("precipitacao_mm_media"),
            fonte=d.get("fonte", "open-meteo"),
            degradado=bool(d.get("degradado")),
        )
    except Exception:
        return TrechoClima(
            periodo=rotulo,
            fonte="fallback",
            degradado=True,
        )


async def _fetch_combustivel(distancia_ida_e_volta_km: float) -> RespostaCombustivel:
    url = f"{COMBUSTIVEL_URL}/combustivel/calcular"
    try:
        r = await _call_with_retry("POST", url, json_body={"distancia_km": distancia_ida_e_volta_km})
        r.raise_for_status()
        return RespostaCombustivel.model_validate(r.json())
    except Exception:
        return RespostaCombustivel(
            custo_medio_reais=0.0,
            distancia_km=distancia_ida_e_volta_km,
            preco_litro_reais=0.0,
            consumo_km_por_litro=0.0,
            degradado=True,
        )


@app.get("/health")
async def health():
    r = await _get_redis()
    pong = await r.ping()
    return {
        "status": "ok",
        "servico": "gateway",
        "redis": bool(pong),
        "timeouts_s": REQUEST_TIMEOUT,
        "retries": MAX_RETRIES,
    }


@app.post("/api/v1/planejamento", response_model=RespostaPlanejamento)
async def planejamento(
    body: SolicitacaoPlanejamento,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    if body.data_volta < body.data_ida:
        raise HTTPException(400, "data_volta deve ser >= data_ida")

    limite_previsao = date.today() + timedelta(days=15)
    if body.data_ida > limite_previsao or body.data_volta > limite_previsao:
        # Open-Meteo forecast limita horizonte; ainda assim tentamos (pode falhar e cair no fallback).
        pass

    body_dict = body.model_dump(mode="json")
    key_material = idempotency_key or _idempotency_body_hash(body_dict)
    cache_key = f"idempotency:planejamento:{key_material}"
    hash_key = f"{cache_key}:bodyhash"
    body_hash = _idempotency_body_hash(body_dict)

    rdb = await _get_redis()
    if True:
        cached = await rdb.get(cache_key)
        if cached:
            stored = await rdb.get(hash_key)
            if stored and stored != body_hash:
                raise HTTPException(
                    409,
                    "Idempotency-Key já usada com payload diferente; use outra chave ou o mesmo corpo.",
                )
            data = json.loads(cached)
            data.setdefault("meta", {})
            data["meta"]["idempotencia"] = "replay"
            return RespostaPlanejamento.model_validate(data)

        rota = await _fetch_rota(body.origem, body.destino)
        if rota.distancia_km <= 0 and rota.degradado:
            raise HTTPException(503, "Não foi possível resolver rota para os locais informados.")

        lat_d, lon_d = rota.destino_lat, rota.destino_lon
        lat_o, lon_o = rota.origem_lat, rota.origem_lon

        clima_ida, clima_volta, combustivel = await asyncio.gather(
            _fetch_clima_trecho(lat_d, lon_d, body.data_ida, body.data_ida, "ida — clima no destino"),
            _fetch_clima_trecho(lat_o, lon_o, body.data_volta, body.data_volta, "volta — clima na origem"),
            _fetch_combustivel(rota.distancia_km * 2),
        )

        resposta = RespostaPlanejamento(
            solicitacao=body,
            clima_ida=clima_ida,
            clima_volta=clima_volta,
            rota=rota,
            combustivel=combustivel,
            meta={
                "idempotencia": "commit",
                "distancia_considerada_combustivel_km": rota.distancia_km * 2,
                "nota_combustivel": "Custo médio estimado para ida e volta (2x distância unidirecional).",
            },
        )
        payload = resposta.model_dump(mode="json")
        body_json = json.dumps(payload, ensure_ascii=False)
        await rdb.set(cache_key, body_json, ex=IDEMPOTENCY_TTL)
        await rdb.set(hash_key, body_hash, ex=IDEMPOTENCY_TTL)
        return resposta

@app.get("/", include_in_schema=False)
async def raiz():
    if os.path.isdir(_STATIC):
        return RedirectResponse(url="/ui/")
    return {"mensagem": "Planejador de Viagens Inteligentes — use POST /api/v1/planejamento"}


if os.path.isdir(_STATIC):
    app.mount("/ui", StaticFiles(directory=_STATIC, html=True), name="ui")
