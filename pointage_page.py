"""Suivi du pointage automatique, avec mode manuel de secours."""
import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from database import connect
from pointage_service import enregistrer_pointage
from rfid_reader import lire_uid

st.title("Pointage RFID")
st.caption("Le mode AUTO enregistre chaque carte sans clic si rfid_auto_worker.py est lance. Fermez le Moniteur serie Arduino.")

STATUT_PATH = Path(__file__).resolve().parent / "rfid_auto_status.json"


def lire_statut_auto():
    try:
        etat = json.loads(STATUT_PATH.read_text(encoding="utf-8"))
        dernier_signal = datetime.fromisoformat(etat["heartbeat"])
        if abs((datetime.now() - dernier_signal).total_seconds()) > 8:
            return None
        return etat
    except (FileNotFoundError, OSError, ValueError, KeyError, TypeError):
        return None


def afficher_mode_auto():
    st.subheader("Mode automatique — sans clic")
    statut = lire_statut_auto()
    if statut is None:
        st.info("Mode AUTO non demarre. Lancez demarrer_rfid_auto.bat dans le dossier du projet.")
        return

    lecteur = statut.get("lecteur")
    fenetre = statut.get("fenetre")
    if lecteur != "connecte":
        st.error("Lecteur deconnecte : " + statut.get("message", ""))
    elif fenetre == "actif":
        seance = statut.get("seance") or {}
        st.success(
            f"SCAN AUTOMATIQUE ACTIF — {seance.get('module', 'Seance')} "
            f"(ID {seance.get('seance_id', '?')}) | fermeture {seance.get('limite', '?')}"
        )
    elif fenetre == "ferme":
        st.warning("Fenetre de pointage fermee pour cette seance. Le lecteur reste en attente.")
    elif fenetre == "erreur" or fenetre == "conflit" or fenetre == "sans_groupe":
        st.error(statut.get("message", "Probleme de pointage."))
    else:
        st.info("Lecteur connecte, en attente de la prochaine seance.")

    dernier = statut.get("dernier_resultat")
    if dernier:
        message = f"{dernier.get('heure', '')} — {dernier.get('etudiant') or 'Carte'} : {dernier.get('message', '')}"
        if dernier.get("statut") == "ok":
            st.success(message)
        elif dernier.get("statut") == "deja":
            st.warning(message)
        else:
            st.error(message)


# Rafraichissement du suivi, sans rouvrir le port serie ni bloquer l'interface.
if hasattr(st, "fragment"):
    st.fragment(run_every="2s")(afficher_mode_auto)()
else:
    afficher_mode_auto()


maintenant = datetime.now()
conn = connect()
try:
    seances_actives = pd.read_sql_query("""
        SELECT id AS ID, module AS Module, date AS Date,
               heure_debut AS Debut, heure_fin AS Fin
        FROM seances
        WHERE date = ? AND heure_debut <= ? AND heure_fin > ?
        ORDER BY heure_debut
    """, conn, params=(maintenant.strftime("%Y-%m-%d"),
                      maintenant.strftime("%H:%M"),
                      maintenant.strftime("%H:%M")))
finally:
    conn.close()

st.subheader("Séance actuellement active")
if seances_actives.empty:
    st.info("Aucune séance en cours.")
elif len(seances_actives) > 1:
    st.error("Plusieurs séances actives : vérifiez les horaires.")
else:
    st.dataframe(seances_actives, width="stretch", hide_index=True)

st.subheader("Mode manuel de secours")
auto_actif = lire_statut_auto() is not None
if auto_actif:
    st.caption("Le mode automatique tient le port serie. Le bouton manuel est desactive pour eviter un conflit COM.")

if st.button("Scanner et enregistrer un pointage", key="scan_presence", disabled=auto_actif):
    st.session_state.pop("dernier_pointage", None)
    try:
        with st.spinner("Approchez la carte du lecteur RFID..."):
            uid = lire_uid()
        if uid:
            st.session_state["dernier_pointage"] = enregistrer_pointage(uid)
        else:
            st.session_state["dernier_pointage"] = None
            st.warning("Aucune carte détectée.")
    except Exception as exc:
        # Les erreurs série incluent SerialException.
        st.error(f"Erreur de lecture RFID : {exc}")

resultat = st.session_state.get("dernier_pointage")
if resultat is not None:
    if resultat.statut == "ok":
        st.success(f"{resultat.etudiant} — {resultat.module} (ID {resultat.seance_id}) : {resultat.message}")
    elif resultat.statut == "deja":
        st.warning(f"{resultat.etudiant} — {resultat.module} : {resultat.message}")
    else:
        st.error(resultat.message)

st.caption("Mode AUTO : une carte = une tentative, filtre de groupe et anti-doublon actifs. Le bouton manuel est reserve au secours.")
