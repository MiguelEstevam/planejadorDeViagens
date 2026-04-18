import os

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Serviço de Combustível", version="1.0.0")

PRECO_LITRO = float(os.getenv("PRECO_GASOLINA_LITRO_REAIS", "6.20"))
CONSUMO_KM_L = float(os.getenv("CONSUMO_KM_POR_LITRO", "12.0"))


class CalcularEntrada(BaseModel):
    distancia_km: float = Field(..., gt=0)


class CalcularSaida(BaseModel):
    custo_medio_reais: float
    distancia_km: float
    preco_litro_reais: float
    consumo_km_por_litro: float
    degradado: bool = False


@app.get("/health")
def health():
    return {"status": "ok", "servico": "combustivel"}


@app.post("/combustivel/calcular", response_model=CalcularSaida)
def calcular(body: CalcularEntrada):
    litros = body.distancia_km / CONSUMO_KM_L
    custo = round(litros * PRECO_LITRO, 2)
    return CalcularSaida(
        custo_medio_reais=custo,
        distancia_km=body.distancia_km,
        preco_litro_reais=PRECO_LITRO,
        consumo_km_por_litro=CONSUMO_KM_L,
    )
