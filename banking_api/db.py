"""Couche de persistence — Banking API v2.
Supabase (async httpx) en prod, listes in-memory en test/dev.
"""
import os
import uuid
import httpx
from datetime import datetime
from typing import Optional

SUPABASE_URL              = os.getenv("SUPABASE_URL", "https://lgghizadrwshujwipasn.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

REST_URL    = f"{SUPABASE_URL}/rest/v1"
USE_SUPABASE = bool(SUPABASE_SERVICE_ROLE_KEY)

_client: Optional[httpx.AsyncClient] = None

# ── Fallback in-memory ────────────────────────────────────────────────
_comptes: list[dict]      = []
_transactions: list[dict] = []
_users: list[dict]        = []


def _headers() -> dict:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }

async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=REST_URL, headers=_headers(), timeout=15.0)
    return _client


# ── Comptes ──────────────────────────────────────────────────────────

async def create_compte(data: dict) -> dict:
    data.setdefault("id", str(uuid.uuid4()))
    data.setdefault("date_creation", datetime.now().isoformat())
    data.setdefault("solde", "0")
    data.setdefault("type", "CURRENT")
    data.setdefault("status", "ACTIVE")
    data.setdefault("overdraft_limit", "0")
    data.setdefault("annual_rate", "0")

    if USE_SUPABASE:
        client  = await _get_client()
        headers = {**_headers(), "Prefer": "return=representation"}
        res     = await client.post("/comptes", json=data, headers=headers)
        res.raise_for_status()
        return res.json()[0]
    else:
        _comptes.append(data)
        return data

async def get_comptes() -> list[dict]:
    if USE_SUPABASE:
        client = await _get_client()
        res    = await client.get("/comptes", params={"select": "*", "order": "date_creation.desc"})
        res.raise_for_status()
        return res.json()
    return list(_comptes)

async def get_comptes_by_email(email: str) -> list[dict]:
    if USE_SUPABASE:
        client = await _get_client()
        res    = await client.get("/comptes", params={"select": "*", "email": f"eq.{email}"})
        res.raise_for_status()
        return res.json()
    return [c for c in _comptes if c.get("email") == email]

async def get_compte_by_numero(numero_compte: str) -> Optional[dict]:
    if USE_SUPABASE:
        client = await _get_client()
        res    = await client.get("/comptes", params={"select": "*", "numero_compte": f"eq.{numero_compte}"})
        res.raise_for_status()
        rows   = res.json()
        return rows[0] if rows else None
    return next((c for c in _comptes if c["numero_compte"] == numero_compte), None)

async def get_compte_by_email(email: str) -> Optional[dict]:
    if USE_SUPABASE:
        client = await _get_client()
        res    = await client.get("/comptes", params={"select": "*", "email": f"eq.{email}"})
        res.raise_for_status()
        rows   = res.json()
        return rows[0] if rows else None
    return next((c for c in _comptes if c["email"] == email), None)

async def update_solde(numero_compte: str, nouveau_solde: str) -> Optional[dict]:
    if USE_SUPABASE:
        client  = await _get_client()
        headers = {**_headers(), "Prefer": "return=representation"}
        res     = await client.patch(
            "/comptes",
            params={"numero_compte": f"eq.{numero_compte}"},
            json={"solde": nouveau_solde},
            headers=headers,
        )
        res.raise_for_status()
        rows = res.json()
        return rows[0] if rows else None
    for c in _comptes:
        if c["numero_compte"] == numero_compte:
            c["solde"] = nouveau_solde
            return c
    return None

async def update_status(numero_compte: str, status: str) -> Optional[dict]:
    if USE_SUPABASE:
        client  = await _get_client()
        headers = {**_headers(), "Prefer": "return=representation"}
        res     = await client.patch(
            "/comptes",
            params={"numero_compte": f"eq.{numero_compte}"},
            json={"status": status},
            headers=headers,
        )
        res.raise_for_status()
        rows = res.json()
        return rows[0] if rows else None
    for c in _comptes:
        if c["numero_compte"] == numero_compte:
            c["status"] = status
            return c
    return None

async def delete_compte(numero_compte: str) -> None:
    if USE_SUPABASE:
        client = await _get_client()
        res    = await client.delete("/comptes", params={"numero_compte": f"eq.{numero_compte}"})
        res.raise_for_status()
    else:
        _comptes[:] = [c for c in _comptes if c["numero_compte"] != numero_compte]


# ── Transactions ─────────────────────────────────────────────────────

async def create_transaction(data: dict) -> dict:
    data.setdefault("id", str(uuid.uuid4()))
    data.setdefault("date", datetime.now().isoformat())

    if USE_SUPABASE:
        client  = await _get_client()
        headers = {**_headers(), "Prefer": "return=representation"}
        res     = await client.post("/transactions", json=data, headers=headers)
        res.raise_for_status()
        return res.json()[0]
    _transactions.append(data)
    return data

async def get_transactions_by_compte(numero_compte: str) -> list[dict]:
    if USE_SUPABASE:
        client = await _get_client()
        res    = await client.get(
            "/transactions",
            params={
                "select": "*",
                "or": f"(compte_source.eq.{numero_compte},compte_destination.eq.{numero_compte})",
                "order": "date.desc",
            },
        )
        res.raise_for_status()
        return res.json()
    return [
        t for t in _transactions
        if t["compte_source"] == numero_compte or t.get("compte_destination") == numero_compte
    ]

async def delete_transactions_by_compte(numero_compte: str) -> int:
    if USE_SUPABASE:
        client  = await _get_client()
        headers = {**_headers(), "Prefer": "return=representation"}
        res     = await client.delete(
            "/transactions",
            params={"or": f"(compte_source.eq.{numero_compte},compte_destination.eq.{numero_compte})"},
            headers=headers,
        )
        res.raise_for_status()
        return len(res.json())
    before         = len(_transactions)
    _transactions[:] = [
        t for t in _transactions
        if t["compte_source"] != numero_compte and t.get("compte_destination") != numero_compte
    ]
    return before - len(_transactions)


# ── Users ─────────────────────────────────────────────────────────────

async def create_user(data: dict) -> dict:
    data.setdefault("id", str(uuid.uuid4()))
    if USE_SUPABASE:
        client  = await _get_client()
        headers = {**_headers(), "Prefer": "return=representation"}
        res     = await client.post("/users", json=data, headers=headers)
        res.raise_for_status()
        return res.json()[0]
    _users.append(data)
    return data

async def get_users() -> list[dict]:
    if USE_SUPABASE:
        client = await _get_client()
        res    = await client.get("/users", params={"select": "id,username,email,role"})
        res.raise_for_status()
        return res.json()
    return [{"id": u["id"], "username": u["username"], "email": u.get("email"), "role": u["role"]} for u in _users]

async def get_user_by_username(username: str) -> Optional[dict]:
    if USE_SUPABASE:
        client = await _get_client()
        res    = await client.get("/users", params={"select": "*", "username": f"eq.{username}"})
        res.raise_for_status()
        rows   = res.json()
        return rows[0] if rows else None
    return next((u for u in _users if u["username"] == username), None)

async def get_user_by_email(email: str) -> Optional[dict]:
    if USE_SUPABASE:
        client = await _get_client()
        res    = await client.get("/users", params={"select": "*", "email": f"eq.{email}"})
        res.raise_for_status()
        rows   = res.json()
        return rows[0] if rows else None
    return next((u for u in _users if u.get("email") == email), None)
