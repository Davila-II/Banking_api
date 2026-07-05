"""Tests unitaires — Banking API v2.
Couvre tous les chemins identifiés + nouveaux (auth, statuts, types).
"""
from decimal import Decimal


# ============================================================
# Auth
# ============================================================

class TestLogin:
    def test_succes(self, client, admin_user):
        res = client.post("/auth/login", json={"username": "admin_test", "password": "admin123"})
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["role"] == "ADMIN"

    def test_mauvais_mot_de_passe(self, client, admin_user):
        res = client.post("/auth/login", json={"username": "admin_test", "password": "wrong"})
        assert res.status_code == 401

    def test_utilisateur_inconnu(self, client):
        res = client.post("/auth/login", json={"username": "ghost", "password": "x"})
        assert res.status_code == 401

    def test_sans_token_endpoint_protege(self, client):
        res = client.get("/comptes")
        assert res.status_code == 401


# ============================================================
# consulter_compte — 2 chemins
# ============================================================

class TestConsulterCompte:
    def test_compte_trouve(self, client, compte_creer, client_headers):
        res = client.get(f"/comptes/{compte_creer['numero_compte']}", headers=client_headers)
        assert res.status_code == 200
        assert res.json()["numero_compte"] == compte_creer["numero_compte"]

    def test_compte_introuvable(self, client, client_headers):
        res = client.get("/comptes/BK-NEXISTEPAS", headers=client_headers)
        assert res.status_code == 404

    def test_acces_compte_dautrui_interdit(self, client, deux_comptes, client_user, client_headers):
        a, _ = deux_comptes
        res = client.get(f"/comptes/{a['numero_compte']}", headers=client_headers)
        assert res.status_code == 403


# ============================================================
# creer_compte — 3 chemins
# ============================================================

class TestCreerCompte:
    def test_succes_admin(self, client, admin_headers):
        import uuid
        res = client.post("/comptes", json={
            "nom_titulaire": "Jean Dupont",
            "email": f"jean_{uuid.uuid4().hex[:4]}@test.com"
        }, headers=admin_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["numero_compte"].startswith("BK-")
        assert data["status"] == "ACTIVE"
        assert data["type"] == "CURRENT"

    def test_succes_client_son_email(self, client, client_user, client_headers):
        res = client.post("/comptes", json={
            "nom_titulaire": "Mon compte",
            "email": client_user["email"],
        }, headers=client_headers)
        assert res.status_code == 201

    def test_client_email_etranger_interdit(self, client, client_headers):
        res = client.post("/comptes", json={
            "nom_titulaire": "Autre",
            "email": "etranger@test.com"
        }, headers=client_headers)
        assert res.status_code == 403

    def test_compte_epargne(self, client, admin_headers):
        import uuid
        res = client.post("/comptes", json={
            "nom_titulaire": "Epargne",
            "email": f"sav_{uuid.uuid4().hex[:4]}@test.com",
            "type": "SAVINGS",
            "annual_rate": "0.03"
        }, headers=admin_headers)
        assert res.status_code == 201
        assert res.json()["type"] == "SAVINGS"


# ============================================================
# depot — 3 chemins
# ============================================================

class TestDepot:
    def test_montant_nul_ou_negatif(self, client, compte_creer, client_headers):
        nc = compte_creer["numero_compte"]
        assert client.post(f"/comptes/{nc}/depot", json={"montant": -50},  headers=client_headers).status_code == 422
        assert client.post(f"/comptes/{nc}/depot", json={"montant": 0},    headers=client_headers).status_code == 422

    def test_compte_introuvable(self, client, client_headers):
        res = client.post("/comptes/BK-NEXISTEPAS/depot", json={"montant": 100}, headers=client_headers)
        assert res.status_code == 404

    def test_succes(self, client, compte_creer, client_headers):
        nc  = compte_creer["numero_compte"]
        res = client.post(f"/comptes/{nc}/depot", json={"montant": 250}, headers=client_headers)
        assert res.status_code == 200
        assert res.json()["type"] == "depot"
        solde = client.get(f"/comptes/{nc}", headers=client_headers).json()["solde"]
        assert Decimal(str(solde)) == Decimal("250")

    def test_compte_gele(self, client, compte_creer, client_headers, admin_headers):
        nc = compte_creer["numero_compte"]
        client.post(f"/comptes/{nc}/freeze", headers=admin_headers)
        res = client.post(f"/comptes/{nc}/depot", json={"montant": 100}, headers=client_headers)
        assert res.status_code == 409


# ============================================================
# retrait — 4 chemins
# ============================================================

class TestRetrait:
    def test_montant_negatif(self, client, compte_creer, client_headers):
        res = client.post(f"/comptes/{compte_creer['numero_compte']}/retrait", json={"montant": -10}, headers=client_headers)
        assert res.status_code == 422

    def test_compte_introuvable(self, client, client_headers):
        res = client.post("/comptes/BK-NEXISTEPAS/retrait", json={"montant": 10}, headers=client_headers)
        assert res.status_code == 404

    def test_solde_insuffisant_savings(self, client, admin_headers):
        import uuid
        email = f"sav_{uuid.uuid4().hex[:4]}@test.com"
        c = client.post("/comptes", json={"nom_titulaire": "S", "email": email, "type": "SAVINGS"}, headers=admin_headers).json()
        nc = c["numero_compte"]
        client.post(f"/comptes/{nc}/depot", json={"montant": 100}, headers=admin_headers)
        res = client.post(f"/comptes/{nc}/retrait", json={"montant": 200}, headers=admin_headers)
        assert res.status_code == 422

    def test_succes(self, client, compte_creer, client_headers):
        nc = compte_creer["numero_compte"]
        client.post(f"/comptes/{nc}/depot", json={"montant": 500}, headers=client_headers)
        res = client.post(f"/comptes/{nc}/retrait", json={"montant": 200}, headers=client_headers)
        assert res.status_code == 200
        assert res.json()["type"] == "retrait"
        solde = client.get(f"/comptes/{nc}", headers=client_headers).json()["solde"]
        assert Decimal(str(solde)) == Decimal("300")


# ============================================================
# virement — 6 chemins
# ============================================================

class TestVirement:
    def test_montant_negatif(self, client, deux_comptes, admin_headers):
        src, _ = deux_comptes
        res = client.post(f"/comptes/{src['numero_compte']}/virement",
                          json={"numero_compte_destination": "BK-X", "montant": -10},
                          headers=admin_headers)
        assert res.status_code == 422

    def test_meme_compte(self, client, deux_comptes, admin_headers):
        src, _ = deux_comptes
        res = client.post(f"/comptes/{src['numero_compte']}/virement",
                          json={"numero_compte_destination": src["numero_compte"], "montant": 10},
                          headers=admin_headers)
        assert res.status_code == 422

    def test_source_introuvable(self, client, deux_comptes, admin_headers):
        _, dst = deux_comptes
        res = client.post("/comptes/BK-NEXISTEPAS/virement",
                          json={"numero_compte_destination": dst["numero_compte"], "montant": 10},
                          headers=admin_headers)
        assert res.status_code == 404

    def test_destination_introuvable(self, client, deux_comptes, admin_headers):
        src, _ = deux_comptes
        res = client.post(f"/comptes/{src['numero_compte']}/virement",
                          json={"numero_compte_destination": "BK-NEXISTEPAS", "montant": 10},
                          headers=admin_headers)
        assert res.status_code == 404

    def test_solde_insuffisant(self, client, deux_comptes, admin_headers):
        src, dst = deux_comptes
        res = client.post(f"/comptes/{src['numero_compte']}/virement",
                          json={"numero_compte_destination": dst["numero_compte"], "montant": 99999},
                          headers=admin_headers)
        assert res.status_code == 422

    def test_succes(self, client, deux_comptes, admin_headers):
        src, dst = deux_comptes
        res = client.post(f"/comptes/{src['numero_compte']}/virement",
                          json={"numero_compte_destination": dst["numero_compte"], "montant": 300},
                          headers=admin_headers)
        assert res.status_code == 200
        src_after = client.get(f"/comptes/{src['numero_compte']}", headers=admin_headers).json()
        dst_after = client.get(f"/comptes/{dst['numero_compte']}", headers=admin_headers).json()
        assert Decimal(str(src_after["solde"])) == Decimal("700")
        assert Decimal(str(dst_after["solde"])) == Decimal("800")


# ============================================================
# Statuts de compte (ADMIN)
# ============================================================

class TestStatutsCompte:
    def test_freeze_puis_reactivate(self, client, compte_creer, admin_headers, client_headers):
        nc = compte_creer["numero_compte"]

        res = client.post(f"/comptes/{nc}/freeze", headers=admin_headers)
        assert res.status_code == 200
        assert client.get(f"/comptes/{nc}", headers=client_headers).json()["status"] == "FROZEN"

        res = client.post(f"/comptes/{nc}/reactivate", headers=admin_headers)
        assert res.status_code == 200
        assert client.get(f"/comptes/{nc}", headers=client_headers).json()["status"] == "ACTIVE"

    def test_close_solde_nul(self, client, compte_creer, admin_headers):
        nc  = compte_creer["numero_compte"]
        res = client.post(f"/comptes/{nc}/close", headers=admin_headers)
        assert res.status_code == 200
        assert res.json()["status"] == "CLOSED"

    def test_close_solde_non_nul(self, client, compte_creer, admin_headers, client_headers):
        nc = compte_creer["numero_compte"]
        client.post(f"/comptes/{nc}/depot", json={"montant": 100}, headers=client_headers)
        res = client.post(f"/comptes/{nc}/close", headers=admin_headers)
        assert res.status_code == 409

    def test_reactivate_closed_impossible(self, client, compte_creer, admin_headers):
        nc = compte_creer["numero_compte"]
        client.post(f"/comptes/{nc}/close", headers=admin_headers)
        res = client.post(f"/comptes/{nc}/reactivate", headers=admin_headers)
        assert res.status_code == 409

    def test_freeze_non_admin(self, client, compte_creer, client_headers):
        nc  = compte_creer["numero_compte"]
        res = client.post(f"/comptes/{nc}/freeze", headers=client_headers)
        assert res.status_code == 403


# ============================================================
# lister_comptes
# ============================================================

class TestListerComptes:
    def test_admin_voit_tout(self, client, deux_comptes, admin_headers):
        res = client.get("/comptes", headers=admin_headers)
        assert res.status_code == 200
        assert len(res.json()) >= 2

    def test_client_voit_ses_comptes(self, client, client_user, client_headers):
        res = client.get("/comptes", headers=client_headers)
        assert res.status_code == 200
        for c in res.json():
            assert c["email"] == client_user["email"]


# ============================================================
# supprimer_compte
# ============================================================

class TestSupprimerCompte:
    def test_compte_introuvable(self, client, admin_headers):
        assert client.delete("/comptes/BK-NEXISTEPAS", headers=admin_headers).status_code == 404

    def test_client_ne_peut_pas_supprimer(self, client, compte_creer, client_headers):
        nc  = compte_creer["numero_compte"]
        res = client.delete(f"/comptes/{nc}", headers=client_headers)
        assert res.status_code == 403

    def test_succes_admin(self, client, compte_creer, admin_headers, client_headers):
        nc  = compte_creer["numero_compte"]
        res = client.delete(f"/comptes/{nc}", headers=admin_headers)
        assert res.status_code == 200
        assert res.json()["succes"] is True
        assert client.get(f"/comptes/{nc}", headers=admin_headers).status_code == 404


# ============================================================
# historique_transactions
# ============================================================

class TestHistoriqueTransactions:
    def test_compte_introuvable(self, client, client_headers):
        assert client.get("/comptes/BK-NEXISTEPAS/transactions", headers=client_headers).status_code == 404

    def test_vide(self, client, compte_creer, client_headers):
        res = client.get(f"/comptes/{compte_creer['numero_compte']}/transactions", headers=client_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_avec_transactions(self, client, compte_creer, client_headers):
        nc = compte_creer["numero_compte"]
        client.post(f"/comptes/{nc}/depot",   json={"montant": 100}, headers=client_headers)
        client.post(f"/comptes/{nc}/depot",   json={"montant": 200}, headers=client_headers)
        res = client.get(f"/comptes/{nc}/transactions", headers=client_headers)
        assert res.status_code == 200
        assert len(res.json()) == 2
