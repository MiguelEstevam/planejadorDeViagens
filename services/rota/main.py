import math
import os
from typing import Any, Optional
from urllib.parse import quote

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

NOMINATIM = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
OSRM = os.getenv("OSRM_URL", "https://router.project-osrm.org/route/v1/driving")

USER_AGENT = os.getenv(
    "NOMINATIM_USER_AGENT",
    "PlanejadorViagensInteligentes/1.0 (projeto academico; contato@localhost)",
)


class RotaResposta(BaseModel):
    distancia_km: float = Field(..., description="Distância estimada pela malha viária")
    duracao_segundos: int
    origem_resolvida: str
    destino_resolvido: str
    origem_lat: float
    origem_lon: float
    destino_lat: float
    destino_lon: float
    resumo: str
    geometria: Optional[dict[str, Any]] = None
    degradado: bool = False


app = FastAPI(title="Serviço de Rota", version="1.0.0")


async def geocode(client: httpx.AsyncClient, q: str) -> tuple[float, float, str]:
    url = f"{NOMINATIM}?q={quote(q)}&format=json&limit=1"
    try:
        r = await client.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=15.0,
        )
        if r.status_code != 200:
            raise HTTPException(502, f"Geocodificação indisponível: HTTP {r.status_code} - {r.text}")
        arr = r.json()
        if not arr:
            raise HTTPException(404, f"Local não encontrado: {q}")
        item = arr[0]
        lat = float(item["lat"])
        lon = float(item["lon"])
        label = item.get("display_name") or q
        return lat, lon, label
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Exceção no geocode: {e}")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@app.get("/health")
def health():
    return {"status": "ok", "servico": "rota"}


@app.get("/rota", response_model=RotaResposta)
async def rota(
    origem: str = Query(..., min_length=2),
    destino: str = Query(..., min_length=2),
):
    try:
        async with httpx.AsyncClient() as client:
            olat, olon, olabel = await geocode(client, origem)
            dlat, dlon, dlabel = await geocode(client, destino)
            coords = f"{olon},{olat};{dlon},{dlat}"
            try:
                r = await client.get(
                    f"{OSRM}/{coords}", 
                    params={"overview": "full", "geometries": "geojson"}, 
                    headers={"User-Agent": USER_AGENT},
                    timeout=20.0
                )
                status_code = r.status_code
                body = r.json() if status_code == 200 else {}
            except Exception as e:
                status_code = 502
                body = {}

            if status_code != 200:
                dist = haversine_km(olat, olon, dlat, dlon) * 1.35
                vel_kmh = 65.0
                return RotaResposta(
                distancia_km=round(dist, 2),
                duracao_segundos=int(dist / vel_kmh * 3600),
                origem_resolvida=olabel,
                destino_resolvido=dlabel,
                origem_lat=olat,
                origem_lon=olon,
                destino_lat=dlat,
                destino_lon=dlon,
                resumo="Estimativa por linha reta ajustada (OSRM indisponível).",
                degradado=True,
            )
        routes = body.get("routes") or []
        if not routes:
            dist = haversine_km(olat, olon, dlat, dlon) * 1.35
            vel_kmh = 65.0
            return RotaResposta(
                distancia_km=round(dist, 2),
                duracao_segundos=int(dist / vel_kmh * 3600),
                origem_resolvida=olabel,
                destino_resolvido=dlabel,
                origem_lat=olat,
                origem_lon=olon,
                destino_lat=dlat,
                destino_lon=dlon,
                resumo="Estimativa aproximada (sem rota OSRM).",
                degradado=True,
            )
        rt = routes[0]
        dist_m = float(rt.get("distance", 0))
        dur_s = int(float(rt.get("duration", 0)))
        km = dist_m / 1000.0
        geom = rt.get("geometry")
        return RotaResposta(
            distancia_km=round(km, 2),
            duracao_segundos=dur_s,
            origem_resolvida=olabel,
            destino_resolvido=dlabel,
            origem_lat=olat,
            origem_lon=olon,
            destino_lat=dlat,
            destino_lon=dlon,
            resumo=f"Rota viária: ~{km:.1f} km, ~{dur_s // 3600}h{(dur_s % 3600) // 60}min.",
            geometria=geom,
            degradado=False,
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, detail=f"Erro interno em rota: {e}")
