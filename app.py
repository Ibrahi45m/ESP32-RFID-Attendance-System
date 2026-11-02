
import streamlit as st
import sqlite3
from database import DB_PATH, init_database
import pandas as pd
from datetime import datetime

init_database()

# Configuration de l'application
st.set_page_config(
    page_title="RFID Attendance System",
    page_icon="📚",
    layout="wide"
)


def accueil():
    st.title("RFID Attendance System")
    st.write("Tableau de bord - Vue generale")

    # Connexion a SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Nombre d'etudiants
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    # Nombre de seances
    cursor.execute("SELECT COUNT(*) FROM seances")
    total_seances = cursor.fetchone()[0]

    # Nombre de pointages par seance
    cursor.execute("SELECT COUNT(*) FROM attendance_seances")
    total_pointages = cursor.fetchone()[0]

    conn.close()

    # Afficher les statistiques
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total des etudiants", total_students)

    with col2:
        st.metric("Total des seances", total_seances)

    with col3:
        st.metric("Pointages par seance", total_pointages)

    # Afficher les prochaines seances
    st.subheader("Prochaines seances")

    # Date et heure actuelles
    maintenant = datetime.now()
    date_actuelle = maintenant.strftime("%Y-%m-%d")
    heure_actuelle = maintenant.strftime("%H:%M")

    # Connexion a SQLite
    conn = sqlite3.connect(DB_PATH)

    # Rechercher les prochaines seances
    df_prochaines = pd.read_sql_query("""
        SELECT
            module AS Module,
            date AS Date,
            heure_debut AS Debut,
            heure_fin AS Fin
        FROM seances
        WHERE date > ?
           OR (date = ? AND heure_debut >= ?)
        ORDER BY date ASC, heure_debut ASC
        LIMIT 5
    """, conn, params=(
        date_actuelle,
        date_actuelle,
        heure_actuelle
    ))

    conn.close()

    # Afficher les resultats
    if df_prochaines.empty:
        st.info("Aucune prochaine seance programmee.")
    else:
        st.dataframe(
            df_prochaines,
            width="stretch",
            hide_index=True
        )



# Definition des pages
page_accueil = st.Page(
    accueil,
    title="Accueil",
    icon="🏠",
    default=True
)

page_dashboard = st.Page(
    "dashboard.py",
    title="Ancien dashboard (test)",
    icon="📊"
)

page_etudiants = st.Page(
    "etudiants_page.py",
    title="Etudiants",
    icon="👨‍🎓"
)

page_seances = st.Page(
    "seances_page.py",
    title="Seances",
    icon="📅"
)

page_pointage = st.Page(
    "pointage_page.py",
    title="Pointage RFID",
    icon="📡"
)

page_groupes = st.Page(
    "groupes_page.py",
    title="Groupes",
    icon="👥"
)

page_rapports = st.Page(
    "rapports_page.py",
    title="Rapports",
    icon="📊"
)

navigation = st.navigation(
    [
        page_accueil,
        page_etudiants,
        page_groupes,
        page_seances,
        page_pointage,
        page_rapports,
        page_dashboard
    ],
    position="sidebar"
)

# Afficher la page selectionnee
navigation.run()
