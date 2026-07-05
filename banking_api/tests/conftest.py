"""Fixtures partagées — Banking API v2."""
import os
import uuid
import pytest

# Désactiver Supabase → fallback mémoire
os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)

from main import app
import db
from auth import hash_password


def _reset():
    db._comptes.clear()
    db._transactions.clear()
    db._users.clear()


@pytest.fixture(autouse=True)
def _auto_reset():
    _reset()
    yield
    _reset()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    _reset()
    with TestClient(app) as c:
        yield c
    _reset()


# ── Utilisateurs de test ──────────────────────────────────────────────

@pytest.fixture
def admin_user():
    """Crée un utilisateur ADMIN dans la base in-memory."""
    user = {
        "id":            str(uuid.uuid4()),
        "username":      "admin_test",
        "password_hash": hash_password("admin123"),
        "email":         None,
        "role":          "ADMIN",
    }
    db._users.append(user)
    return user

@pytest.fixture
def client_user():
    """Crée un utilisateur CLIENT dans la base in-memory."""
    uid = uuid.uuid4().hex[:6]
    user = {
        "id":            str(uuid.uuid4()),
        "username":      f"client_{uid}",
        "password_hash": hash_password("client123"),
        "email":         f"client_{uid}@test.com",
        "role":          "CLIENT",
    }
    db._users.append(user)
    return user


# ── Tokens JWT ────────────────────────────────────────────────────────

@pytest.fixture
def admin_token(client, admin_user):
    """Retourne un Bearer token valide pour l'admin."""
    res = client.post("/auth/login", json={"username": admin_user["username"], "password": "admin123"})
    assert res.status_code == 200, res.json()
    return res.json()["access_token"]

@pytest.fixture
def client_token(client, client_user):
    """Retourne un Bearer token valide pour le client."""
    res = client.post("/auth/login", json={"username": client_user["username"], "password": "client123"})
    assert res.status_code == 200, res.json()
    return res.json()["access_token"]

@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}

@pytest.fixture
def client_headers(client_token):
    return {"Authorization": f"Bearer {client_token}"}


# ── Comptes de test ───────────────────────────────────────────────────

@pytest.fixture
def compte_creer(client, client_user, client_headers):
    """Crée un compte pour le client authentifié."""
    res = client.post("/comptes", json={
        "nom_titulaire": client_user["username"],
        "email":         client_user["email"],
    }, headers=client_headers)
    assert res.status_code == 201, res.json()
    return res.json()

@pytest.fixture
def deux_comptes(client, admin_user, admin_headers):
    """Crée deux comptes distincts (via ADMIN) avec dépôts initiaux."""
    uid = uuid.uuid4().hex[:6]

    # Créer deux users clients
    user_a = {"id": str(uuid.uuid4()), "username": f"src_{uid}", "password_hash": hash_password("x"), "email": f"src_{uid}@test.com", "role": "CLIENT"}
    user_b = {"id": str(uuid.uuid4()), "username": f"dst_{uid}", "password_hash": hash_password("x"), "email": f"dst_{uid}@test.com", "role": "CLIENT"}
    db._users.extend([user_a, user_b])

    a = client.post("/comptes", json={"nom_titulaire": "Source", "email": user_a["email"]}, headers=admin_headers).json()
    b = client.post("/comptes", json={"nom_titulaire": "Destination", "email": user_b["email"]}, headers=admin_headers).json()

    client.post(f"/comptes/{a['numero_compte']}/depot", json={"montant": 1000}, headers=admin_headers)
    client.post(f"/comptes/{b['numero_compte']}/depot", json={"montant": 500},  headers=admin_headers)

    a = client.get(f"/comptes/{a['numero_compte']}", headers=admin_headers).json()
    b = client.get(f"/comptes/{b['numero_compte']}", headers=admin_headers).json()
    return a, b
