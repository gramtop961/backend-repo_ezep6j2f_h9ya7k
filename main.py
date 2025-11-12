import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import requests

from database import db, create_document, get_documents
from schemas import Pokemon, EvolutionStage, Stats

POKEAPI_BASE = "https://pokeapi.co/api/v2"

app = FastAPI(title="Pixel PokéDex API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PokemonQuery(BaseModel):
    query: Optional[str] = None
    type: Optional[str] = None
    limit: int = 50
    offset: int = 0

@app.get("/")
def read_root():
    return {"message": "Pixel PokéDex API running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()
    except Exception as e:
        response["database"] = f"⚠️ Error: {str(e)[:80]}"
    return response

# Helper functions to fetch from PokeAPI and normalize

def fetch_pokemon_basic(poke_id_or_name: str):
    r = requests.get(f"{POKEAPI_BASE}/pokemon/{poke_id_or_name}")
    if r.status_code != 200:
        raise HTTPException(status_code=404, detail="Pokémon not found")
    return r.json()


def fetch_species(poke_id: int):
    r = requests.get(f"{POKEAPI_BASE}/pokemon-species/{poke_id}")
    if r.status_code != 200:
        return None
    return r.json()


def fetch_evolution_chain(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()


def build_evolution_chain(chain_node) -> List[EvolutionStage]:
    stages: List[EvolutionStage] = []
    def traverse(node):
        name = node.get("species", {}).get("name")
        if not name:
            return
        # Fetch id by species URL
        species_url = node.get("species", {}).get("url", "")
        try:
            poke_id = int(species_url.rstrip('/').split('/')[-1])
        except Exception:
            poke_id = 0
        stages.append(EvolutionStage(id=poke_id, name=name, sprite=f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{poke_id}.png"))
        for child in node.get("evolves_to", []):
            traverse(child)
    traverse(chain_node)
    # Deduplicate preserving order
    seen = set()
    deduped = []
    for s in stages:
        if s.id not in seen and s.id != 0:
            deduped.append(s)
            seen.add(s.id)
    return deduped


def normalize_pokemon(raw) -> Pokemon:
    types = [t["type"]["name"] for t in raw.get("types", [])]
    stats_map = {s["stat"]["name"]: s["base_stat"] for s in raw.get("stats", [])}
    stats = Stats(
        hp=stats_map.get("hp", 0),
        attack=stats_map.get("attack", 0),
        defense=stats_map.get("defense", 0),
        special_attack=stats_map.get("special-attack", 0),
        special_defense=stats_map.get("special-defense", 0),
        speed=stats_map.get("speed", 0),
    )
    pid = raw.get("id")
    species = fetch_species(pid) or {}
    evo_chain_url = (species.get("evolution_chain") or {}).get("url")
    evolution = []
    if evo_chain_url:
        evo = fetch_evolution_chain(evo_chain_url)
        if evo:
            evolution = build_evolution_chain(evo.get("chain", {}))
    return Pokemon(
        id=pid,
        name=raw.get("name", "").title(),
        types=types,
        height=raw.get("height", 0) / 10.0,
        weight=raw.get("weight", 0) / 10.0,
        stats=stats,
        sprite=f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{pid}.png",
        spriteHD=f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{pid}.png",
        evolution=evolution,
    )

@app.get("/api/pokemon/{poke}", response_model=Pokemon)
def get_pokemon(poke: str):
    raw = fetch_pokemon_basic(poke.lower())
    return normalize_pokemon(raw)

@app.get("/api/pokemon", response_model=List[Pokemon])
def list_pokemon(limit: int = 50, offset: int = 0, type: Optional[str] = None, q: Optional[str] = None):
    # Fetch list IDs first
    r = requests.get(f"{POKEAPI_BASE}/pokemon?limit={limit}&offset={offset}")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch list from PokeAPI")
    results = r.json().get("results", [])

    pokes: List[Pokemon] = []
    for item in results:
        try:
            raw = fetch_pokemon_basic(item["name"])  # small extra calls
            p = normalize_pokemon(raw)
            if type and type not in p.types:
                continue
            if q and q.lower() not in p.name.lower():
                continue
            pokes.append(p)
        except Exception:
            continue
    return pokes

# Optional: cache seeds some favorites into DB for quick demo
@app.post("/api/cache/{poke}")
def cache_pokemon(poke: str):
    raw = fetch_pokemon_basic(poke.lower())
    p = normalize_pokemon(raw)
    try:
        create_document("pokemon", p)
    except Exception:
        pass
    return {"status": "ok", "id": p.id, "name": p.name}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
