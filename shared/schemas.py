"""Contratos compartilhados — domínio com origem explícita (modelagem)."""
from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field


class Coordenadas(BaseModel):
    latitude: float
    longitude: float


class Localizacao(BaseModel):
    """Ponto geográfico nomeado (origem ou destino na viagem)."""

    texto: str = Field(..., description="Endereço ou cidade")
    coordenadas: Optional[Coordenadas] = None


class SolicitacaoPlanejamento(BaseModel):
    """Entrada do usuário: origem e destino obrigatórios na definição do caso de uso."""

    origem: str = Field(..., min_length=2, max_length=256, description="Local de partida")
    destino: str = Field(..., min_length=2, max_length=256, description="Local de chegada")
    data_ida: date
    data_volta: date


class TrechoClima(BaseModel):
    periodo: str
    temperatura_max_media_c: Optional[float] = None
    temperatura_min_media_c: Optional[float] = None
    precipitacao_mm_media: Optional[float] = None
    fonte: str = "open-meteo"
    degradado: bool = False


class RespostaRota(BaseModel):
    distancia_km: float
    duracao_segundos: int
    origem_resolvida: str
    destino_resolvido: str
    origem_lat: float
    origem_lon: float
    destino_lat: float
    destino_lon: float
    resumo: str
    degradado: bool = False


class RespostaCombustivel(BaseModel):
    custo_medio_reais: float
    distancia_km: float
    preco_litro_reais: float
    consumo_km_por_litro: float
    degradado: bool = False


class RespostaPlanejamento(BaseModel):
    solicitacao: SolicitacaoPlanejamento
    clima_ida: TrechoClima
    clima_volta: TrechoClima
    rota: RespostaRota
    combustivel: RespostaCombustivel
    meta: dict[str, Any] = Field(default_factory=dict)
