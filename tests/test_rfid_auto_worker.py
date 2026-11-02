"""Tests de la fenetre horaire : sans lecteur et sans modifier attendance.db."""
import sqlite3
import unittest
from datetime import datetime
from rfid_auto_worker import configurer_fenetre, calculer_fin_pointage, etat_seance


class FenetreRFIDTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE seances(id INTEGER, module TEXT, date TEXT, heure_debut TEXT, heure_fin TEXT)")
        self.db.execute("CREATE TABLE seance_groupes(seance_id INTEGER, groupe_id INTEGER)")
        self.db.execute("INSERT INTO seances VALUES (4, 'Python', '2026-11-02', '08:30', '10:30')")
        self.db.execute("INSERT INTO seance_groupes VALUES (4, 1)")

    def tearDown(self):
        self.db.close()

    def etat(self, heure, mode="half", minutes=None):
        return etat_seance(self.db, datetime.fromisoformat("2026-11-02T" + heure), mode, minutes)

    def test_half_before_start(self):
        self.assertEqual(self.etat("08:29")["code"], "attente")

    def test_half_at_start(self):
        self.assertEqual(self.etat("08:30")["code"], "actif")

    def test_half_cutoff(self):
        self.assertEqual(self.etat("09:29:59")["code"], "actif")
        self.assertEqual(self.etat("09:30:00")["code"], "ferme")

    def test_full_until_end(self):
        self.assertEqual(self.etat("10:29:59", "full")["code"], "actif")
        self.assertEqual(self.etat("10:30:00", "full")["code"], "attente")

    def test_custom_minutes(self):
        self.assertEqual(self.etat("08:44:59", "minutes", 15)["code"], "actif")
        self.assertEqual(self.etat("08:45:00", "minutes", 15)["code"], "ferme")

    def test_group_required(self):
        self.db.execute("DELETE FROM seance_groupes")
        self.assertEqual(self.etat("09:00")["code"], "sans_groupe")

    def test_overlapping_seances(self):
        self.db.execute("INSERT INTO seances VALUES (8, 'Java', '2026-11-02', '09:00', '11:00')")
        self.assertEqual(self.etat("09:15")["code"], "conflit")

    def test_bad_config(self):
        for value in ("", "0", "oops", "-1"):
            with self.assertRaises(ValueError):
                configurer_fenetre(value)

    def test_custom_cap_at_session_end(self):
        debut = datetime.fromisoformat("2026-11-02T08:30")
        fin = datetime.fromisoformat("2026-11-02T10:30")
        self.assertEqual(calculer_fin_pointage(debut, fin, "minutes", 300), fin)


if __name__ == "__main__":
    unittest.main()
