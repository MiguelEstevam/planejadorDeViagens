import asyncio
import httpx
from urllib.parse import quote

async def geocode(client: httpx.AsyncClient, q: str):
    USER_AGENT = "PlanejadorViagensInteligentes/1.0 (docker; acadêmico)"
    url = f"https://nominatim.openstreetmap.org/search?q={quote(q)}&format=json&limit=1"
    r = await client.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=15.0,
    )
    print(r.status_code)
    print(r.text)

async def main():
    async with httpx.AsyncClient() as client:
        await geocode(client, "Sao Paulo")

asyncio.run(main())
