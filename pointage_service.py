"""Règles métier du pointage, séparées de l'interface et du port série."""
from dataclasses import dataclass
from datetime import datetime
import sqlite3
from database import connect


@dataclass(frozen=True)
class ResultatPointage:
    statut: str
    message: str
    uid: str
    etudiant: str = ""
    module: str = ""
    seance_id: int | None = None


def normaliser_uid(uid: str) -> str:
    return " ".join(uid.upper().strip().split())


def enregistrer_pointage(uid: str, maintenant=None, db_path=None) -> ResultatPointage:
    """N'accepte qu'une séance active, une carte connue et un seul pointage."""
    uid = normaliser_uid(uid)
    if not uid:
        return ResultatPointage("erreur", "UID vide.", uid)

    maintenant = maintenant or datetime.now()
    date_sql = maintenant.strftime("%Y-%m-%d")
    heure_sql = maintenant.strftime("%H:%M")

    conn = connect(db_path)
    try:
        # Verrou pour éviter deux insertions concurrentes au même instant.
        conn.execute("BEGIN IMMEDIATE")
        etudiant = conn.execute(
            "SELECT id, name, date_inscription FROM students WHERE uid = ?", (uid,)
        ).fetchone()
        if etudiant is None:
            conn.rollback()
            return ResultatPointage("inconnue", "Carte non inscrite.", uid)

        etudiant_id, nom, inscription = etudiant
        if inscription and inscription > date_sql:
            conn.rollback()
            return ResultatPointage("inscription", "Étudiant non inscrit à cette date.", uid, nom)

        # Intervalle semi-ouvert : début inclus, fin exclue.
        seances = conn.execute("""
            SELECT id, module FROM seances
            WHERE date = ? AND heure_debut <= ? AND heure_fin > ?
        """, (date_sql, heure_sql, heure_sql)).fetchall()
        if not seances:
            conn.rollback()
            return ResultatPointage("aucune_seance", "Aucune séance en cours.", uid, nom)
        if len(seances) != 1:
            conn.rollback()
            return ResultatPointage("conflit", "Plusieurs séances actives : pointage refusé.", uid, nom)

        seance_id, module = seances[0]

        # Par securite, une seance doit etre associee a un groupe.
        groupe_affecte = conn.execute("""
            SELECT 1 FROM seance_groupes
            WHERE seance_id = ? LIMIT 1
        """, (seance_id,)).fetchone()
        if groupe_affecte is None:
            conn.rollback()
            return ResultatPointage(
                "sans_groupe",
                "Pointage refuse : aucun groupe associe a cette seance.",
                uid, nom, module, seance_id
            )

        # Un etudiant doit appartenir a au moins un groupe de la seance
        # a la date de la seance (y compris les bornes).
        autorise = conn.execute("""
            SELECT 1
            FROM seance_groupes AS sg
            JOIN student_groupes AS eg ON eg.groupe_id = sg.groupe_id
            WHERE sg.seance_id = ?
              AND eg.student_id = ?
              AND eg.date_debut <= ?
              AND (eg.date_fin IS NULL OR eg.date_fin >= ?)
            LIMIT 1
        """, (seance_id, etudiant_id, date_sql, date_sql)).fetchone()
        if autorise is None:
            conn.rollback()
            return ResultatPointage(
                "hors_groupe",
                "Pointage refuse : etudiant non affecte au groupe de cette seance.",
                uid, nom, module, seance_id
            )

        try:
            conn.execute("""
                INSERT INTO attendance_seances (student_id, seance_id, heure_pointage)
                VALUES (?, ?, ?)
            """, (etudiant_id, seance_id, maintenant.strftime("%H:%M:%S")))
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            deja = conn.execute("""
                SELECT 1 FROM attendance_seances
                WHERE student_id = ? AND seance_id = ?
            """, (etudiant_id, seance_id)).fetchone()
            if deja:
                return ResultatPointage("deja", "Pointage déjà enregistré.", uid, nom, module, seance_id)
            raise exc

        conn.commit()
        return ResultatPointage("ok", "Présence enregistrée.", uid, nom, module, seance_id)
    finally:
        conn.close()
