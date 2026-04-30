from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
import uuid

app = FastAPI(
    title="Banking API"
    description="API REST pour la gestion de comptes bancaires - dépôts et retraits",
    version="1.0.0",
    docs_url="/api-docs",       
    redoc_url="/api-redoc" 
)

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

class TransactionMontant(BaseModel):
    montant: float

class VirementData(BaseModel):
    numero_compte_destination: str
    montant: float

class TransactionResponse(BaseModel):
    id: str
    type: str
    montant: float
    date: str
    compte_source: str
    compte_destination: str | None

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

# Consulter un compte par numéro
@app.get("/comptes/{numero_compte}", response_model=CompteResponse)
def consulter_compte(numero_compte: str):
    compte = next((c for c in comptes if c["numero_compte"] == numero_compte), None)
    if not compte:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    return compte

# Dépôt
@app.post("/comptes/{numero_compte}/depot", response_model=TransactionResponse)
def depot(numero_compte: str, data: TransactionMontant):
    if data.montant <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif")

    compte = next((c for c in comptes if c["numero_compte"] == numero_compte), None)
    if not compte:
        raise HTTPException(status_code=404, detail="Compte introuvable")

    compte["solde"] += data.montant

    transaction = {
        "id": str(uuid.uuid4()),
        "type": "depot",
        "montant": data.montant,
        "date": datetime.now().isoformat(),
        "compte_source": numero_compte,
        "compte_destination": None
    }
    transactions.append(transaction)
    return transaction

# Retrait
@app.post("/comptes/{numero_compte}/retrait", response_model=TransactionResponse)
def retrait(numero_compte: str, data: TransactionMontant):
    if data.montant <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif")

    compte = next((c for c in comptes if c["numero_compte"] == numero_compte), None)
    if not compte:
        raise HTTPException(status_code=404, detail="Compte introuvable")

    if compte["solde"] < data.montant:
        raise HTTPException(status_code=400, detail="Solde insuffisant")

    compte["solde"] -= data.montant

    transaction = {
        "id": str(uuid.uuid4()),
        "type": "retrait",
        "montant": data.montant,
        "date": datetime.now().isoformat(),
        "compte_source": numero_compte,
        "compte_destination": None
    }
    transactions.append(transaction)
    return transaction

# Supprimer un compte
@app.delete("/comptes/{numero_compte}")
def supprimer_compte(numero_compte: str):
    compte = next((c for c in comptes if c["numero_compte"] == numero_compte), None)
    if not compte:
        raise HTTPException(status_code=404, detail="Compte introuvable")

    comptes.remove(compte)

    txns_supprimees = [
        t for t in transactions
        if t["compte_source"] == numero_compte or t["compte_destination"] == numero_compte
    ]
    for t in txns_supprimees:
        transactions.remove(t)

    return {
        "succes": True,
        "compte_supprime": numero_compte,
        "transactions_supprimees": len(txns_supprimees)
    }

# Historique des transactions d'un compte
@app.get("/comptes/{numero_compte}/transactions", response_model=List[TransactionResponse])
def historique_transactions(numero_compte: str):
    compte = next((c for c in comptes if c["numero_compte"] == numero_compte), None)
    if not compte:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    historique = [
        t for t in transactions
        if t["compte_source"] == numero_compte or t["compte_destination"] == numero_compte
    ]
    return historique

# Virement
@app.post("/comptes/{numero_compte}/virement", response_model=TransactionResponse)
def virement(numero_compte: str, data: VirementData):
    if data.montant <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif")

    if numero_compte == data.numero_compte_destination:
        raise HTTPException(status_code=400, detail="Impossible de virer vers le même compte")

    source = next((c for c in comptes if c["numero_compte"] == numero_compte), None)
    if not source:
        raise HTTPException(status_code=404, detail="Compte source introuvable")

    destination = next((c for c in comptes if c["numero_compte"] == data.numero_compte_destination), None)
    if not destination:
        raise HTTPException(status_code=404, detail="Compte destination introuvable")

    if source["solde"] < data.montant:
        raise HTTPException(status_code=400, detail="Solde insuffisant")

    source["solde"] -= data.montant
    destination["solde"] += data.montant

    transaction = {
        "id": str(uuid.uuid4()),
        "type": "virement",
        "montant": data.montant,
        "date": datetime.now().isoformat(),
        "compte_source": numero_compte,
        "compte_destination": data.numero_compte_destination
    }
    transactions.append(transaction)
    return transaction