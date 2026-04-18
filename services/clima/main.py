import os
from datetime import date

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

OPEN_METEO = os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")

app = FastAPI(title="Serviço de Clima", version="1.0.0")


class ClimaResposta(BaseModel):
    latitude: float
    longitude: float
    data_inicio: date
    data_fim: date
    temperatura_max_media_c: float | None = None
    temperatura_min_media_c: float | None = None
    precipitacao_mm_media: float | None = None
    fonte: str = "open-meteo"
    degradado: bool = False


@app.get("/health")
def health():
    return {"status": "ok", "servico": "clima"}


@app.get("/clima", response_model=ClimaResposta)
async def clima(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    data_inicio: date = Query(...),
    data_fim: date = Query(...),
):
    if data_fim < data_inicio:
        raise HTTPException(400, "data_fim deve ser >= data_inicio")
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": data_inicio.isoformat(),
        "end_date": data_fim.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "America/Sao_Paulo",
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(OPEN_METEO, params=params, timeout=15.0)
        if r.status_code != 200:
            raise HTTPException(502, "Falha ao consultar previsão")
        data = r.json()
    daily = data.get("daily") or {}
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    prec = daily.get("precipitation_sum") or []

    def avg(xs: list) -> float | None:
        nums = [float(x) for x in xs if x is not None]
        return sum(nums) / len(nums) if nums else None

    return ClimaResposta(
        latitude=lat,
        longitude=lon,
        data_inicio=data_inicio,
        data_fim=data_fim,
        temperatura_max_media_c=avg(tmax),
        temperatura_min_media_c=avg(tmin),
        precipitacao_mm_media=avg(prec),
    )
