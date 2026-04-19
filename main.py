from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
import uuid

app = FastAPI(title="Banking API")

# Stockage en mémoire
comptes = []
transactions = []

# Schémas (formats JSON)
class CompteCreate(BaseModel):
    nom_titulaire: str
    email: str

class CompteResponse(BaseModel):
    id: str
    numero_compte: str
    nom_titulaire: str
    email: str
    solde: float
    date_creation: str

# Endpoints

# Créer un compte
@app.post("/comptes", response_model=CompteResponse)
def creer_compte(data: CompteCreate):
    for c in comptes:
        if c["email"] == data.email:
            raise HTTPException(status_code=400, detail="Email déjà utilisé")

    nouveau_compte = {
        "id": str(uuid.uuid4()),
        "numero_compte": "BK-" + str(uuid.uuid4())[:8].upper(),
        "nom_titulaire": data.nom_titulaire,
        "email": data.email,
        "solde": 0.0,
        "date_creation": datetime.now().isoformat()
    }
    comptes.append(nouveau_compte)
    return nouveau_compte

# Lister les comptes
@app.get("/comptes", response_model=List[CompteResponse])
def lister_comptes():
    return comptes