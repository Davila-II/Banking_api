from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Ce qu'on reçoit pour créer un compte
class CompteCreate(BaseModel):
    nom_titulaire: str
    email: str

# Ce qu'on retourne au client
class CompteResponse(BaseModel):
    id: int
    numero_compte: str
    nom_titulaire: str
    email: str
    solde: float
    date_creation: datetime