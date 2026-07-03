"""Tests d'intégration — Banking API.
Scénarios complets de bout en bout.
"""


class TestScenariosComplets:
    """Scénarios métier complets."""

    def test_cycle_de_vie_compte(self, client):
        """Scénario complet : création → dépôts → retraits → virement → suppression."""
        # 1. Créer deux comptes
        a = client.post("/comptes", json={
            "nom_titulaire": "Emma Bernard",
            "email": "emma@banque.fr"
        }).json()
        b = client.post("/comptes", json={
            "nom_titulaire": "Lucas Moreau",
            "email": "lucas@banque.fr"
        }).json()

        assert a["solde"] == 0.0
        assert b["solde"] == 0.0

        # 2. Dépôts initiaux
        client.post(f"/comptes/{a['numero_compte']}/depot", json={"montant": 2000})
        client.post(f"/comptes/{b['numero_compte']}/depot", json={"montant": 1000})

        a = client.get(f"/comptes/{a['numero_compte']}").json()
        b = client.get(f"/comptes/{b['numero_compte']}").json()
        assert a["solde"] == 2000.0
        assert b["solde"] == 1000.0

        # 3. Virement de A vers B
        client.post(
            f"/comptes/{a['numero_compte']}/virement",
            json={"numero_compte_destination": b["numero_compte"], "montant": 750}
        )

        a = client.get(f"/comptes/{a['numero_compte']}").json()
        b = client.get(f"/comptes/{b['numero_compte']}").json()
        assert a["solde"] == 1250.0
        assert b["solde"] == 1750.0

        # 4. Retrait sur B
        client.post(f"/comptes/{b['numero_compte']}/retrait", json={"montant": 250})
        b = client.get(f"/comptes/{b['numero_compte']}").json()
        assert b["solde"] == 1500.0

        # 5. Vérifier l'historique de A
        txns_a = client.get(f"/comptes/{a['numero_compte']}/transactions").json()
        assert len(txns_a) == 2  # depot + virement

        # 6. Supprimer le compte A
        res = client.delete(f"/comptes/{a['numero_compte']}")
        assert res.status_code == 200
        assert res.json()["succes"] is True

        # 7. A n'existe plus, B existe encore
        assert client.get(f"/comptes/{a['numero_compte']}").status_code == 404
        assert client.get(f"/comptes/{b['numero_compte']}").status_code == 200

        # 8. La liste ne contient plus que B
        comptes = client.get("/comptes").json()
        assert len(comptes) == 1
        assert comptes[0]["numero_compte"] == b["numero_compte"]

    def test_scenario_erreurs_en_chaîne(self, client, compte_creer):
        """Scénario d'erreurs : tentatives invalides puis opération valide."""
        nc = compte_creer["numero_compte"]

        # Tentative de retrait à découvert
        r1 = client.post(f"/comptes/{nc}/retrait", json={"montant": 1000})
        assert r1.status_code == 400

        # Tentative de dépôt négatif
        r2 = client.post(f"/comptes/{nc}/depot", json={"montant": -50})
        assert r2.status_code == 400

        # Tentative de virement vers soi-même
        r3 = client.post(
            f"/comptes/{nc}/virement",
            json={"numero_compte_destination": nc, "montant": 10}
        )
        assert r3.status_code == 400

        # Le solde n'a pas bougé
        c = client.get(f"/comptes/{nc}").json()
        assert c["solde"] == 0.0

        # Opération valide
        client.post(f"/comptes/{nc}/depot", json={"montant": 500})
        c = client.get(f"/comptes/{nc}").json()
        assert c["solde"] == 500.0

    def test_operations_multiples_sur_un_compte(self, client, compte_creer):
        """Série d'opérations valides successives."""
        nc = compte_creer["numero_compte"]

        operations = [
            ("depot", 100),
            ("depot", 250),
            ("retrait", 50),
            ("depot", 300),
            ("retrait", 100),
        ]

        expected = 0.0
        for op_type, montant in operations:
            if op_type == "depot":
                client.post(f"/comptes/{nc}/depot", json={"montant": montant})
                expected += montant
            else:
                client.post(f"/comptes/{nc}/retrait", json={"montant": montant})
                expected -= montant

            c = client.get(f"/comptes/{nc}").json()
            assert c["solde"] == expected

        # Vérifier 5 transactions
        txns = client.get(f"/comptes/{nc}/transactions").json()
        assert len(txns) == 5

    def test_virement_croise(self, client):
        """Deux virements croisés entre deux comptes."""
        a = client.post("/comptes", json={
            "nom_titulaire": "A", "email": "a@test.com"
        }).json()
        b = client.post("/comptes", json={
            "nom_titulaire": "B", "email": "b@test.com"
        }).json()

        # Approvisionner
        client.post(f"/comptes/{a['numero_compte']}/depot", json={"montant": 1000})
        client.post(f"/comptes/{b['numero_compte']}/depot", json={"montant": 1000})

        # A → B 300
        client.post(
            f"/comptes/{a['numero_compte']}/virement",
            json={"numero_compte_destination": b["numero_compte"], "montant": 300}
        )
        # B → A 200
        client.post(
            f"/comptes/{b['numero_compte']}/virement",
            json={"numero_compte_destination": a["numero_compte"], "montant": 200}
        )

        a = client.get(f"/comptes/{a['numero_compte']}").json()
        b = client.get(f"/comptes/{b['numero_compte']}").json()
        assert a["solde"] == 900.0   # 1000 - 300 + 200
        assert b["solde"] == 1100.0  # 1000 + 300 - 200

    def test_concurrence_simple(self, client):
        """Création de 3 comptes et opérations sur chacun — pas de fuite d'état."""
        comptes = []
        for i in range(3):
            c = client.post("/comptes", json={
                "nom_titulaire": f"User {i}",
                "email": f"user{i}@test.com"
            }).json()
            comptes.append(c)

        # Dépôts sur chaque compte
        for i, c in enumerate(comptes):
            client.post(f"/comptes/{c['numero_compte']}/depot", json={"montant": (i + 1) * 100})

        # Vérifier les soldes indépendants
        for i, c in enumerate(comptes):
            updated = client.get(f"/comptes/{c['numero_compte']}").json()
            assert updated["solde"] == (i + 1) * 100.0
