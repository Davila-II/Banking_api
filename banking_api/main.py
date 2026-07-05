"""Banking API v2 — FastAPI + JWT + types de compte + statuts."""
import uuid
from decimal import Decimal
from typing import List

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

import db
from auth import (
    TokenClaims, get_current_user, require_admin,
    hash_password, verify_password, create_access_token,
)
from models import (
    AccountType,
    CompteCreate, CompteResponse,
    TransactionMontant, VirementData, TransactionResponse,
    LoginRequest, LoginResponse,
    UserCreate, UserResponse,
)

# ── App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Banking API",
    description="API REST bancaire — JWT, types de compte (courant/épargne), statuts, virements.",
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


# ── Helpers métier ────────────────────────────────────────────────────

def _ensure_active(compte: dict) -> None:
    status = compte.get("status", "ACTIVE")
    if status != "ACTIVE":
        raise HTTPException(status_code=409, detail=f"Compte {compte['numero_compte']} est {status} — opération impossible")

def _ensure_funds(compte: dict, montant: Decimal) -> None:
    solde    = Decimal(str(compte.get("solde", "0")))
    overdraft = Decimal(str(compte.get("overdraft_limit", "0")))
    if compte.get("type", "CURRENT") == "SAVINGS":
        if solde < montant:
            raise HTTPException(status_code=422, detail="Solde insuffisant (compte épargne : découvert interdit)")
    else:
        if solde - montant < -overdraft:
            raise HTTPException(status_code=422, detail=f"Découvert autorisé dépassé (limite : {overdraft})")

def _ensure_owner_or_admin(compte: dict, user: TokenClaims) -> None:
    if user.role == "ADMIN":
        return
    if user.email != compte.get("email"):
        raise HTTPException(status_code=403, detail="Accès interdit : ce compte ne vous appartient pas")


# ── Auth ──────────────────────────────────────────────────────────────

@app.post("/auth/login", response_model=LoginResponse, tags=["auth"])
async def login(data: LoginRequest):
    """Authentification → retourne un Bearer token JWT."""
    user = await db.get_user_by_username(data.username)
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    token = create_access_token({
        "sub":      user["id"],
        "username": user["username"],
        "email":    user.get("email"),
        "role":     user["role"],
    })
    return LoginResponse(access_token=token, role=user["role"])


# ── Users (ADMIN) ─────────────────────────────────────────────────────

@app.post("/users", response_model=UserResponse, status_code=201, tags=["users"])
async def create_user(data: UserCreate, _admin=Depends(require_admin)):
    """Crée un utilisateur (ADMIN uniquement)."""
    if await db.get_user_by_username(data.username):
        raise HTTPException(status_code=400, detail="Ce nom d'utilisateur est déjà pris")
    user = await db.create_user({
        "username":      data.username,
        "password_hash": hash_password(data.password),
        "email":         data.email,
        "role":          data.role.value,
    })
    return user

@app.get("/users", response_model=List[UserResponse], tags=["users"])
async def list_users(_admin=Depends(require_admin)):
    """Liste tous les utilisateurs (ADMIN uniquement)."""
    return await db.get_users()


# ── Comptes ───────────────────────────────────────────────────────────

@app.post("/comptes", response_model=CompteResponse, status_code=201, tags=["comptes"])
async def creer_compte(data: CompteCreate, user: TokenClaims = Depends(get_current_user)):
    """Crée un compte.
    - CLIENT : doit utiliser son propre email.
    - ADMIN  : peut créer pour n'importe quel email.
    """
    if user.role == "CLIENT" and data.email != user.email:
        raise HTTPException(status_code=403, detail="Un client ne peut ouvrir un compte qu'avec sa propre adresse email")

    compte = await db.create_compte({
        "numero_compte":  "BK-" + str(uuid.uuid4())[:8].upper(),
        "nom_titulaire":  data.nom_titulaire,
        "email":          data.email,
        "solde":          "0",
        "type":           data.type.value,
        "status":         "ACTIVE",
        "overdraft_limit": str(data.overdraft_limit),
        "annual_rate":    str(data.annual_rate),
    })
    return compte

@app.get("/comptes", response_model=List[CompteResponse], tags=["comptes"])
async def lister_comptes(user: TokenClaims = Depends(get_current_user)):
    """Liste les comptes.
    - CLIENT : ses propres comptes uniquement.
    - ADMIN  : tous les comptes.
    """
    if user.role == "ADMIN":
        return await db.get_comptes()
    return await db.get_comptes_by_email(user.email)

@app.get("/comptes/{numero_compte}", response_model=CompteResponse, tags=["comptes"])
async def consulter_compte(numero_compte: str, user: TokenClaims = Depends(get_current_user)):
    compte = await db.get_compte_by_numero(numero_compte)
    if not compte:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    _ensure_owner_or_admin(compte, user)
    return compte


# ── Opérations bancaires ──────────────────────────────────────────────

@app.post("/comptes/{numero_compte}/depot", response_model=TransactionResponse, tags=["opérations"])
async def depot(numero_compte: str, data: TransactionMontant, user: TokenClaims = Depends(get_current_user)):
    compte = await db.get_compte_by_numero(numero_compte)
    if not compte:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    _ensure_owner_or_admin(compte, user)
    _ensure_active(compte)

    nouveau_solde = Decimal(str(compte["solde"])) + data.montant
    await db.update_solde(numero_compte, str(nouveau_solde))
    return await db.create_transaction({
        "type":               "depot",
        "montant":            str(data.montant),
        "compte_source":      numero_compte,
        "compte_destination": None,
    })

@app.post("/comptes/{numero_compte}/retrait", response_model=TransactionResponse, tags=["opérations"])
async def retrait(numero_compte: str, data: TransactionMontant, user: TokenClaims = Depends(get_current_user)):
    compte = await db.get_compte_by_numero(numero_compte)
    if not compte:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    _ensure_owner_or_admin(compte, user)
    _ensure_active(compte)
    _ensure_funds(compte, data.montant)

    nouveau_solde = Decimal(str(compte["solde"])) - data.montant
    await db.update_solde(numero_compte, str(nouveau_solde))
    return await db.create_transaction({
        "type":               "retrait",
        "montant":            str(data.montant),
        "compte_source":      numero_compte,
        "compte_destination": None,
    })

@app.post("/comptes/{numero_compte}/virement", response_model=TransactionResponse, tags=["opérations"])
async def virement(numero_compte: str, data: VirementData, user: TokenClaims = Depends(get_current_user)):
    if numero_compte == data.numero_compte_destination:
        raise HTTPException(status_code=422, detail="Impossible de virer vers le même compte")

    source = await db.get_compte_by_numero(numero_compte)
    if not source:
        raise HTTPException(status_code=404, detail="Compte source introuvable")
    _ensure_owner_or_admin(source, user)

    destination = await db.get_compte_by_numero(data.numero_compte_destination)
    if not destination:
        raise HTTPException(status_code=404, detail="Compte destination introuvable")

    _ensure_active(source)
    _ensure_active(destination)
    _ensure_funds(source, data.montant)

    await db.update_solde(numero_compte, str(Decimal(str(source["solde"])) - data.montant))
    await db.update_solde(data.numero_compte_destination, str(Decimal(str(destination["solde"])) + data.montant))

    return await db.create_transaction({
        "type":               "virement",
        "montant":            str(data.montant),
        "compte_source":      numero_compte,
        "compte_destination": data.numero_compte_destination,
    })

@app.get("/comptes/{numero_compte}/transactions", response_model=List[TransactionResponse], tags=["opérations"])
async def historique_transactions(numero_compte: str, user: TokenClaims = Depends(get_current_user)):
    compte = await db.get_compte_by_numero(numero_compte)
    if not compte:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    _ensure_owner_or_admin(compte, user)
    return await db.get_transactions_by_compte(numero_compte)


# ── Admin — gestion des statuts ───────────────────────────────────────

@app.post("/comptes/{numero_compte}/freeze", tags=["admin"])
async def freeze_compte(numero_compte: str, _admin=Depends(require_admin)):
    """Gèle un compte (ADMIN uniquement)."""
    if not await db.get_compte_by_numero(numero_compte):
        raise HTTPException(status_code=404, detail="Compte introuvable")
    await db.update_status(numero_compte, "FROZEN")
    return {"succes": True, "status": "FROZEN", "numero_compte": numero_compte}

@app.post("/comptes/{numero_compte}/reactivate", tags=["admin"])
async def reactivate_compte(numero_compte: str, _admin=Depends(require_admin)):
    """Réactive un compte gelé (ADMIN uniquement). Impossible sur un compte CLOSED."""
    compte = await db.get_compte_by_numero(numero_compte)
    if not compte:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    if compte.get("status") == "CLOSED":
        raise HTTPException(status_code=409, detail="Impossible de réactiver un compte clôturé (état définitif)")
    await db.update_status(numero_compte, "ACTIVE")
    return {"succes": True, "status": "ACTIVE", "numero_compte": numero_compte}

@app.post("/comptes/{numero_compte}/close", tags=["admin"])
async def close_compte(numero_compte: str, _admin=Depends(require_admin)):
    """Clôture un compte (ADMIN uniquement). Le solde doit être nul."""
    compte = await db.get_compte_by_numero(numero_compte)
    if not compte:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    if Decimal(str(compte.get("solde", "0"))) != 0:
        raise HTTPException(status_code=409, detail="Impossible de clôturer un compte dont le solde n'est pas nul")
    await db.update_status(numero_compte, "CLOSED")
    return {"succes": True, "status": "CLOSED", "numero_compte": numero_compte}

@app.delete("/comptes/{numero_compte}", tags=["admin"])
async def supprimer_compte(numero_compte: str, _admin=Depends(require_admin)):
    """Supprime un compte et ses transactions (ADMIN uniquement)."""
    if not await db.get_compte_by_numero(numero_compte):
        raise HTTPException(status_code=404, detail="Compte introuvable")
    nb_txns = await db.delete_transactions_by_compte(numero_compte)
    await db.delete_compte(numero_compte)
    return {"succes": True, "compte_supprime": numero_compte, "transactions_supprimees": nb_txns}