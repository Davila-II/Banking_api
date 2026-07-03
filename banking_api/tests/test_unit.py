"""Tests unitaires — Banking API.
Couvre les 18 chemins identifiés dans l'analyse CFG (cfg_analysis.html)
+ cas supplémentaires (GET /comptes, DELETE, liste vide, etc.).
"""

# ============================================================
# consulter_compte — 2 chemins
# ============================================================

class TestConsulterCompte:
    """GET /comptes/{numero_compte}"""

    def test_compte_trouve(self, client, compte_creer):
        """PATH 1: Compte trouvé → 200 avec les infos du compte."""
        res = client.get(f"/comptes/{compte_creer['numero_compte']}")
        assert res.status_code == 200
        data = res.json()
        assert data["numero_compte"] == compte_creer["numero_compte"]
        assert data["nom_titulaire"] == compte_creer["nom_titulaire"]
        assert data["email"] == compte_creer["email"]
        assert data["solde"] == 0.0

    def test_compte_introuvable(self, client):
        """PATH 2: Compte inexistant → 404."""
        res = client.get("/comptes/BK-NEXISTEPAS")
        assert res.status_code == 404
        assert "introuvable" in res.json()["detail"].lower()


# ============================================================
# creer_compte — 3 chemins
# ============================================================

class TestCreerCompte:
    """POST /comptes"""

    def test_succes_premier_compte(self, client):
        """PATH 1: Aucun email existant → 200, compte créé."""
        res = client.post("/comptes", json={
            "nom_titulaire": "Jean Dupont",
            "email": "jean@test.com"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["nom_titulaire"] == "Jean Dupont"
        assert data["email"] == "jean@test.com"
        assert data["solde"] == 0.0
        assert data["numero_compte"].startswith("BK-")
        assert len(data["id"]) > 0

    def test_succes_deuxieme_compte(self, client, compte_creer):
        """PATH 2: Un compte existe déjà, email différent → 200."""
        res = client.post("/comptes", json={
            "nom_titulaire": "Bob Martin",
            "email": "bob@test.com"
        })
        assert res.status_code == 200
        assert res.json()["email"] == "bob@test.com"

    def test_email_deja_utilise(self, client, compte_creer):
        """PATH 3: Email déjà utilisé → 400."""
        res = client.post("/comptes", json={
            "nom_titulaire": "Autre",
            "email": compte_creer["email"]  # même email que compte_creer
        })
        assert res.status_code == 400
        assert "email" in res.json()["detail"].lower()


# ============================================================
# depot — 3 chemins
# ============================================================

class TestDepot:
    """POST /comptes/{numero}/depot"""

    def test_montant_negatif(self, client, compte_creer):
        """PATH 1: Montant ≤ 0 → 400."""
        res = client.post(
            f"/comptes/{compte_creer['numero_compte']}/depot",
            json={"montant": -50}
        )
        assert res.status_code == 400
        res2 = client.post(
            f"/comptes/{compte_creer['numero_compte']}/depot",
            json={"montant": 0}
        )
        assert res2.status_code == 400

    def test_compte_introuvable(self, client):
        """PATH 2: Compte inexistant → 404."""
        res = client.post("/comptes/BK-NEXISTEPAS/depot", json={"montant": 100})
        assert res.status_code == 404

    def test_succes(self, client, compte_creer):
        """PATH 3: Dépôt valide → 200, solde mis à jour, transaction créée."""
        res = client.post(
            f"/comptes/{compte_creer['numero_compte']}/depot",
            json={"montant": 250}
        )
        assert res.status_code == 200
        txn = res.json()
        assert txn["type"] == "depot"
        assert txn["montant"] == 250.0
        assert txn["compte_source"] == compte_creer["numero_compte"]
        assert txn["compte_destination"] is None

        # Vérifier le solde
        c = client.get(f"/comptes/{compte_creer['numero_compte']}").json()
        assert c["solde"] == 250.0


# ============================================================
# retrait — 4 chemins
# ============================================================

class TestRetrait:
    """POST /comptes/{numero}/retrait"""

    def test_montant_negatif(self, client, compte_creer):
        """PATH 1: Montant ≤ 0 → 400."""
        res = client.post(
            f"/comptes/{compte_creer['numero_compte']}/retrait",
            json={"montant": -10}
        )
        assert res.status_code == 400

    def test_compte_introuvable(self, client):
        """PATH 2: Compte inexistant → 404."""
        res = client.post("/comptes/BK-NEXISTEPAS/retrait", json={"montant": 10})
        assert res.status_code == 404

    def test_solde_insuffisant(self, client, compte_creer):
        """PATH 3: Solde insuffisant → 400."""
        # Solde = 0, retrait = 100
        res = client.post(
            f"/comptes/{compte_creer['numero_compte']}/retrait",
            json={"montant": 100}
        )
        assert res.status_code == 400
        assert "insuffisant" in res.json()["detail"].lower()

    def test_succes(self, client, compte_creer):
        """PATH 4: Retrait valide → 200."""
        # D'abord, approvisionner le compte
        client.post(
            f"/comptes/{compte_creer['numero_compte']}/depot",
            json={"montant": 500}
        )
        res = client.post(
            f"/comptes/{compte_creer['numero_compte']}/retrait",
            json={"montant": 200}
        )
        assert res.status_code == 200
        txn = res.json()
        assert txn["type"] == "retrait"
        assert txn["montant"] == 200.0

        c = client.get(f"/comptes/{compte_creer['numero_compte']}").json()
        assert c["solde"] == 300.0


# ============================================================
# virement — 6 chemins
# ============================================================

class TestVirement:
    """POST /comptes/{numero}/virement"""

    def test_montant_negatif(self, client, deux_comptes):
        """PATH 1: Montant ≤ 0 → 400."""
        src, _ = deux_comptes
        res = client.post(
            f"/comptes/{src['numero_compte']}/virement",
            json={"numero_compte_destination": "BK-NEXISTE", "montant": -10}
        )
        assert res.status_code == 400

    def test_meme_compte(self, client, deux_comptes):
        """PATH 2: Source = destination → 400."""
        src, _ = deux_comptes
        res = client.post(
            f"/comptes/{src['numero_compte']}/virement",
            json={"numero_compte_destination": src["numero_compte"], "montant": 10}
        )
        assert res.status_code == 400
        assert "même" in res.json()["detail"].lower()

    def test_source_introuvable(self, client, deux_comptes):
        """PATH 3: Compte source inexistant → 404."""
        _, dst = deux_comptes
        res = client.post(
            "/comptes/BK-NEXISTEPAS/virement",
            json={"numero_compte_destination": dst["numero_compte"], "montant": 10}
        )
        assert res.status_code == 404
        assert "source" in res.json()["detail"].lower()

    def test_destination_introuvable(self, client, deux_comptes):
        """PATH 4: Compte destination inexistant → 404."""
        src, _ = deux_comptes
        res = client.post(
            f"/comptes/{src['numero_compte']}/virement",
            json={"numero_compte_destination": "BK-NEXISTEPAS", "montant": 10}
        )
        assert res.status_code == 404
        assert "destination" in res.json()["detail"].lower()

    def test_solde_insuffisant(self, client, deux_comptes):
        """PATH 5: Solde source insuffisant → 400."""
        src, dst = deux_comptes
        res = client.post(
            f"/comptes/{src['numero_compte']}/virement",
            json={
                "numero_compte_destination": dst["numero_compte"],
                "montant": 99999  # > 1000
            }
        )
        assert res.status_code == 400
        assert "insuffisant" in res.json()["detail"].lower()

    def test_succes(self, client, deux_comptes):
        """PATH 6: Virement valide → 200, deux soldes mis à jour."""
        src, dst = deux_comptes
        res = client.post(
            f"/comptes/{src['numero_compte']}/virement",
            json={
                "numero_compte_destination": dst["numero_compte"],
                "montant": 300
            }
        )
        assert res.status_code == 200
        txn = res.json()
        assert txn["type"] == "virement"
        assert txn["montant"] == 300.0
        assert txn["compte_source"] == src["numero_compte"]
        assert txn["compte_destination"] == dst["numero_compte"]

        # Vérifier les soldes
        src_after = client.get(f"/comptes/{src['numero_compte']}").json()
        dst_after = client.get(f"/comptes/{dst['numero_compte']}").json()
        assert src_after["solde"] == 700.0   # 1000 - 300
        assert dst_after["solde"] == 800.0   # 500 + 300


# ============================================================
# lister_comptes
# ============================================================

class TestListerComptes:
    """GET /comptes"""

    def test_liste_vide(self, client):
        """Aucun compte → liste vide."""
        # Nettoyer tout compte existant
        comptes = client.get("/comptes").json()
        for c in comptes:
            client.delete(f"/comptes/{c['numero_compte']}")
        res = client.get("/comptes")
        assert res.status_code == 200
        assert res.json() == []

    def test_liste_avec_comptes(self, client, deux_comptes):
        """Plusieurs comptes → liste complète."""
        res = client.get("/comptes")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 2  # au moins les 2 comptes du fixture


# ============================================================
# supprimer_compte
# ============================================================

class TestSupprimerCompte:
    """DELETE /comptes/{numero_compte}"""

    def test_compte_introuvable(self, client):
        """Compte inexistant → 404."""
        res = client.delete("/comptes/BK-NEXISTEPAS")
        assert res.status_code == 404

    def test_succes(self, client, compte_creer):
        """Suppression valide → 200, compte disparaît."""
        res = client.delete(f"/comptes/{compte_creer['numero_compte']}")
        assert res.status_code == 200
        data = res.json()
        assert data["succes"] is True
        assert data["compte_supprime"] == compte_creer["numero_compte"]

        # Vérifier que le compte n'existe plus
        res2 = client.get(f"/comptes/{compte_creer['numero_compte']}")
        assert res2.status_code == 404


# ============================================================
# historique_transactions
# ============================================================

class TestHistoriqueTransactions:
    """GET /comptes/{numero}/transactions"""

    def test_compte_introuvable(self, client):
        """Compte inexistant → 404."""
        res = client.get("/comptes/BK-NEXISTEPAS/transactions")
        assert res.status_code == 404

    def test_pas_de_transactions(self, client, compte_creer):
        """Compte sans transactions → liste vide."""
        res = client.get(f"/comptes/{compte_creer['numero_compte']}/transactions")
        assert res.status_code == 200
        assert res.json() == []

    def test_avec_transactions(self, client, compte_creer):
        """Compte avec transactions → liste des transactions."""
        client.post(
            f"/comptes/{compte_creer['numero_compte']}/depot",
            json={"montant": 100}
        )
        client.post(
            f"/comptes/{compte_creer['numero_compte']}/depot",
            json={"montant": 200}
        )
        res = client.get(f"/comptes/{compte_creer['numero_compte']}/transactions")
        assert res.status_code == 200
        assert len(res.json()) == 2
