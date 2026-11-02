"""Tests sans matÃ©riel et sans modifier attendance.db."""
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from database import connect, init_database
from couleurs_service import synchroniser_couleurs, nettoyer_couleur_orpheline
from pointage_service import enregistrer_pointage


class AttendanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "test.db"
        init_database(self.db)
        self.conn = connect(self.db)
        with self.conn:
            self.conn.execute("""
                INSERT INTO students (name, uid, date_inscription)
                VALUES ('Sara', 'A1 B2 C3 D4', '2026-10-28')
            """)
            self.conn.execute("""
                INSERT INTO seances (module, date, heure_debut, heure_fin)
                VALUES ('Python', '2026-11-02', '08:30', '10:30')
            """)
            self.conn.execute("INSERT INTO groupes(nom) VALUES ('G1')")
            self.conn.execute("""
                INSERT INTO student_groupes(student_id, groupe_id, date_debut)
                VALUES (1, 1, '2026-11-01')
            """)
            self.conn.execute("""
                INSERT INTO seance_groupes(seance_id, groupe_id)
                VALUES (1, 1)
            """)

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def pointage(self, uid, hour):
        return enregistrer_pointage(uid, datetime(2026, 11, 2, *hour), self.db)

    def test_before_and_after_schedule(self):
        self.assertEqual(self.pointage('A1 B2 C3 D4', (8, 29)).statut, 'aucune_seance')
        self.assertEqual(self.pointage('A1 B2 C3 D4', (10, 30)).statut, 'aucune_seance')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM attendance_seances').fetchone()[0], 0)

    def test_valid_and_duplicate(self):
        self.assertEqual(self.pointage(' a1   b2 c3 d4 ', (8, 30)).statut, 'ok')
        self.assertEqual(self.pointage('A1 B2 C3 D4', (9, 20)).statut, 'deja')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM attendance_seances').fetchone()[0], 1)

    def test_unknown_card(self):
        self.assertEqual(self.pointage('01 02 03 04', (9, 0)).statut, 'inconnue')

    def test_overlap_is_rejected(self):
        with self.conn:
            self.conn.execute("""
                INSERT INTO seances (module, date, heure_debut, heure_fin)
                VALUES ('Java', '2026-11-02', '09:00', '11:00')
            """)
        self.assertEqual(self.pointage('A1 B2 C3 D4', (9, 30)).statut, 'conflit')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM attendance_seances').fetchone()[0], 0)

    def test_future_registration(self):
        with self.conn:
            self.conn.execute("UPDATE students SET date_inscription='2026-11-03'")
        self.assertEqual(self.pointage('A1 B2 C3 D4', (9, 0)).statut, 'inscription')

    def test_refus_sans_groupe(self):
        with self.conn:
            self.conn.execute("DELETE FROM seance_groupes WHERE seance_id=1")
        result = self.pointage('A1 B2 C3 D4', (9, 0))
        self.assertEqual(result.statut, 'sans_groupe')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM attendance_seances').fetchone()[0], 0)

    def test_refus_hors_groupe(self):
        with self.conn:
            self.conn.execute("DELETE FROM student_groupes WHERE student_id=1")
        result = self.pointage('A1 B2 C3 D4', (9, 0))
        self.assertEqual(result.statut, 'hors_groupe')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM attendance_seances').fetchone()[0], 0)

    def test_affectation_future_refusee(self):
        with self.conn:
            self.conn.execute("UPDATE student_groupes SET date_debut='2026-11-03'")
        self.assertEqual(self.pointage('A1 B2 C3 D4', (9, 0)).statut, 'hors_groupe')

    def test_affectation_terminee_refusee(self):
        with self.conn:
            self.conn.execute("UPDATE student_groupes SET date_fin='2026-11-01'")
        self.assertEqual(self.pointage('A1 B2 C3 D4', (9, 0)).statut, 'hors_groupe')

    def test_multiple_groupes_un_seul_autorise_suffit(self):
        with self.conn:
            self.conn.execute("INSERT INTO groupes(nom) VALUES('G2')")
            self.conn.execute("INSERT INTO seance_groupes(seance_id,groupe_id) VALUES(1,2)")
        self.assertEqual(self.pointage('A1 B2 C3 D4', (9, 0)).statut, 'ok')

    def test_foreign_keys(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with self.conn:
                self.conn.execute("""
                    INSERT INTO attendance_seances (student_id, seance_id, heure_pointage)
                    VALUES (999, 1, '09:00:00')
                """)

    def test_colors_remain_stable(self):
        orig = synchroniser_couleurs(self.conn)
        self.assertIn('Python', orig)
        with self.conn:
            self.conn.execute("""
                INSERT INTO seances (module, date, heure_debut, heure_fin)
                VALUES ('Java', '2026-11-03', '11:00', '12:00')
            """)
        updated = synchroniser_couleurs(self.conn)
        self.assertEqual(orig['Python'], updated['Python'])
        self.assertNotEqual(updated['Python'], updated['Java'])
        with self.conn:
            self.conn.execute("DELETE FROM seances WHERE module='Java'")
            self.assertEqual(nettoyer_couleur_orpheline(self.conn, 'Java'), 1)
        self.assertNotIn('Java', dict(self.conn.execute('SELECT module, couleur FROM couleurs_modules')))

    def test_color_remains_if_another_session(self):
        synchroniser_couleurs(self.conn)
        with self.conn:
            self.conn.execute("""
                INSERT INTO seances (module, date, heure_debut, heure_fin)
                VALUES ('Python', '2026-11-03', '08:30', '10:30')
            """)
            self.conn.execute("DELETE FROM seance_groupes WHERE seance_id=1")
            self.conn.execute("DELETE FROM seances WHERE id=1")
            self.assertEqual(nettoyer_couleur_orpheline(self.conn, 'Python'), 0)

    def test_init_is_idempotent(self):
        init_database(self.db)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM students').fetchone()[0], 1)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM seances').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()

class ExtraSchemaTests(unittest.TestCase):
    def test_delete_pointed_seance_is_blocked_by_foreign_key(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "db.sqlite"
            init_database(path)
            conn = connect(path)
            try:
                with conn:
                    conn.execute("INSERT INTO students(name,uid,date_inscription) VALUES('Ahmed','AA BB','2026-10-28')")
                    conn.execute("INSERT INTO seances(module,date,heure_debut,heure_fin) VALUES('Python','2026-11-02','08:30','10:30')")
                    conn.execute("INSERT INTO attendance_seances(student_id,seance_id,heure_pointage) VALUES(1,1,'09:00:00')")
                with self.assertRaises(sqlite3.IntegrityError):
                    with conn:
                        conn.execute("DELETE FROM seances WHERE id=1")
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM seances").fetchone()[0], 1)
            finally:
                conn.close()

    def test_unique_colors_for_20_modules(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "db.sqlite"
            init_database(path)
            conn = connect(path)
            try:
                with conn:
                    for i in range(20):
                        conn.execute("INSERT INTO seances(module,date,heure_debut,heure_fin) VALUES(?,?,?,?)", (f'Module {i}', '2026-11-02', '09:00', '10:00'))
                colors = synchroniser_couleurs(conn)
                self.assertEqual(len(colors), 20)
                self.assertEqual(len(set(colors.values())), 20)
            finally:
                conn.close()
