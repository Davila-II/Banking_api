"""Supabase async client with in-memory fallback — Banking API."""
import os
import uuid
import httpx
from datetime import datetime
from typing import Optional

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://lgghizadrwshujwipasn.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

REST_URL = f"{SUPABASE_URL}/rest/v1"
USE_SUPABASE = bool(SUPABASE_SERVICE_ROLE_KEY)

_client: Optional[httpx.AsyncClient] = None

# Fallback mémoire
_comptes: list[dict] = []
_transactions: list[dict] = []


def _headers() -> dict:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


async def _client_singleton() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=REST_URL, headers=_headers(), timeout=15.0)
    return _client


# ── Comptes ──────────────────────────────────────────────────────────

async def create_compte(data: dict) -> dict:
    if USE_SUPABASE:
        client = await _client_singleton()
        headers = {**_headers(), "Prefer": "return=representation"}
        res = await client.post("/comptes", json=data, headers=headers)
        res.raise_for_status()
        return res.json()[0]
    else:
        data["id"] = data.get("id", str(uuid.uuid4()))
        data["date_creation"] = data.get("date_creation", datetime.now().isoformat())
        _comptes.append(data)
        return data


async def get_comptes() -> list[dict]:
    if USE_SUPABASE:
        client = await _client_singleton()
        res = await client.get("/comptes", params={"select": "*", "order": "date_creation.desc"})
        res.raise_for_status()
        return res.json()
    else:
        return list(_comptes)


async def get_compte_by_numero(numero_compte: str) -> Optional[dict]:
    if USE_SUPABASE:
        client = await _client_singleton()
        res = await client.get(
            "/comptes",
            params={"select": "*", "numero_compte": f"eq.{numero_compte}"},
        )
        res.raise_for_status()
        rows = res.json()
        return rows[0] if rows else None
    else:
        return next((c for c in _comptes if c["numero_compte"] == numero_compte), None)


async def get_compte_by_email(email: str) -> Optional[dict]:
    if USE_SUPABASE:
        client = await _client_singleton()
        res = await client.get("/comptes", params={"select": "*", "email": f"eq.{email}"})
        res.raise_for_status()
        rows = res.json()
        return rows[0] if rows else None
    else:
        return next((c for c in _comptes if c["email"] == email), None)


async def delete_compte(numero_compte: str) -> dict:
    if USE_SUPABASE:
        client = await _client_singleton()
        res = await client.delete("/comptes", params={"numero_compte": f"eq.{numero_compte}"})
        res.raise_for_status()
    else:
        c = next((c for c in _comptes if c["numero_compte"] == numero_compte), None)
        if c:
            _comptes.remove(c)
        _transactions[:] = [
            t for t in _transactions
            if t["compte_source"] != numero_compte and t.get("compte_destination") != numero_compte
        ]
    return {"succes": True, "numero_compte": numero_compte}


async def update_solde(numero_compte: str, nouveau_solde: float) -> Optional[dict]:
    if USE_SUPABASE:
        client = await _client_singleton()
        headers = {**_headers(), "Prefer": "return=representation"}
        res = await client.patch(
            "/comptes",
            params={"numero_compte": f"eq.{numero_compte}"},
            json={"solde": nouveau_solde},
            headers=headers,
        )
        res.raise_for_status()
        rows = res.json()
        return rows[0] if rows else None
    else:
        for c in _comptes:
            if c["numero_compte"] == numero_compte:
                c["solde"] = nouveau_solde
                return c
        return None


# ── Transactions ─────────────────────────────────────────────────────

async def create_transaction(data: dict) -> dict:
    if USE_SUPABASE:
        client = await _client_singleton()
        headers = {**_headers(), "Prefer": "return=representation"}
        res = await client.post("/transactions", json=data, headers=headers)
        res.raise_for_status()
        return res.json()[0]
    else:
        data["id"] = data.get("id", str(uuid.uuid4()))
        data["date"] = data.get("date", datetime.now().isoformat())
        _transactions.append(data)
        return data


async def get_transactions_by_compte(numero_compte: str) -> list[dict]:
    if USE_SUPABASE:
        client = await _client_singleton()
        res = await client.get(
            "/transactions",
            params={
                "select": "*",
                "or": f"(compte_source.eq.{numero_compte},compte_destination.eq.{numero_compte})",
                "order": "date.desc",
            },
        )
        res.raise_for_status()
        return res.json()
    else:
        return [
            t for t in _transactions
            if t["compte_source"] == numero_compte or t.get("compte_destination") == numero_compte
        ]


async def delete_transactions_by_compte(numero_compte: str) -> int:
    if USE_SUPABASE:
        client = await _client_singleton()
        headers = {**_headers(), "Prefer": "return=representation"}
        res = await client.delete(
            "/transactions",
            params={"or": f"(compte_source.eq.{numero_compte},compte_destination.eq.{numero_compte})"},
            headers=headers,
        )
        res.raise_for_status()
        return len(res.json())
    else:
        before = len(_transactions)
        _transactions[:] = [
            t for t in _transactions
            if t["compte_source"] != numero_compte and t.get("compte_destination") != numero_compte
        ]
        return before - len(_transactions)
