"""Contrôles ciblés anti-répétition et messages de fenêtre, sans matériel."""
import sqlite3
import unittest
from datetime import datetime
from rfid_auto_worker import FiltreAntiRepetition, etat_seance


class FiltreAntiRepetitionTests(unittest.TestCase):
    def setUp(self):
        self.f = FiltreAntiRepetition(delai=2.0)

    def test_premiere_carte_acceptee(self):
        self.assertFalse(self.f.ignorer("AAAA", 10.0, 1))

    def test_uid_identique_dans_deux_secondes_ignore(self):
        self.assertFalse(self.f.ignorer("AAAA", 10.0, 1))
        self.assertTrue(self.f.ignorer("AAAA", 11.99, 1))

    def test_uid_redevient_lisible_apres_deux_secondes(self):
        self.assertFalse(self.f.ignorer("AAAA", 10.0, 1))
        self.assertFalse(self.f.ignorer("AAAA", 12.0, 1))

    def test_autre_uid_nest_pas_bloque(self):
        self.f.ignorer("AAAA", 10.0, 1)
        self.assertFalse(self.f.ignorer("BBBB", 10.2, 1))

    def test_intercaler_autre_carte_ne_reinitialise_pas_delai(self):
        self.f.ignorer("AAAA", 10.0, 1)
        self.f.ignorer("BBBB", 10.2, 1)
        self.assertTrue(self.f.ignorer("AAAA", 11.0, 1))

    def test_changement_de_seance_permet_scan(self):
        self.f.ignorer("AAAA", 10.0, 1)
        self.assertFalse(self.f.ignorer("AAAA", 10.1, 2))

    def test_repetition_ignores_ne_rallonge_pas_le_delai(self):
        self.f.ignorer("AAAA", 10.0, 1)
        self.assertTrue(self.f.ignorer("AAAA", 11.0, 1))
        self.assertFalse(self.f.ignorer("AAAA", 12.0, 1))

    def test_delai_invalide(self):
        with self.assertRaises(ValueError):
            FiltreAntiRepetition(delai=0)

    def test_nettoyage_des_anciennes_cartes(self):
        for i in range(101):
            self.f.ignorer(f"UID{i}", float(i * 3), 1)
        self.assertLess(len(self.f._derniers), 100)


class MessageAvantSeanceTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE seances(id INTEGER, module TEXT, date TEXT, heure_debut TEXT, heure_fin TEXT)")
        self.db.execute("CREATE TABLE seance_groupes(seance_id INTEGER, groupe_id INTEGER)")
        self.db.execute("INSERT INTO seances VALUES (12, 'TEST LED VERTE G1', '2026-11-01', '17:30', '18:30')")

    def tearDown(self):
        self.db.close()

    def test_avant_la_seance_message_non_ouverte(self):
        resultat = etat_seance(self.db, datetime.fromisoformat('2026-11-01T17:29:00'), 'half', None)
        self.assertEqual(resultat['code'], 'attente')
        self.assertIn('non ouverte', resultat['message'])
        self.assertIn('17:30', resultat['message'])

    def test_ancienne_seance_terminee_mais_prochaine_non_ouverte(self):
        self.db.execute("INSERT INTO seances VALUES (11, 'ANCIENNE', '2026-11-01', '16:00', '17:30')")
        resultat = etat_seance(self.db, datetime.fromisoformat('2026-11-01T17:15:00'), 'half', None)
        self.assertEqual(resultat['code'], 'ferme')
        self.assertIn('terminee', resultat['message'])
        self.assertIn('non ouverte', resultat['message'])
        self.assertIn('17:30', resultat['message'])

    def test_apres_la_seance_aucune_seance(self):
        resultat = etat_seance(self.db, datetime.fromisoformat('2026-11-01T19:00:00'), 'half', None)
        self.assertEqual(resultat['code'], 'attente')
        self.assertEqual(resultat['message'], 'Aucune seance en cours.')


if __name__ == '__main__':
    unittest.main()
