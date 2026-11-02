
import streamlit as st
import pandas as pd
import sqlite3
from database import DB_PATH
from rfid_reader import lire_uid
from pointage_service import normaliser_uid
from datetime import date

# Titre
st.title("Gestion des etudiants")

# Connexion a SQLite
conn = sqlite3.connect(DB_PATH)

# Recuperer les etudiants
df_students = pd.read_sql_query("""
    SELECT
        id AS ID,
        name AS Nom,
        uid AS UID,
        date_inscription AS Date_inscription
    FROM students
    ORDER BY name ASC
""", conn)

conn.close()

# Afficher les statistiques
st.metric("Total des etudiants", len(df_students))

# Afficher la liste
st.subheader("Liste des etudiants")

st.dataframe(
    df_students,
    width="stretch",
    hide_index=True
)

# Scanner une carte RFID
st.subheader("Scanner une carte RFID")

if st.button("Scanner la carte", key="scanner_etudiants"):
    st.session_state.pop("student_page_uid", None)
    try:
        with st.spinner("Approchez votre carte du lecteur RFID..."):
            uid_detected = lire_uid()
        if uid_detected:
            st.session_state["student_page_uid"] = normaliser_uid(uid_detected)
            st.rerun()
        else:
            st.warning("Aucune carte detectee.")
    except Exception as exc:
        st.error(f"Erreur de connexion RFID : {exc}")

# Afficher la carte detectee
if "student_page_uid" in st.session_state:
    st.success(
        "Carte detectee : " + st.session_state["student_page_uid"]
    )


# Inscription d'un nouvel etudiant
st.subheader("Ajouter un etudiant")

# Saisir le nom
nom = st.text_input("Nom de l'etudiant")

# Recuperer la carte scannee
uid = normaliser_uid(st.session_state.get("student_page_uid", ""))

# Annuler la carte selectionnee
if uid:
    if st.button("Annuler la carte", key="annuler_carte_etudiant"):
        st.session_state.pop("student_page_uid", None)
        st.rerun()

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
    else:
        st.success("Carte disponible pour l'inscription.")

else:
    st.info("Veuillez scanner une carte RFID.")

# Bouton d'inscription
if st.button(
    "Enregistrer l'etudiant",
    disabled=not (nom.strip() and uid) or registered_name is not None,
    key="enregistrer_etudiant_page"
):

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO students (name, uid, date_inscription)
            VALUES (?, ?, ?)
        """, (
            nom.strip(),
            uid,
            date.today().isoformat()
        ))

        conn.commit()
        st.success("Etudiant enregistre avec succes !")

    except sqlite3.IntegrityError:
        st.error("Cette carte est deja enregistree !")

    finally:
        conn.close()
