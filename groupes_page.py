from datetime import date
import streamlit as st
import pandas as pd
from database import connect
import sqlite3
from datetime import date, timedelta


st.title("Gestion des groupes")

# Ajouter un groupe
st.subheader("Ajouter un groupe")

with st.form("form_ajouter_groupe"):
    nom_groupe = st.text_input(
        "Nom du groupe",
        placeholder="Exemple : G1"
    )

    ajouter = st.form_submit_button("Ajouter le groupe")

if ajouter:
    nom_groupe = nom_groupe.strip()

    if not nom_groupe:
        st.error("Veuillez saisir un nom de groupe.")
    else:
        conn = connect()

        try:
            with conn:
                conn.execute(
                    "INSERT INTO groupes (nom) VALUES (?)",
                    (nom_groupe,)
                )
            st.success("Groupe ajoute avec succes !")

        except Exception as erreur:
            import sqlite3
            if isinstance(erreur, sqlite3.IntegrityError):
                st.warning("Ce groupe existe deja.")
            else:
                st.error("Impossible d'ajouter le groupe.")
                raise

        finally:
            conn.close()

# Afficher les groupes
st.divider()
st.subheader("Liste des groupes")

conn = connect()

df_groupes = pd.read_sql_query("""
    SELECT
        id AS ID,
        nom AS Groupe
    FROM groupes
    ORDER BY nom COLLATE NOCASE
""", conn)

conn.close()

st.dataframe(
    df_groupes,
    width="stretch",
    hide_index=True
)

# =====================================
# AFFECTATION DES ETUDIANTS AUX GROUPES
# =====================================

st.divider()
st.subheader("Affecter un etudiant a un groupe")

conn = connect()

etudiants = conn.execute("""
    SELECT id, name
    FROM students
    ORDER BY name
""").fetchall()

groupes = conn.execute("""
    SELECT id, nom
    FROM groupes
    ORDER BY nom COLLATE NOCASE
""").fetchall()

conn.close()

if etudiants and groupes:

    options_etudiants = {
        f"{nom} | ID {id_etudiant}": id_etudiant
        for id_etudiant, nom in etudiants
    }

    options_groupes = {
        nom: id_groupe
        for id_groupe, nom in groupes
    }

    with st.form("form_affectation_groupe"):

        choix_etudiant = st.selectbox(
            "Choisir un etudiant",
            list(options_etudiants.keys())
        )

        choix_groupe = st.selectbox(
            "Choisir un groupe",
            list(options_groupes.keys())
        )

        date_affectation = st.date_input(
            "Date de debut",
            value=date.today()
        )

        affecter = st.form_submit_button(
            "Affecter au groupe"
        )

    if affecter:

        id_etudiant = options_etudiants[choix_etudiant]
        id_groupe = options_groupes[choix_groupe]
        date_debut = date_affectation.isoformat()

        conn = connect()

        try:
            # Eviter une double affectation active
            existe = conn.execute("""
                SELECT 1
                FROM student_groupes
                WHERE student_id = ?
                  AND groupe_id = ?
                  AND (
                      date_fin IS NULL
                      OR date_fin >= ?
                  )
                LIMIT 1
            """, (
                id_etudiant,
                id_groupe,
                date_debut
            )).fetchone()

            if existe:
                st.warning(
                    "Cet etudiant possede deja "
                    "une affectation couvrant cette date."
                )

            else:
                with conn:
                    conn.execute("""
                        INSERT INTO student_groupes
                        (student_id, groupe_id, date_debut)
                        VALUES (?, ?, ?)
                    """, (
                        id_etudiant,
                        id_groupe,
                        date_debut
                    ))

                st.success(
                    "Etudiant affecte au groupe avec succes !"
                )

        except sqlite3.IntegrityError as erreur:
            if "Chevauchement des affectations" in str(erreur):
                st.warning(
                    "Cette affectation chevauche une periode "
                    "deja enregistree pour cet etudiant "
                    "et ce groupe."
                )
            else:
                st.error(
                    "Impossible d'enregistrer cette affectation. "
                    "Verifiez les informations saisies."
                )

        finally:
            conn.close()

else:
    st.info(
        "Ajoutez au moins un etudiant et un groupe."
    )


# =====================================
# LISTE DES AFFECTATIONS
# =====================================

st.subheader("Etudiants par groupe")

conn = connect()

df_affectations = pd.read_sql_query("""
    SELECT
        students.name AS Etudiant,
        groupes.nom AS Groupe,
        student_groupes.date_debut AS Date_debut,
        student_groupes.date_fin AS Date_fin
    FROM student_groupes
    JOIN students
        ON students.id = student_groupes.student_id
    JOIN groupes
        ON groupes.id = student_groupes.groupe_id
    ORDER BY groupes.nom, students.name
""", conn)

conn.close()

st.dataframe(
    df_affectations,
    width="stretch",
    hide_index=True
)

# =====================================
# ASSOCIER LES SEANCES AUX GROUPES
# =====================================

from datetime import datetime

st.divider()
st.subheader("Associer une seance aux groupes")

conn = connect()

maintenant = datetime.now()
date_actuelle = maintenant.strftime("%Y-%m-%d")
heure_actuelle = maintenant.strftime("%H:%M")

# Seances futures sans pointages

# Seances futures ou en cours, sans pointages
seances_disponibles = conn.execute("""
    SELECT id, module, date, heure_debut, heure_fin
    FROM seances AS s
    WHERE (
        s.date > ?
        OR (s.date = ? AND s.heure_fin > ?)
    )
    AND NOT EXISTS (
        SELECT 1
        FROM attendance_seances AS a
        WHERE a.seance_id = s.id
    )
    ORDER BY s.date, s.heure_debut
""", (
    date_actuelle,
    date_actuelle,
    heure_actuelle
)).fetchall()


groupes_disponibles = conn.execute("""
    SELECT id, nom
    FROM groupes
    ORDER BY nom COLLATE NOCASE
""").fetchall()

conn.close()

if seances_disponibles and groupes_disponibles:

    options_seances = {
        f"{module} | {jour} | {debut}-{fin} | ID {id_s}": id_s
        for id_s, module, jour, debut, fin in seances_disponibles
    }

    options_groupes = {
        nom: id_g
        for id_g, nom in groupes_disponibles
    }

    with st.form("form_associer_seance_groupe"):

        choix_seance = st.selectbox(
            "Choisir une seance",
            list(options_seances.keys())
        )

        choix_groupes = st.multiselect(
            "Choisir les groupes concernes",
            list(options_groupes.keys())
        )

        associer = st.form_submit_button(
            "Associer les groupes"
        )

    if associer:

        if not choix_groupes:
            st.warning("Choisissez au moins un groupe.")

        else:
            id_seance = options_seances[choix_seance]

            conn = connect()

            try:
                with conn:
                    for nom_groupe in choix_groupes:
                        conn.execute("""
                            INSERT OR IGNORE
                            INTO seance_groupes
                            (seance_id, groupe_id)
                            VALUES (?, ?)
                        """, (
                            id_seance,
                            options_groupes[nom_groupe]
                        ))

                st.success("Association enregistree !")

            finally:
                conn.close()

else:
    st.info(
        "Aucune seance future disponible "
        "ou aucun groupe cree."
    )

# =====================================
# AFFICHER LES ASSOCIATIONS
# =====================================

st.subheader("Seances et groupes associes")

conn = connect()

df_seance_groupes = pd.read_sql_query("""
    SELECT
        seances.id AS Seance_ID,
        seances.module AS Module,
        seances.date AS Date,
        groupes.nom AS Groupe
    FROM seance_groupes
    JOIN seances
        ON seances.id = seance_groupes.seance_id
    JOIN groupes
        ON groupes.id = seance_groupes.groupe_id
    ORDER BY seances.date, seances.id, groupes.nom
""", conn)

conn.close()

st.dataframe(
    df_seance_groupes,
    width="stretch",
    hide_index=True
)

# =====================================
# TERMINER UNE AFFECTATION
# =====================================

st.divider()
st.subheader("Terminer une affectation")

conn = connect()

affectations_actives = conn.execute("""
    SELECT
        sg.student_id,
        sg.groupe_id,
        sg.date_debut,
        s.name,
        g.nom
    FROM student_groupes sg
    JOIN students s ON s.id = sg.student_id
    JOIN groupes g ON g.id = sg.groupe_id
    WHERE sg.date_fin IS NULL
    ORDER BY s.name, g.nom
""").fetchall()

conn.close()

if affectations_actives:

    options_fin = {
        f"{nom} | {groupe} | Depuis {debut}": (
            student_id, groupe_id, debut
        )
        for student_id, groupe_id, debut, nom, groupe
        in affectations_actives
    }

    with st.form("form_fin_affectation"):

        choix_fin = st.selectbox(
            "Choisir une affectation",
            list(options_fin.keys())
        )

        date_fin = st.date_input(
            "Dernier jour dans le groupe",
            value=date.today(),
            min_value=date.today()
        )

        confirmation_fin = st.checkbox(
            "Je confirme la fin de cette affectation"
        )

        terminer = st.form_submit_button(
            "Terminer l'affectation"
        )

    if terminer:

        student_id, groupe_id, debut = options_fin[choix_fin]

        if not confirmation_fin:
            st.warning("Veuillez confirmer l'operation.")

        elif date_fin.isoformat() < debut:
            st.error(
                "La date de fin doit etre "
                "apres la date de debut."
            )

        else:
            conn = connect()

            try:
                with conn:
                    curseur = conn.execute("""
                        UPDATE student_groupes
                        SET date_fin = ?
                        WHERE student_id = ?
                          AND groupe_id = ?
                          AND date_debut = ?
                          AND date_fin IS NULL
                    """, (
                        date_fin.isoformat(),
                        student_id,
                        groupe_id,
                        debut
                    ))

                if curseur.rowcount == 1:
                    st.success(
                        "Affectation terminee avec succes !"
                    )
                else:
                    st.warning(
                        "Affectation deja modifiee."
                    )

            except sqlite3.IntegrityError as erreur:
                if "Chevauchement des affectations" in str(erreur):
                    st.warning(
                        "Modification refusee : cette periode "
                        "chevauche une autre affectation."
                    )
                else:
                    st.error(
                        "Impossible de terminer cette affectation."
                    )

            finally:
                conn.close()

else:
    st.info("Aucune affectation ouverte.")


# =====================================
# TRANSFERT ENTRE GROUPES
# =====================================

st.divider()
st.subheader("Transferer un etudiant")

conn = connect()

affectations_ouvertes = conn.execute("""
    SELECT sg.student_id, sg.groupe_id,
           sg.date_debut, s.name, g.nom
    FROM student_groupes sg
    JOIN students s ON s.id = sg.student_id
    JOIN groupes g ON g.id = sg.groupe_id
    WHERE sg.date_fin IS NULL
    ORDER BY s.name, g.nom
""").fetchall()

groupes_dest = conn.execute("""
    SELECT id, nom FROM groupes
    ORDER BY nom COLLATE NOCASE
""").fetchall()

conn.close()

if affectations_ouvertes and len(groupes_dest) >= 2:

    options_origine = {
        f"{nom} | {groupe} | Depuis {debut}":
            (student_id, groupe_id, debut)
        for student_id, groupe_id, debut, nom, groupe
        in affectations_ouvertes
    }

    options_dest = {
        nom: groupe_id
        for groupe_id, nom in groupes_dest
    }

    with st.form("form_transfert"):

        origine = st.selectbox(
            "Etudiant et groupe actuel",
            list(options_origine.keys())
        )

        destination = st.selectbox(
            "Nouveau groupe",
            list(options_dest.keys())
        )

        date_transfert = st.date_input(
            "Date du transfert",
            value=None,
            min_value=date.today() + timedelta(days=1),
            help="Choisissez explicitement la date du transfert."
        )

        confirmation = st.checkbox(
            "Je confirme le transfert"
        )

        transferer = st.form_submit_button(
            "Valider le transfert"
        )


    if transferer:

        id_etudiant, id_origine, debut = (
            options_origine[origine]
        )
        id_destination = options_dest[destination]

        if date_transfert is None:
            st.warning("Veuillez choisir la date du transfert.")

        elif not confirmation:
            st.warning("Veuillez confirmer le transfert.")

        elif id_origine == id_destination:
            st.error("Le nouveau groupe doit etre different.")

        elif date_transfert.isoformat() <= debut:
            st.error("La date de transfert est trop ancienne.")

        else:
            fin_origine = (
                date_transfert - timedelta(days=1)
            ).isoformat()

            conn = connect()

            try:
                with conn:

                    # Terminer l'ancienne affectation
                    resultat = conn.execute("""
                        UPDATE student_groupes
                        SET date_fin = ?
                        WHERE student_id = ?
                          AND groupe_id = ?
                          AND date_debut = ?
                          AND date_fin IS NULL
                    """, (
                        fin_origine,
                        id_etudiant,
                        id_origine,
                        debut
                    ))

                    if resultat.rowcount != 1:
                        raise ValueError(
                            "Affectation d'origine introuvable."
                        )

                    # Creer la nouvelle affectation
                    conn.execute("""
                        INSERT INTO student_groupes
                        (student_id, groupe_id, date_debut)
                        VALUES (?, ?, ?)
                    """, (
                        id_etudiant,
                        id_destination,
                        date_transfert.isoformat()
                    ))

                st.success("Transfert effectue avec succes !")

            except sqlite3.IntegrityError:
                st.error(
                    "Transfert refuse : periode invalide "
                    "ou chevauchement des affectations."
                )

            except ValueError as erreur:
                st.error(str(erreur))

            finally:
                conn.close()

else:
    st.info(
        "Deux groupes et une affectation ouverte "
        "sont necessaires."
    )
