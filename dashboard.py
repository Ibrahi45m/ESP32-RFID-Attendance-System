
import streamlit as st
import pandas as pd

import sqlite3
from database import DB_PATH

import serial
import time

from datetime import date
from datetime import time as dt_time

# Titre principal
st.title("RFID Attendance System")

# Description
st.write("Bienvenue dans le système de gestion des présences.")

# Sous-titre
st.subheader("Tableau de bord")

# Choisir le mode de fonctionnement
mode = st.radio(
    "Mode de fonctionnement",
    ["Inscription", "Presence"]
)

# Afficher le mode choisi
st.write("Mode selectionne :", mode)

# Afficher un message selon le mode choisi

if mode == "Inscription":
    st.info("Mode Inscription : Ajouter un nouvel etudiant")

elif mode == "Presence":
    st.success("Mode Presence : Enregistrer les presences")

# Message
st.info("Le système RFID est prêt !")


# Connexion a SQLite
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Compter les etudiants
cursor.execute("SELECT COUNT(*) FROM students")

# Recuperer le resultat
total_students = cursor.fetchone()[0]


# Compter les presences
cursor.execute("SELECT COUNT(*) FROM attendance")

total_attendance = cursor.fetchone()[0]

# Fermer la connexion
conn.close()

# Afficher le nombre dans le Dashboard

# Creer deux colonnes
col1, col2 = st.columns(2)

# Premiere colonne
with col1:
    st.metric("Total des etudiants", total_students)

# Deuxieme colonne
with col2:
    st.metric("Total des presences", total_attendance)


# Afficher l'historique des presences
st.subheader("Historique des presences")

# Bouton pour actualiser les donnees
if st.button("Actualiser les donnees"):
    st.success("Donnees actualisees !")

# Connexion a SQLite
conn = sqlite3.connect(DB_PATH)

# Lire les donnees
df = pd.read_sql_query("""
    SELECT student AS Etudiant,
           date AS Date,
           time AS Heure
    FROM attendance
    ORDER BY date DESC, time DESC
""", conn)

# Fermer la connexion
conn.close()


# Recuperer les dates disponibles
dates = sorted(df["Date"].unique(), reverse=True)

# Choisir une date
selected_date = st.selectbox(
    "Choisir une date",
    ["Toutes les dates"] + list(dates)
)

# Filtrer les donnees
if selected_date == "Toutes les dates":
    filtered_df = df
else:
    filtered_df = df[df["Date"] == selected_date]

# Nombre de presences apres filtrage
total_filtered = len(filtered_df)

# Afficher le resultat
st.metric("Presences affichees", total_filtered)

# Afficher le tableau filtre
st.dataframe(filtered_df, width="stretch", hide_index=True)

# Liste des etudiants sans presence
st.subheader("Etudiants absents dans la seance")

if selected_date == "Toutes les dates":
    st.info("Choisissez une date pour afficher les absents.")

else:
    # Connexion a SQLite
    conn = sqlite3.connect(DB_PATH)

    # Chercher les etudiants sans presence
    df_absents = pd.read_sql_query("""
        SELECT name AS Etudiant
        FROM students
        WHERE date_inscription <= ?
          AND uid NOT IN (
              SELECT uid
              FROM attendance
              WHERE date = ?
          )
        ORDER BY name ASC
    """, conn, params=(selected_date, selected_date))

    # Compter les etudiants inscrits a cette date
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM students
        WHERE date_inscription <= ?
    """, (selected_date,))

    total_inscrits = cursor.fetchone()[0]

    # Fermer la connexion
    conn.close()

    # Afficher l'effectif
    st.metric("Effectif inscrit a cette date", total_inscrits)

    # Calculer le taux de presence
    if total_inscrits > 0:
        taux_presence = (total_filtered / total_inscrits) * 100
    else:
        taux_presence = 0

    # Afficher le taux
    st.metric("Taux de presence", f"{taux_presence:.1f}%")

    # Compter les etudiants sans presence
    total_absents = len(df_absents)

    st.metric("Total des absents", total_absents)

    # Afficher les absents
    if df_absents.empty:
        st.success(
            "Tous les etudiants inscrits ont une presence enregistree pour cette date !"
        )
    else:
        st.dataframe(
            df_absents,
            width="stretch",
            hide_index=True
        )



# Convertir le tableau filtre en CSV
csv_data = filtered_df.to_csv(index=False).encode("utf-8-sig")

# Bouton pour telecharger le fichier
st.download_button(
    label="Telecharger les presences (CSV)",
    data=csv_data,
    file_name="presences.csv",
    mime="text/csv"
)

# Statistiques par date
stats = df.groupby("Date").size().reset_index(name="Presences")

# Titre du graphique
st.subheader("Presences par jour")

# Afficher le graphique
st.bar_chart(stats, x="Date", y="Presences")


# Statistiques par etudiant
student_stats = df.groupby("Etudiant").size().reset_index(name="Presences")

# Titre
st.subheader("Presences par etudiant")

# Graphique
st.bar_chart(student_stats, x="Etudiant", y="Presences")


# Liste des etudiants
st.subheader("Liste des etudiants")

# Connexion a SQLite
conn = sqlite3.connect(DB_PATH)

# Lire les etudiants
df_students = pd.read_sql_query("""
    SELECT id AS ID, name AS Etudiant
    FROM students
    ORDER BY name ASC
""", conn)

# Fermer la connexion
conn.close()

# Afficher la liste
st.dataframe(
    df_students,
    width="stretch",
    hide_index=True
)

# Inscription d'un nouvel etudiant
st.subheader("Ajouter un etudiant")

# Saisir le nom
name = st.text_input("Nom de l'etudiant")


# Recuperer l'UID scannee
uid = st.session_state.get("scanned_uid", "")

# Afficher le statut de la carte
if uid:
    st.info("Carte RFID selectionnee : " + uid)
else:
    st.warning("Veuillez scanner une carte RFID.")

# Afficher Annuler seulement si une carte existe
if uid:
    if st.button("Annuler la carte"):
        st.session_state.pop("scanned_uid", None)
        st.rerun()


# Afficher le nom saisi
if name:
    st.write("Nom saisi :", name)


# Verifier si la carte est deja inscrite
registered_name = None

if uid:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT name FROM students WHERE uid = ?",
        (uid,)
    )

    result = cursor.fetchone()
    conn.close()

    if result is not None:
        registered_name = result[0]
        st.warning(
            "Cette carte appartient deja a : " + registered_name
        )

# Bouton d'inscription

if st.button(
    "Enregistrer l'etudiant",
    disabled=not (name.strip() and uid) or registered_name is not None
):

    name = name.strip()

    # Verifier les champs
    if not name or not uid:
        st.warning("Veuillez remplir tous les champs.")

    else:
        # Connexion a SQLite
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Verifier si l'UID existe
        cursor.execute(
            "SELECT name FROM students WHERE uid = ?",
            (uid,)
        )

        result = cursor.fetchone()

        if result is not None:
            st.error(
                "Carte deja enregistree pour : " + result[0]
            )

        else:
            # Ajouter le nouvel etudiant
            # Date d'inscription automatique
            date_inscription = date.today().isoformat()

            # Ajouter l'etudiant
            cursor.execute(
                """
                INSERT INTO students (name, uid, date_inscription)
                VALUES (?, ?, ?)
                """,
                (name, uid, date_inscription)
            )


            conn.commit()

            st.success("Etudiant enregistre avec succes !")

        conn.close()

# Lecture automatique de la carte RFID
st.subheader("Scanner une carte RFID")

if st.button("Scanner la carte"):
    st.session_state.pop("scanned_uid", None)
    st.info("Approchez votre carte du lecteur RFID...")

    try:
        with serial.Serial("COM7", 115200, timeout=1) as esp32:
            time.sleep(2)

            uid_detected = None
            start_time = time.monotonic()

            while time.monotonic() - start_time < 12:
                line = esp32.readline().decode(
                    "utf-8", errors="replace"
                ).strip()

                if line.startswith("Card UID:"):
                    uid_detected = line.split(":", 1)[1].strip().upper()
                    break


        if uid_detected:
            st.session_state["scanned_uid"] = uid_detected

            st.rerun()
        else:
            st.warning("Aucune carte detectee.")

    except serial.SerialException as e:
        st.error(f"Erreur de connexion RFID : {e}")

# Afficher l'UID sauvegardee dans la session
if "scanned_uid" in st.session_state:
    st.info(
        "UID sauvegardee : " + st.session_state["scanned_uid"]
    )


# Afficher les presences par seance
st.subheader("Presences par seance")

# Connexion a SQLite
conn = sqlite3.connect(DB_PATH)

# Lire les presences avec JOIN
df_seances = pd.read_sql_query("""
    SELECT
        students.name AS Etudiant,
        seances.module AS Module,
        seances.date AS Date,
        attendance_seances.heure_pointage AS Heure
    FROM attendance_seances

    JOIN students
        ON attendance_seances.student_id = students.id

    JOIN seances
        ON attendance_seances.seance_id = seances.id

    ORDER BY seances.date DESC,
             attendance_seances.heure_pointage DESC
""", conn)

# Fermer la connexion
conn.close()

# Afficher le nombre de presences

# Recuperer les modules disponibles
modules = ["Tous les modules"] + sorted(
    df_seances["Module"].unique().tolist()
)

# Choisir un module
selected_module = st.selectbox(
    "Choisir un module",
    modules
)

# Filtrer les presences
if selected_module == "Tous les modules":
    df_filtre = df_seances
else:
    df_filtre = df_seances[
        df_seances["Module"] == selected_module
    ]

# Afficher le nombre de presences
st.metric("Presences affichees par seance", len(df_filtre))

# Afficher le tableau filtre
st.dataframe(
    df_filtre,
    width="stretch",
    hide_index=True
)

# Convertir les presences filtrees en CSV
csv_seances = df_filtre.to_csv(index=False).encode("utf-8-sig")

# Telecharger les presences par seance
st.download_button(
    label="Telecharger les presences par seance (CSV)",
    data=csv_seances,
    file_name="presences_par_seance.csv",
    mime="text/csv"
)

# Gestion des seances
st.subheader("Gestion des seances")

# Formulaire d'ajout
with st.form("form_ajout_seance"):

    module = st.text_input("Nom du module")

    date_seance = st.date_input("Date de la seance")


    # Choisir l'heure de debut
    st.write("Heure de debut")

    col_h1, col_m1 = st.columns(2)

    with col_h1:
        h_debut = st.selectbox(
            "Heures debut",
            range(24),
            index=8,
            format_func=lambda x: f"{x:02d}"
        )

    with col_m1:
        m_debut = st.selectbox(
            "Minutes debut",
            range(60),
            index=30,
            format_func=lambda x: f"{x:02d}"
        )

    # Choisir l'heure de fin
    st.write("Heure de fin")

    col_h2, col_m2 = st.columns(2)

    with col_h2:
        h_fin = st.selectbox(
            "Heures fin",
            range(24),
            index=10,
            format_func=lambda x: f"{x:02d}"
        )

    with col_m2:
        m_fin = st.selectbox(
            "Minutes fin",
            range(60),
            index=30,
            format_func=lambda x: f"{x:02d}"
        )

    # Construire les horaires
    heure_debut = dt_time(h_debut, m_debut)
    heure_fin = dt_time(h_fin, m_fin)


    # Bouton de validation
    submitted = st.form_submit_button("Enregistrer la seance")



# Verifier les informations du formulaire
if submitted:

    if not module.strip():
        st.error("Veuillez saisir le nom du module.")

    elif heure_fin <= heure_debut:
        st.error(
            "Erreur : l'heure de fin doit etre apres l'heure de debut."
        )

    else:
        # Preparer les informations
        module = module.strip()
        date_sql = date_seance.isoformat()
        debut_sql = heure_debut.strftime("%H:%M")
        fin_sql = heure_fin.strftime("%H:%M")

        # Connexion a SQLite
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Verifier si la seance existe deja
        cursor.execute("""
            SELECT id
            FROM seances
            WHERE module = ?
              AND date = ?
              AND heure_debut = ?
              AND heure_fin = ?
        """, (module, date_sql, debut_sql, fin_sql))

        seance_existante = cursor.fetchone()

        if seance_existante:
            st.warning("Cette seance existe deja !")

        else:
            # Verifier le chevauchement
            cursor.execute("""
                SELECT module, heure_debut, heure_fin
                FROM seances
                WHERE date = ?
                  AND heure_debut < ?
                  AND heure_fin > ?
            """, (date_sql, fin_sql, debut_sql))

            conflits = cursor.fetchall()

            if conflits:
                st.error("Chevauchement detecte !")

                for conflit in conflits:
                    st.warning(
                        f"Seance existante : {conflit[0]} "
                        f"({conflit[1]} - {conflit[2]})"
                    )

            else:
                # Ajouter la nouvelle seance
                cursor.execute("""
                    INSERT INTO seances
                    (module, date, heure_debut, heure_fin)
                    VALUES (?, ?, ?, ?)
                """, (module, date_sql, debut_sql, fin_sql))

                conn.commit()

                st.success("Seance enregistree avec succes !")

        conn.close()

# Liste des seances enregistrees
st.subheader("Liste des seances")

# Connexion a SQLite
conn = sqlite3.connect(DB_PATH)

# Recuperer les seances
df_liste_seances = pd.read_sql_query("""
    SELECT
        id AS ID,
        module AS Module,
        date AS Date,
        heure_debut AS Debut,
        heure_fin AS Fin
    FROM seances
    ORDER BY date DESC, heure_debut ASC
""", conn)

# Fermer la connexion
conn.close()

# Afficher le nombre de seances
st.metric("Total des seances", len(df_liste_seances))

# Afficher le tableau
st.dataframe(
    df_liste_seances,
    width="stretch",
    hide_index=True
)

# Selectionner une seance
st.subheader("Consulter une seance")

# Preparer les choix
options_seances = {}

for _, row in df_liste_seances.iterrows():
    label = (
        f"{row['Module']} | {row['Date']} | "
        f"{row['Debut']} - {row['Fin']} | ID {row['ID']}"
    )

    options_seances[label] = int(row["ID"])

# Afficher les choix
if options_seances:
    seance_choisie = st.selectbox(
        "Choisir une seance",
        list(options_seances.keys())
    )

    # Recuperer son ID
    selected_seance_id = options_seances[seance_choisie]


    # Afficher les etudiants presents dans la seance
    st.subheader("Etudiants presents dans la seance")

    # Connexion a SQLite
    conn = sqlite3.connect(DB_PATH)

    # Recuperer les presences de la seance selectionnee
    df_presents = pd.read_sql_query("""
        SELECT
            students.name AS Etudiant,
            attendance_seances.heure_pointage AS Heure
        FROM attendance_seances
        JOIN students
            ON attendance_seances.student_id = students.id
        WHERE attendance_seances.seance_id = ?
        ORDER BY attendance_seances.heure_pointage ASC
    """, conn, params=(selected_seance_id,))

    conn.close()

    # Afficher le nombre de presents
    st.metric("Total des presents", len(df_presents))

    # Afficher les etudiants
    if df_presents.empty:
        st.info("Aucune presence enregistree pour cette seance.")
    else:
        st.dataframe(
            df_presents,
            width="stretch",
            hide_index=True
        )

    # Etudiants sans pointage dans la seance
    st.subheader("Etudiants absents dans la seance")

    conn = sqlite3.connect(DB_PATH)

    df_absents_seance = pd.read_sql_query("""
        SELECT students.name AS Etudiant
        FROM students
        JOIN seances
            ON seances.id = ?
        WHERE students.date_inscription <= seances.date
          AND NOT EXISTS (
              SELECT 1
              FROM attendance_seances
              WHERE attendance_seances.student_id = students.id
                AND attendance_seances.seance_id = seances.id
          )
        ORDER BY students.name ASC
    """, conn, params=(selected_seance_id,))

    conn.close()

    # Nombre d'etudiants sans pointage
    st.metric(
        "Total des absents",
        len(df_absents_seance)
    )

    # Calculer le taux de presence par seance
    total_presents = len(df_presents)
    total_absents = len(df_absents_seance)

    total_concernes = total_presents + total_absents

    if total_concernes > 0:
        taux_presence = (total_presents / total_concernes) * 100
    else:
        taux_presence = 0

    # Afficher le taux
    st.metric(
        "Taux de presence de la seance",
        f"{taux_presence:.1f}%"
    )


    # Afficher la liste
    if df_absents_seance.empty:
        st.success("Aucun etudiant absent dans cette seance !")
    else:
        st.dataframe(
            df_absents_seance,
            width="stretch",
            hide_index=True
        )

    # Exporter les absents de la seance
    csv_absents = df_absents_seance.to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        label="Telecharger les absents (CSV)",
        data=csv_absents,
        file_name=f"absents_seance_{selected_seance_id}.csv",
        mime="text/csv"
    )


    st.info(f"Seance selectionnee : ID {selected_seance_id}")

else:
    st.warning("Aucune seance disponible.")



# Modifier une seance
st.subheader("Modifier une seance")
if st.session_state.pop("modification_ok", False):
    st.success("Seance modifiee avec succes !")

if options_seances:

    # Choisir une seance
    choix_modification = st.selectbox(
        "Choisir la seance a modifier",
        list(options_seances.keys()),
        key="select_modification"
    )

    id_modification = options_seances[choix_modification]

    st.info(f"Seance a modifier : ID {id_modification}")

    # Recuperer les informations actuelles
    ligne = df_liste_seances[
        df_liste_seances["ID"] == id_modification
    ].iloc[0]

    ancien_module = ligne["Module"]
    ancienne_date = date.fromisoformat(ligne["Date"])
    ancien_debut = dt_time.fromisoformat(ligne["Debut"])
    ancienne_fin = dt_time.fromisoformat(ligne["Fin"])

    # Formulaire de modification
    with st.form(f"form_modifier_{id_modification}"):

        nouveau_module = st.text_input(
            "Module",
            value=ancien_module
        )

        nouvelle_date = st.date_input(
            "Date",
            value=ancienne_date
        )

        st.write("Heure de debut")

        col1, col2 = st.columns(2)

        with col1:
            h_debut_mod = st.selectbox(
                "Heures debut",
                range(24),
                index=ancien_debut.hour,
                format_func=lambda x: f"{x:02d}"
            )

        with col2:
            m_debut_mod = st.selectbox(
                "Minutes debut",
                range(60),
                index=ancien_debut.minute,
                format_func=lambda x: f"{x:02d}"
            )

        st.write("Heure de fin")

        col3, col4 = st.columns(2)

        with col3:
            h_fin_mod = st.selectbox(
                "Heures fin",
                range(24),
                index=ancienne_fin.hour,
                format_func=lambda x: f"{x:02d}"
            )

        with col4:
            m_fin_mod = st.selectbox(
                "Minutes fin",
                range(60),
                index=ancienne_fin.minute,
                format_func=lambda x: f"{x:02d}"
            )

        modifier = st.form_submit_button(
            "Valider la modification"
        )

    # Tester les informations sans modifier SQLite
    if modifier:

        nouveau_module = nouveau_module.strip()
        nouveau_debut = dt_time(h_debut_mod, m_debut_mod)
        nouvelle_fin = dt_time(h_fin_mod, m_fin_mod)

        # Verifier les informations
        if not nouveau_module:
            st.error("Veuillez saisir le nom du module.")

        elif nouvelle_fin <= nouveau_debut:
            st.error(
                "L'heure de fin doit etre apres l'heure de debut."
            )

        else:
            date_sql = nouvelle_date.isoformat()
            debut_sql = nouveau_debut.strftime("%H:%M")
            fin_sql = nouvelle_fin.strftime("%H:%M")

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Rechercher les conflits avec les autres seances
            cursor.execute("""
                SELECT module, heure_debut, heure_fin
                FROM seances
                WHERE id != ?
                  AND date = ?
                  AND heure_debut < ?
                  AND heure_fin > ?
            """, (
                id_modification,
                date_sql,
                fin_sql,
                debut_sql
            ))

            conflits = cursor.fetchall()

            if conflits:
                st.error("Modification refusee : chevauchement detecte !")

                for conflit in conflits:
                    st.warning(
                        f"Seance existante : {conflit[0]} "
                        f"({conflit[1]} - {conflit[2]})"
                    )

            else:
                # Modifier la seance
                cursor.execute("""
                    UPDATE seances
                    SET module = ?,
                        date = ?,
                        heure_debut = ?,
                        heure_fin = ?
                    WHERE id = ?
                """, (
                    nouveau_module,
                    date_sql,
                    debut_sql,
                    fin_sql,
                    id_modification
                ))

                conn.commit()

                st.session_state["modification_ok"] = True
                st.rerun()

            conn.close()


else:
    st.warning("Aucune seance disponible.")
