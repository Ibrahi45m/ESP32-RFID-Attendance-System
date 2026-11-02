import sqlite3
import sys
import unittest
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rapports_service import etudiants_attendus, bilan_seance, bilan_global_etudiants


class RapportsGroupesTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.executescript('''
        PRAGMA foreign_keys = ON;
        CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT NOT NULL, date_inscription TEXT);
        CREATE TABLE seances (id INTEGER PRIMARY KEY, module TEXT, date TEXT, heure_debut TEXT, heure_fin TEXT);
        CREATE TABLE attendance_seances (id INTEGER PRIMARY KEY, student_id INTEGER, seance_id INTEGER, heure_pointage TEXT, UNIQUE(student_id,seance_id));
        CREATE TABLE groupes (id INTEGER PRIMARY KEY, nom TEXT);
        CREATE TABLE student_groupes (student_id INTEGER, groupe_id INTEGER, date_debut TEXT, date_fin TEXT);
        CREATE TABLE seance_groupes (seance_id INTEGER, groupe_id INTEGER, PRIMARY KEY(seance_id, groupe_id));
        INSERT INTO students VALUES (1,'Ahmed','2026-10-28'), (2,'Sara','2026-10-28'), (3,'Youness','2026-10-28'),(4,'Nouveau','2026-11-03');
        INSERT INTO groupes VALUES (1,'G1'),(2,'G2');
        INSERT INTO student_groupes VALUES (1,1,'2026-11-01',NULL), (2,1,'2026-11-01',NULL), (1,2,'2026-11-01',NULL), (3,2,'2026-11-01','2026-11-04');
        INSERT INTO seances VALUES (4,'Python','2026-11-02','08:30','10:30'), (1,'Java','2026-10-30','08:30','10:30'),(7,'Linux','2026-11-06','14:00','15:00'),(8,'Vide','2026-11-08','14:00','15:00');
        INSERT INTO seance_groupes VALUES (4,1),(4,2),(7,2),(8,1);
        INSERT INTO attendance_seances VALUES (1,1,4,'08:35:00'),(2,3,4,'08:40:00'),(3,1,1,'08:40:00');
        ''')
        self.now = datetime(2026,11,7,12)

    def tearDown(self): self.conn.close()

    def test_multiple_groups_student_deduplicated(self):
        ids = etudiants_attendus(self.conn,4)['Etudiant_ID'].tolist()
        self.assertEqual(ids, [1,2,3])

    def test_grouped_absence_and_rate(self):
        b = bilan_seance(self.conn,4,self.now)
        self.assertTrue(b['avec_groupe'])
        self.assertEqual(b['total_attendus'], 3)
        self.assertEqual(b['presences_eligibles'], 2)
        self.assertEqual(b['sans_pointage']['Etudiant'].tolist(), ['Sara'])
        self.assertEqual(b['taux'], 66.7)

    def test_legacy_eligible_all_and_annotated(self):
        b = bilan_seance(self.conn,1,self.now)
        self.assertFalse(b['avec_groupe'])
        self.assertEqual(b['total_attendus'],3)
        self.assertEqual(b['presences_eligibles'],1)

    def test_end_of_membership(self):
        b = bilan_seance(self.conn,7,self.now)
        self.assertEqual(b['attendus']['Etudiant'].tolist(), ['Ahmed'])

    def test_out_of_group_pointage_not_counted(self):
        self.conn.execute("INSERT INTO attendance_seances VALUES (4, 2,7,'14:10:00')")
        b = bilan_seance(self.conn,7,self.now)
        self.assertEqual(b['pointages_hors_groupe'],1)
        self.assertEqual(b['presences_eligibles'],0)
        self.assertEqual(b['taux'],0)

    def test_not_yet_finished(self):
        b = bilan_seance(self.conn,8,self.now)
        self.assertFalse(b['terminee'])
        self.assertNotIn('taux',b)

    def test_rate_undefined_zero_enrolled(self):
        self.conn.execute('DELETE FROM student_groupes WHERE groupe_id=1')
        b = bilan_seance(self.conn,8,datetime(2026,11,9,12))
        self.assertIsNone(b['taux'])

    def test_global_grouped_and_legacy_separate(self):
        d = bilan_global_etudiants(self.conn,self.now)
        p = d[(d.Etudiant=='Sara')&(d.Module=='Python')].iloc[0]
        self.assertEqual((p.Mode,int(p.Seances),int(p.Presences),int(p.Sans_pointage)),('Groupes',1,0,1))
        legacy = d[(d.Etudiant=='Sara')&(d.Module=='Java')].iloc[0]
        self.assertEqual(legacy.Mode,'Historique sans groupe')

    def test_student_registered_after_session_excluded(self):
        self.assertNotIn(4,etudiants_attendus(self.conn,4).Etudiant_ID.tolist())

    def test_enrollment_start_date_enforced(self):
        self.conn.execute("UPDATE student_groupes SET date_debut='2026-11-03' WHERE student_id=2")
        self.assertNotIn(2,etudiants_attendus(self.conn,4).Etudiant_ID.tolist())

    def test_does_not_modify_data(self):
        before=self.conn.total_changes
        bilan_global_etudiants(self.conn,self.now)
        bilan_seance(self.conn,4,self.now)
        self.assertEqual(before,self.conn.total_changes)


if __name__=='__main__':unittest.main()
