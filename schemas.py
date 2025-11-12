"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name.
"""

from pydantic import BaseModel, Field
from typing import List, Optional

class EvolutionStage(BaseModel):
    id: int
    name: str
    sprite: Optional[str] = None

class Stats(BaseModel):
    hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int

class Pokemon(BaseModel):
    id: int = Field(..., description="National Pokédex number")
    name: str
    types: List[str]
    height: float
    weight: float
    stats: Stats
    sprite: Optional[str] = None
    spriteHD: Optional[str] = None
    evolution: List[EvolutionStage] = []
