"""Calculs de presence par groupes avec fallback historique explicite.

Les séances sans groupe conservent une estimation héritée (tous les
étudiants inscrits à la date de la séance), jamais présentée comme une
absence officielle. Les séances groupées comptent uniquement les membres
affectés à cette date, sans doublons si une séance a plusieurs groupes.
"""
from datetime import datetime
import pandas as pd


def _groupes_seance(conn, seance_id):
    return conn.execute(
        'SELECT 1 FROM seance_groupes WHERE seance_id = ? LIMIT 1',
        (seance_id,),
    ).fetchone() is not None


def etudiants_attendus(conn, seance_id):
    """DataFrame (Etudiant_ID, Etudiant), sans doublons et par date."""
    seance = conn.execute('SELECT date FROM seances WHERE id = ?', (seance_id,)).fetchone()
    if seance is None:
        raise ValueError('Séance introuvable.')
    date_seance = seance[0]
    if _groupes_seance(conn, seance_id):
        return pd.read_sql_query('''
            SELECT DISTINCT e.id AS Etudiant_ID, e.name AS Etudiant
            FROM students AS e
            JOIN student_groupes AS eg ON eg.student_id = e.id
            JOIN seance_groupes AS sg ON sg.groupe_id = eg.groupe_id
            WHERE sg.seance_id = ?
              AND (e.date_inscription IS NULL OR e.date_inscription <= ?)
              AND eg.date_debut <= ?
              AND (eg.date_fin IS NULL OR eg.date_fin >= ?)
            ORDER BY e.name COLLATE NOCASE, e.id
        ''', conn, params=(seance_id, date_seance, date_seance, date_seance))
    return pd.read_sql_query('''
        SELECT id AS Etudiant_ID, name AS Etudiant
        FROM students
        WHERE date_inscription IS NULL OR date_inscription <= ?
        ORDER BY name COLLATE NOCASE, id
    ''', conn, params=(date_seance,))


def bilan_seance(conn, seance_id, maintenant=None):
    """Donne les métriques d'une séance terminée, sinon terminé=False."""
    ligne = conn.execute('''
        SELECT date, heure_fin FROM seances WHERE id = ?
    ''', (seance_id,)).fetchone()
    if ligne is None:
        raise ValueError('Séance introuvable.')
    now = maintenant or datetime.now()
    date_sql = now.strftime('%Y-%m-%d')
    heure_sql = now.strftime('%H:%M')
    termine = ligne[0] < date_sql or (ligne[0] == date_sql and ligne[1] <= heure_sql)
    groupe = _groupes_seance(conn, seance_id)
    if not termine:
        return {"terminee": False, "avec_groupe": groupe}
    attendus = etudiants_attendus(conn, seance_id)
    pointages = pd.read_sql_query('''
        SELECT student_id AS Etudiant_ID
        FROM attendance_seances
        WHERE seance_id = ?
    ''', conn, params=(seance_id,))
    ids_presents = set(pointages['Etudiant_ID'].tolist())
    attendus_ids = set(attendus['Etudiant_ID'].tolist())
    absents = attendus[~attendus['Etudiant_ID'].isin(ids_presents)].copy()
    presents = len(attendus_ids & ids_presents)
    total = len(attendus_ids)
    return {
        "terminee": True,
        "avec_groupe": groupe,
        "attendus": attendus,
        "sans_pointage": absents,
        "presences_eligibles": presents,
        "total_attendus": total,
        "taux": round(100 * presents / total, 1) if total else None,
        "pointages_hors_groupe": len(ids_presents - attendus_ids) if groupe else 0,
    }


def bilan_global_etudiants(conn, maintenant=None):
    """Bilan par étudiant/module, distinguer 'Groupes' et 'Historique sans groupe'."""
    now = maintenant or datetime.now()
    date_sql, heure_sql = now.strftime('%Y-%m-%d'), now.strftime('%H:%M')
    return pd.read_sql_query('''
        WITH termine AS (
            SELECT s.id, s.module, s.date
            FROM seances AS s
            WHERE s.date < ? OR (s.date = ? AND s.heure_fin <= ?)
        ), attendus AS (
            SELECT
                st.id AS Etudiant_ID,
                st.name AS Etudiant,
                s.id AS Seance_ID,
                s.module AS Module,
                CASE WHEN EXISTS (
                    SELECT 1 FROM seance_groupes sg WHERE sg.seance_id = s.id
                ) THEN 'Groupes' ELSE 'Historique sans groupe' END AS Mode
            FROM students st
            CROSS JOIN termine s
            WHERE (st.date_inscription IS NULL OR st.date_inscription <= s.date)
            AND (
                NOT EXISTS (
                    SELECT 1 FROM seance_groupes sg WHERE sg.seance_id = s.id
                )
                OR EXISTS (
                    SELECT 1
                    FROM seance_groupes sg
                    JOIN student_groupes eg ON eg.groupe_id = sg.groupe_id
                    WHERE sg.seance_id = s.id
                      AND eg.student_id = st.id
                      AND eg.date_debut <= s.date
                      AND (eg.date_fin IS NULL OR eg.date_fin >= s.date)
                )
            )
        )
        SELECT a.Etudiant_ID, a.Etudiant, a.Module, a.Mode,
               COUNT(*) AS Seances,
               COUNT(p.id) AS Presences,
               COUNT(*) - COUNT(p.id) AS Sans_pointage
        FROM attendus a
        LEFT JOIN attendance_seances p
          ON p.student_id = a.Etudiant_ID AND p.seance_id = a.Seance_ID
        GROUP BY a.Etudiant_ID, a.Module, a.Mode
        ORDER BY a.Module COLLATE NOCASE, a.Etudiant COLLATE NOCASE, a.Etudiant_ID, a.Mode
    ''', conn, params=(date_sql, date_sql, heure_sql))
