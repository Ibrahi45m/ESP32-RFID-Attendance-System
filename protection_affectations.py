
from database import connect

conn = connect()

try:
    # Empêcher les chevauchements lors d'un INSERT
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS
        verifier_affectation_insert
        BEFORE INSERT ON student_groupes
        WHEN EXISTS (
            SELECT 1
            FROM student_groupes AS sg
            WHERE sg.student_id = NEW.student_id
              AND sg.groupe_id = NEW.groupe_id
              AND (
                  NEW.date_fin IS NULL
                  OR sg.date_debut <= NEW.date_fin
              )
              AND (
                  sg.date_fin IS NULL
                  OR sg.date_fin >= NEW.date_debut
              )
        )
        BEGIN
            SELECT RAISE(
                ABORT,
                'Chevauchement des affectations'
            );
        END
    """)

    # Empêcher les chevauchements lors d'un UPDATE
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS
        verifier_affectation_update
        BEFORE UPDATE ON student_groupes
        WHEN EXISTS (
            SELECT 1
            FROM student_groupes AS sg
            WHERE sg.student_id = NEW.student_id
              AND sg.groupe_id = NEW.groupe_id
              AND sg.rowid != OLD.rowid
              AND (
                  NEW.date_fin IS NULL
                  OR sg.date_debut <= NEW.date_fin
              )
              AND (
                  sg.date_fin IS NULL
                  OR sg.date_fin >= NEW.date_debut
              )
        )
        BEGIN
            SELECT RAISE(
                ABORT,
                'Chevauchement des affectations'
            );
        END
    """)

    conn.commit()
    print("Protection des affectations : OK")

finally:
    conn.close()
