"""Fixtures partagées pour les tests Banking API."""
import pytest
import os
import uuid

# Désactiver Supabase pour les tests (fallback mémoire)
os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)

from main import app
import db


def _reset_state():
    """Réinitialise les listes mémoire entre les tests."""
    db._comptes.clear()
    db._transactions.clear()


@pytest.fixture(autouse=True)
def _auto_reset():
    """Reset du state avant chaque test."""
    _reset_state()


@pytest.fixture
def client():
    """Client de test FastAPI."""
    from fastapi.testclient import TestClient
    _reset_state()
    with TestClient(app) as c:
        yield c
    _reset_state()


@pytest.fixture
def compte_creer(client):
    """Crée un compte de test unique et le retourne."""
    uid = uuid.uuid4().hex[:8]
    res = client.post("/comptes", json={
        "nom_titulaire": f"Alice {uid}",
        "email": f"alice_{uid}@test.com"
    })
    assert res.status_code == 200, f"Création échouée: {res.json()}"
    return res.json()


@pytest.fixture
def deux_comptes(client):
    """Crée deux comptes de test avec dépôts initiaux."""
    uid = uuid.uuid4().hex[:8]
    a = client.post("/comptes", json={
        "nom_titulaire": "Source",
        "email": f"source_{uid}@test.com"
    }).json()

    b = client.post("/comptes", json={
        "nom_titulaire": "Destination",
        "email": f"dest_{uid}@test.com"
    }).json()

    client.post(f"/comptes/{a['numero_compte']}/depot", json={"montant": 1000})
    client.post(f"/comptes/{b['numero_compte']}/depot", json={"montant": 500})

    a = client.get(f"/comptes/{a['numero_compte']}").json()
    b = client.get(f"/comptes/{b['numero_compte']}").json()
    return a, b
