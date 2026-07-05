"""Tests d'intégration v2 — scénarios complets avec auth."""
from decimal import Decimal


class TestScenariosComplets:

    def test_cycle_de_vie_complet(self, client, admin_user, admin_headers):
        """Création → dépôt → virement → gel → réactivation → clôture."""
        import uuid
        e1 = f"emma_{uuid.uuid4().hex[:4]}@banque.fr"
        e2 = f"lucas_{uuid.uuid4().hex[:4]}@banque.fr"

        a = client.post("/comptes", json={"nom_titulaire": "Emma",  "email": e1}, headers=admin_headers).json()
        b = client.post("/comptes", json={"nom_titulaire": "Lucas", "email": e2}, headers=admin_headers).json()

        client.post(f"/comptes/{a['numero_compte']}/depot", json={"montant": 2000}, headers=admin_headers)
        client.post(f"/comptes/{b['numero_compte']}/depot", json={"montant": 1000}, headers=admin_headers)

        # Virement A → B
        client.post(f"/comptes/{a['numero_compte']}/virement",
                    json={"numero_compte_destination": b["numero_compte"], "montant": 750},
                    headers=admin_headers)

        a = client.get(f"/comptes/{a['numero_compte']}", headers=admin_headers).json()
        b = client.get(f"/comptes/{b['numero_compte']}", headers=admin_headers).json()
        assert Decimal(str(a["solde"])) == Decimal("1250")
        assert Decimal(str(b["solde"])) == Decimal("1750")

        # Gel du compte B
        client.post(f"/comptes/{b['numero_compte']}/freeze", headers=admin_headers)
        res = client.post(f"/comptes/{b['numero_compte']}/retrait", json={"montant": 100}, headers=admin_headers)
        assert res.status_code == 409

        # Réactivation
        client.post(f"/comptes/{b['numero_compte']}/reactivate", headers=admin_headers)
        client.post(f"/comptes/{b['numero_compte']}/retrait", json={"montant": 1750}, headers=admin_headers)

        # Clôture (solde nul)
        res = client.post(f"/comptes/{b['numero_compte']}/close", headers=admin_headers)
        assert res.status_code == 200

        # Historique A : depot + virement = 2 transactions
        txns = client.get(f"/comptes/{a['numero_compte']}/transactions", headers=admin_headers).json()
        assert len(txns) == 2

        # Suppression A
        res = client.delete(f"/comptes/{a['numero_compte']}", headers=admin_headers)
        assert res.status_code == 200
        assert client.get(f"/comptes/{a['numero_compte']}", headers=admin_headers).status_code == 404

    def test_isolation_client(self, client, client_user, client_headers, admin_headers):
        """Un client ne voit que ses propres comptes et ne peut pas accéder à ceux d'autrui."""
        import uuid
        # Créer un compte pour autrui
        stranger = client.post("/comptes", json={
            "nom_titulaire": "Stranger",
            "email": f"stranger_{uuid.uuid4().hex[:4]}@test.com"
        }, headers=admin_headers).json()

        # Le client crée son propre compte
        mon_compte = client.post("/comptes", json={
            "nom_titulaire": "Moi",
            "email": client_user["email"]
        }, headers=client_headers).json()

        # Le client ne voit pas le compte étranger dans la liste
        mes_comptes = client.get("/comptes", headers=client_headers).json()
        numeros = [c["numero_compte"] for c in mes_comptes]
        assert stranger["numero_compte"] not in numeros
        assert mon_compte["numero_compte"] in numeros

        # Accès direct refusé
        res = client.get(f"/comptes/{stranger['numero_compte']}", headers=client_headers)
        assert res.status_code == 403

    def test_decouvert_compte_courant(self, client, admin_headers):
        """Un compte courant peut aller en négatif dans la limite du découvert."""
        import uuid
        email = f"dec_{uuid.uuid4().hex[:4]}@test.com"
        c = client.post("/comptes", json={
            "nom_titulaire": "Découvert",
            "email": email,
            "type": "CURRENT",
            "overdraft_limit": "500"
        }, headers=admin_headers).json()
        nc = c["numero_compte"]

        client.post(f"/comptes/{nc}/depot", json={"montant": 100}, headers=admin_headers)

        # Retrait 400 → solde = -300 (dans la limite de -500)
        res = client.post(f"/comptes/{nc}/retrait", json={"montant": 400}, headers=admin_headers)
        assert res.status_code == 200
        solde = Decimal(str(client.get(f"/comptes/{nc}", headers=admin_headers).json()["solde"]))
        assert solde == Decimal("-300")

        # Retrait 250 → solde serait -550 > découvert → refus
        res = client.post(f"/comptes/{nc}/retrait", json={"montant": 250}, headers=admin_headers)
        assert res.status_code == 422

    def test_operations_multiples(self, client, compte_creer, client_headers):
        """Série d'opérations successives avec vérification du solde."""
        nc = compte_creer["numero_compte"]
        ops = [("depot", 100), ("depot", 250), ("retrait", 50), ("depot", 300), ("retrait", 100)]
        expected = Decimal("0")

        for op, montant in ops:
            client.post(f"/comptes/{nc}/{op}", json={"montant": montant}, headers=client_headers)
            expected += Decimal(str(montant)) if op == "depot" else -Decimal(str(montant))
            solde = Decimal(str(client.get(f"/comptes/{nc}", headers=client_headers).json()["solde"]))
            assert solde == expected

        txns = client.get(f"/comptes/{nc}/transactions", headers=client_headers).json()
        assert len(txns) == 5
