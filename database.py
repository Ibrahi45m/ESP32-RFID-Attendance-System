"""Schéma SQLite du projet RFID Attendance. Migrations non destructives."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "attendance.db"


def connect(db_path=None):
    """Connexion SQLite avec contrôle des clés étrangères."""
    conn = sqlite3.connect(str(db_path or DB_PATH), timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database(db_path=None):
    """Crée les tables manquantes sans effacer les données existantes."""
    conn = connect(db_path)
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    uid TEXT NOT NULL UNIQUE,
                    date_inscription TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS seances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module TEXT NOT NULL,
                    date TEXT NOT NULL,
                    heure_debut TEXT NOT NULL,
                    heure_fin TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS attendance_seances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    seance_id INTEGER NOT NULL,
                    heure_pointage TEXT NOT NULL,
                    UNIQUE(student_id, seance_id),
                    FOREIGN KEY(student_id) REFERENCES students(id),
                    FOREIGN KEY(seance_id) REFERENCES seances(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT NOT NULL,
                    student TEXT NOT NULL,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    UNIQUE(uid, date)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS couleurs_modules (
                    module TEXT PRIMARY KEY,
                    couleur TEXT NOT NULL UNIQUE
                )
            """)
            # Gestion des groupes (compatible avec migration_groupes.py)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS groupes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom TEXT NOT NULL UNIQUE COLLATE NOCASE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS student_groupes (
                    student_id INTEGER NOT NULL,
                    groupe_id INTEGER NOT NULL,
                    date_debut TEXT NOT NULL,
                    date_fin TEXT,
                    PRIMARY KEY (student_id, groupe_id, date_debut),
                    CHECK (date_fin IS NULL OR date_fin >= date_debut),
                    FOREIGN KEY (student_id) REFERENCES students(id),
                    FOREIGN KEY (groupe_id) REFERENCES groupes(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS seance_groupes (
                    seance_id INTEGER NOT NULL,
                    groupe_id INTEGER NOT NULL,
                    PRIMARY KEY (seance_id, groupe_id),
                    FOREIGN KEY (seance_id) REFERENCES seances(id),
                    FOREIGN KEY (groupe_id) REFERENCES groupes(id)
                )
            """)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(students)")}
            if "date_inscription" not in columns:
                conn.execute("ALTER TABLE students ADD COLUMN date_inscription TEXT")
    finally:
        conn.close()


if __name__ == "__main__":
    init_database()
    print("Database ready!")
