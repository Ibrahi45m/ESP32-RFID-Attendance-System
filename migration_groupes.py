
from database import connect

conn = connect()

try:
    with conn:
        # Table des groupes
        conn.execute("""
            CREATE TABLE IF NOT EXISTS groupes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL UNIQUE COLLATE NOCASE
            )
        """)

        # Affectation des etudiants aux groupes
        conn.execute("""
            CREATE TABLE IF NOT EXISTS student_groupes (
                student_id INTEGER NOT NULL,
                groupe_id INTEGER NOT NULL,
                date_debut TEXT NOT NULL,
                date_fin TEXT,

                PRIMARY KEY (
                    student_id,
                    groupe_id,
                    date_debut
                ),

                CHECK (
                    date_fin IS NULL
                    OR date_fin >= date_debut
                ),

                FOREIGN KEY (student_id)
                    REFERENCES students(id),

                FOREIGN KEY (groupe_id)
                    REFERENCES groupes(id)
            )
        """)

        # Affectation des seances aux groupes
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seance_groupes (
                seance_id INTEGER NOT NULL,
                groupe_id INTEGER NOT NULL,

                PRIMARY KEY (seance_id, groupe_id),

                FOREIGN KEY (seance_id)
                    REFERENCES seances(id),

                FOREIGN KEY (groupe_id)
                    REFERENCES groupes(id)
            )
        """)

    print("Migration groupes : OK")

    for table in (
        "groupes",
        "student_groupes",
        "seance_groupes"
    ):
        nombre = conn.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

        print(f"{table} : {nombre} ligne(s)")

finally:
    conn.close()
