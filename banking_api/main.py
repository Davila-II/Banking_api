from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

from db import (
    create_compte,
    get_comptes,
    get_compte_by_numero,
    get_compte_by_email,
    delete_compte,
    update_solde,
    create_transaction,
    get_transactions_by_compte,
)

app = FastAPI(
    title="Banking API",
    description="API REST pour la gestion de comptes bancaires — dépôts et retraits",
    version="2.0.0",
    docs_url="/api-docs",
    redoc_url="/api-redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Schémas ──────────────────────────────────────────────────────────


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
    compte_destination: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────


def _format_compte(c: dict) -> dict:
    return {
        "id": c["id"],
        "numero_compte": c["numero_compte"],
        "nom_titulaire": c["nom_titulaire"],
        "email": c["email"],
        "solde": float(c["solde"]),
        "date_creation": c["date_creation"],
    }


def _format_transaction(t: dict) -> dict:
    return {
        "id": t["id"],
        "type": t["type"],
        "montant": float(t["montant"]),
        "date": t["date"],
        "compte_source": t["compte_source"],
        "compte_destination": t.get("compte_destination"),
    }


# ── Endpoints ────────────────────────────────────────────────────────


@app.post("/comptes", response_model=CompteResponse)
async def creer_compte(data: CompteCreate):
    existing = await get_compte_by_email(data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    nouveau = await create_compte({
        "numero_compte": "BK-" + str(uuid.uuid4())[:8].upper(),
        "nom_titulaire": data.nom_titulaire,
        "email": data.email,
        "solde": 0,
    })
    return _format_compte(nouveau)


@app.get("/comptes", response_model=List[CompteResponse])
async def lister_comptes():
    comptes = await get_comptes()
    return [_format_compte(c) for c in comptes]


@app.get("/comptes/{numero_compte}", response_model=CompteResponse)
async def consulter_compte(numero_compte: str):
    compte = await get_compte_by_numero(numero_compte)
    if not compte:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    return _format_compte(compte)


@app.post("/comptes/{numero_compte}/depot", response_model=TransactionResponse)
async def depot(numero_compte: str, data: TransactionMontant):
    if data.montant <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif")

    compte = await get_compte_by_numero(numero_compte)
    if not compte:
        raise HTTPException(status_code=404, detail="Compte introuvable")

    nouveau_solde = float(compte["solde"]) + data.montant
    await update_solde(numero_compte, nouveau_solde)

    txn = await create_transaction({
        "type": "depot",
        "montant": data.montant,
        "compte_source": numero_compte,
    })
    return _format_transaction(txn)


@app.post("/comptes/{numero_compte}/retrait", response_model=TransactionResponse)
async def retrait(numero_compte: str, data: TransactionMontant):
    if data.montant <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif")

    compte = await get_compte_by_numero(numero_compte)
    if not compte:
        raise HTTPException(status_code=404, detail="Compte introuvable")

    if float(compte["solde"]) < data.montant:
        raise HTTPException(status_code=400, detail="Solde insuffisant")

    nouveau_solde = float(compte["solde"]) - data.montant
    await update_solde(numero_compte, nouveau_solde)

    txn = await create_transaction({
        "type": "retrait",
        "montant": data.montant,
        "compte_source": numero_compte,
    })
    return _format_transaction(txn)


@app.delete("/comptes/{numero_compte}")
async def supprimer_compte(numero_compte: str):
    compte = await get_compte_by_numero(numero_compte)
    if not compte:
        raise HTTPException(status_code=404, detail="Compte introuvable")

    # ON DELETE CASCADE sur transactions compte_source + SET NULL sur compte_destination
    await delete_compte(numero_compte)

    return {
        "succes": True,
        "compte_supprime": numero_compte,
    }


@app.get("/comptes/{numero_compte}/transactions", response_model=List[TransactionResponse])
async def historique_transactions(numero_compte: str):
    compte = await get_compte_by_numero(numero_compte)
    if not compte:
        raise HTTPException(status_code=404, detail="Compte introuvable")

    txns = await get_transactions_by_compte(numero_compte)
    return [_format_transaction(t) for t in txns]


@app.post("/comptes/{numero_compte}/virement", response_model=TransactionResponse)
async def virement(numero_compte: str, data: VirementData):
    if data.montant <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif")

    if numero_compte == data.numero_compte_destination:
        raise HTTPException(status_code=400, detail="Impossible de virer vers le même compte")

    source = await get_compte_by_numero(numero_compte)
    if not source:
        raise HTTPException(status_code=404, detail="Compte source introuvable")

    destination = await get_compte_by_numero(data.numero_compte_destination)
    if not destination:
        raise HTTPException(status_code=404, detail="Compte destination introuvable")

    if float(source["solde"]) < data.montant:
        raise HTTPException(status_code=400, detail="Solde insuffisant")

    nouveau_solde_source = float(source["solde"]) - data.montant
    nouveau_solde_dest = float(destination["solde"]) + data.montant

    await update_solde(numero_compte, nouveau_solde_source)
    await update_solde(data.numero_compte_destination, nouveau_solde_dest)

    txn = await create_transaction({
        "type": "virement",
        "montant": data.montant,
        "compte_source": numero_compte,
        "compte_destination": data.numero_compte_destination,
    })
    return _format_transaction(txn)
