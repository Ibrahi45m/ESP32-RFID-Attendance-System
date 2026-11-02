
import streamlit as st
import pandas as pd
import sqlite3
from database import DB_PATH
from rapports_service import bilan_seance, bilan_global_etudiants

# Titre
st.title("Rapports des presences")

# Détecter les pointages historiques d'essai hors horaire.
conn_anomalies = sqlite3.connect(DB_PATH)
pointages_hors_horaires = conn_anomalies.execute("""
    SELECT COUNT(*)
    FROM attendance_seances AS a
    JOIN seances AS s ON s.id = a.seance_id
    WHERE substr(a.heure_pointage, 1, 5) < s.heure_debut
       OR substr(a.heure_pointage, 1, 5) >= s.heure_fin
""").fetchone()[0]
conn_anomalies.close()
if pointages_hors_horaires:
    st.warning(
        f"{pointages_hors_horaires} pointage(s) historique(s) hors de l'horaire "
        "de la séance. Ce sont potentiellement des données de test : "
        "les taux affichés ne doivent pas être utilisés comme relevés officiels."
    )

# Organisation de la page Rapports
tab_presences, tab_global, tab_individuel = st.tabs([
    "Presences par seance",
    "Bilan global",
    "Rapport individuel"
])

with tab_presences:
    # Connexion a SQLite
    conn = sqlite3.connect(DB_PATH)

    # Recuperer les presences par seance
    df_rapports = pd.read_sql_query("""
        SELECT
            seances.id AS Seance_ID,
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

    conn.close()


    # Titre de l'historique
    st.subheader("Historique des presences par seance")

    # Tous les modules, même sans pointage.
    conn_modules = sqlite3.connect(DB_PATH)
    modules_disponibles = [row[0] for row in conn_modules.execute("""
        SELECT DISTINCT module FROM seances ORDER BY module COLLATE NOCASE
    """).fetchall()]
    conn_modules.close()
    modules = ["Tous les modules"] + modules_disponibles

    # Selectionner un module
    module_choisi = st.selectbox(
        "Choisir un module",
        modules
    )

    # Filtrer les presences
    if module_choisi == "Tous les modules":
        df_filtre = df_rapports
    else:
        df_filtre = df_rapports[
            df_rapports["Module"] == module_choisi
        ]

    # Recuperer toutes les seances
    conn = sqlite3.connect(DB_PATH)

    df_seances = pd.read_sql_query("""
        SELECT id, module, date, heure_debut, heure_fin
        FROM seances
        ORDER BY date DESC, heure_debut ASC
    """, conn)

    conn.close()

    # Garder les seances du module choisi
    if module_choisi != "Tous les modules":
        df_seances = df_seances[
            df_seances["module"] == module_choisi
        ]

    # Construire les choix
    options_seances = {"Toutes les seances": None}

    for _, ligne in df_seances.iterrows():
        label = (
            f"{ligne['module']} | {ligne['date']} | "
            f"{ligne['heure_debut']} - {ligne['heure_fin']} | "
            f"ID {ligne['id']}"
        )
        options_seances[label] = int(ligne["id"])

    # Choisir une seance precise
    choix_seance = st.selectbox(
        "Choisir une seance",
        list(options_seances.keys())
    )

    seance_id = options_seances[choix_seance]

    # Appliquer le filtre
    if seance_id is not None:
        df_filtre = df_filtre[
            df_filtre["Seance_ID"] == seance_id
        ]

    # Afficher le nombre de pointages filtres
    st.metric("Pointages affiches", len(df_filtre))

    # Afficher le tableau
    st.dataframe(
        df_filtre.drop(columns=["Seance_ID"]),
        width="stretch",
        hide_index=True
    )


    # Absences par seance
    if seance_id is not None:

        st.subheader("Sans pointage par seance")

        # Recuperer la seance selectionnee
        ligne = df_seances[
            df_seances["id"] == seance_id
        ].iloc[0]

        # Date et heure de fin de la seance
        from datetime import datetime

        fin_seance = datetime.strptime(
            ligne["date"] + " " + ligne["heure_fin"],
            "%Y-%m-%d %H:%M"
        )

        # Seuls les étudiants des groupes de la séance sont attendus.
        # Les séances historiques sans groupe gardent un bilan provisoire.
        conn = sqlite3.connect(DB_PATH)
        try:
            bilan = bilan_seance(conn, seance_id)
        finally:
            conn.close()

        if not bilan["terminee"]:
            st.info(
                "Cette seance n'est pas encore terminee. "
                "Les absences ne sont pas encore disponibles."
            )
        else:
            if not bilan["avec_groupe"]:
                st.warning(
                    "Seance historique sans groupe : la liste des etudiants "
                    "est une estimation (tous les inscrits a cette date). "
                    "Ce bilan n'est pas un releve officiel."
                )
            else:
                st.caption("Etudiants attendus : membres des groupes "
                           "affectes a cette seance, a sa date.")

            st.caption("Sans pointage ne signifie pas absence confirmee.")
            st.metric("Total sans pointage", len(bilan["sans_pointage"]))

            if bilan["sans_pointage"].empty:
                st.success("Aucun etudiant sans pointage parmi les attendus.")
            else:
                st.dataframe(
                    bilan["sans_pointage"][["Etudiant"]],
                    width="stretch", hide_index=True
                )

            if bilan["pointages_hors_groupe"]:
                st.error(
                    f"{bilan['pointages_hors_groupe']} pointage(s) "
                    "hors du perimetre du groupe. Ils ne sont pas "
                    "comptes dans le taux."
                )

            st.metric("Etudiants attendus", bilan["total_attendus"])
            st.metric("Presences des etudiants attendus", bilan["presences_eligibles"])
            if bilan["taux"] is None:
                st.info("Taux non defini : aucun etudiant attendu.")
            else:
                st.metric("Taux de presence de la seance", f"{bilan['taux']:.1f}%")

with tab_global:
    # Rapport global par module
    st.subheader("Rapport global par module")

    from datetime import datetime

    # Date et heure actuelles
    maintenant = datetime.now()

    date_actuelle = maintenant.strftime("%Y-%m-%d")
    heure_actuelle = maintenant.strftime("%H:%M")

    # Connexion a SQLite
    conn = sqlite3.connect(DB_PATH)

    # Compter les seances terminees par module
    df_global = pd.read_sql_query("""
        SELECT
            module AS Module,
            COUNT(*) AS Seances_terminees
        FROM seances
        WHERE date < ?
        OR (date = ? AND heure_fin <= ?)
        GROUP BY module
        ORDER BY module ASC
    """, conn, params=(
        date_actuelle,
        date_actuelle,
        heure_actuelle
    ))

    conn.close()

    # Afficher les resultats
    st.dataframe(
        df_global,
        width="stretch",
        hide_index=True
    )
with tab_individuel:
    # Rapport detaille par etudiant et par module
    st.subheader("Bilan des etudiants par module")
    st.caption(
        "Les seances avec groupe prennent uniquement les membres affectes "
        "a la date de la seance. Les seances sans groupe restent en mode "
        "Historique sans groupe (estimation non officielle)."
    )

    conn = sqlite3.connect(DB_PATH)
    try:
        df_bilan = bilan_global_etudiants(conn)
    finally:
        conn.close()

    # Calculer le taux de presence pour chaque etudiant
    df_bilan["Taux de presence (%)"] = (
        df_bilan["Presences"] / df_bilan["Seances"] * 100
    ).round(1).fillna(0)


    # Filtrer le bilan par module
    modules_bilan = ["Tous les modules"] + sorted(
        df_bilan["Module"].unique().tolist()
    )

    module_bilan = st.selectbox(
        "Choisir un module pour le bilan",
        modules_bilan,
        key="filtre_bilan_module"
    )

    # Appliquer le filtre
    if module_bilan == "Tous les modules":
        df_bilan_filtre = df_bilan
    else:
        df_bilan_filtre = df_bilan[
            df_bilan["Module"] == module_bilan
        ]

    # Utiliser l'ID : deux etudiants peuvent avoir le même nom.
    etudiants_bilan = {"Tous les etudiants": None}
    for _, etudiant in df_bilan[["Etudiant_ID", "Etudiant"]].drop_duplicates().iterrows():
        etudiants_bilan[
            f"{etudiant['Etudiant']} | ID {int(etudiant['Etudiant_ID'])}"
        ] = int(etudiant["Etudiant_ID"])

    etudiant_choisi = st.selectbox(
        "Choisir un etudiant pour le bilan",
        list(etudiants_bilan.keys()),
        key="filtre_bilan_etudiant"
    )
    etudiant_id_choisi = etudiants_bilan[etudiant_choisi]

    if etudiant_id_choisi is not None:
        df_bilan_filtre = df_bilan_filtre[
            df_bilan_filtre["Etudiant_ID"] == etudiant_id_choisi
        ]

    st.dataframe(
        df_bilan_filtre.drop(columns=["Etudiant_ID"]),
        width="stretch",
        hide_index=True
    )

    # Bilan individuel de l'etudiant
    if etudiant_id_choisi is not None:

        st.subheader("Bilan individuel")

        # Calculer les totaux
        total_seances = int(df_bilan_filtre["Seances"].sum())
        total_presences = int(df_bilan_filtre["Presences"].sum())
        total_absences = int(df_bilan_filtre["Sans_pointage"].sum())

        # Calculer le taux global
        if total_seances > 0:
            taux_global = (total_presences / total_seances) * 100
        else:
            taux_global = 0

        # Afficher les indicateurs
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total des seances", total_seances)

        with col2:
            st.metric("Presences", total_presences)

        with col3:
            st.metric("Sans pointage", total_absences)

        with col4:
            st.metric("Taux global", f"{taux_global:.1f}%")

        # Exporter le rapport individuel
        csv_individuel = df_bilan_filtre.drop(
            columns=["Etudiant_ID"]
        ).to_csv(index=False).encode("utf-8-sig")

        # Nom de fichier unique même si deux étudiants ont le même nom.
        nom_fichier = f"rapport_etudiant_ID{etudiant_id_choisi}.csv"

        # Bouton de telechargement
        st.download_button(
            label="Telecharger le rapport individuel (CSV)",
            data=csv_individuel,
            file_name=nom_fichier,
            mime="text/csv",
            key="export_rapport_individuel"
        )
