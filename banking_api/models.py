"""Schémas Pydantic partagés — Banking API v2."""
from enum import Enum
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator


# ── Enums ────────────────────────────────────────────────────────────

class AccountType(str, Enum):
    CURRENT = "CURRENT"   # Compte courant (découvert autorisé)
    SAVINGS = "SAVINGS"   # Compte épargne (taux d'intérêt, pas de découvert)

class AccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"

class Role(str, Enum):
    CLIENT = "CLIENT"
    ADMIN  = "ADMIN"


# ── Auth ─────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


# ── Users ─────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    role: Role = Role.CLIENT

class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    role: str


# ── Comptes ──────────────────────────────────────────────────────────

class CompteCreate(BaseModel):
    nom_titulaire: str
    email: str
    type: AccountType = AccountType.CURRENT
    overdraft_limit: Decimal = Decimal("0")   # Plafond découvert (CURRENT uniquement)
    annual_rate: Decimal = Decimal("0.00")    # Taux annuel (SAVINGS uniquement)

    @field_validator("overdraft_limit")
    @classmethod
    def overdraft_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Le plafond de découvert ne peut pas être négatif")
        return v

    @field_validator("annual_rate")
    @classmethod
    def rate_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Le taux annuel ne peut pas être négatif")
        return v

class CompteResponse(BaseModel):
    id: str
    numero_compte: str
    nom_titulaire: str
    email: str
    solde: Decimal
    type: str = "CURRENT"
    status: str = "ACTIVE"
    overdraft_limit: Decimal = Decimal("0")
    annual_rate: Decimal = Decimal("0")
    date_creation: str


# ── Transactions ─────────────────────────────────────────────────────

class TransactionMontant(BaseModel):
    montant: Decimal

    @field_validator("montant")
    @classmethod
    def montant_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Le montant doit être strictement positif")
        return v

class VirementData(BaseModel):
    numero_compte_destination: str
    montant: Decimal

    @field_validator("montant")
    @classmethod
    def montant_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Le montant doit être strictement positif")
        return v

class TransactionResponse(BaseModel):
    id: str
    type: str
    montant: Decimal
    date: str
    compte_source: str
    compte_destination: Optional[str] = None
