import asyncio
import httpx
from services.rota.main import geocode, NOMINATIM, OSRM

async def main():
    async with httpx.AsyncClient() as client:
        try:
            print("Testing geocode...")
            lat, lon, label = await geocode(client, "Sao Paulo")
            print(f"Geocode success: {lat}, {lon}, {label}")
            
            coords = f"{lon},{lat};-49.273,-25.428"
            print(f"Testing OSRM with {coords}...")
            r = await client.get(f"{OSRM}/{coords}", params={"overview": "false"}, timeout=20.0)
            print("OSRM status:", r.status_code)
            print("OSRM response:", r.text[:200])
        except Exception as e:
            print(f"Exception: {type(e).__name__}: {e}")

asyncio.run(main())
