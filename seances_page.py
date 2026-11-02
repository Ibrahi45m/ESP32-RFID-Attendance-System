import streamlit as st
import pandas as pd
import sqlite3
from database import DB_PATH, connect
from couleurs_service import synchroniser_couleurs, nettoyer_couleur_orpheline
from datetime import date, timedelta
import plotly.graph_objects as go

# Titre de la page
st.title("Gestion des seances")
# Actualiser les donnees
st.button(
    "Actualiser la liste des seances",
    key="actualiser_seances"
)
# Message apres enregistrement

# Connexion a SQLite
conn = sqlite3.connect(DB_PATH)

# Recuperer les seances
df_seances = pd.read_sql_query("""
    SELECT
        id AS ID,
        module AS Module,
        date AS Date,
        heure_debut AS Debut,
        heure_fin AS Fin
    FROM seances
    ORDER BY date DESC, heure_debut ASC
""", conn)

conn.close()

# Statistiques
st.metric("Total des seances", len(df_seances))

# Liste des seances
st.subheader("Liste des seances")

st.dataframe(
    df_seances,
    width="stretch",
    hide_index=True
)

# Ajouter une nouvelle seance
st.subheader("Ajouter une seance")

with st.form("form_ajout_seance_page"):

    module = st.text_input("Nom du module")

    date_seance = st.date_input("Date de la seance")

    # Heure de debut
    st.write("Heure de debut")

    col1, col2 = st.columns(2)

    with col1:
        h_debut = st.selectbox(
            "Heures debut",
            range(24),
            index=8,
            format_func=lambda x: f"{x:02d}"
        )

    with col2:
        m_debut = st.selectbox(
            "Minutes debut",
            range(60),
            index=30,
            format_func=lambda x: f"{x:02d}"
        )

    # Heure de fin
    st.write("Heure de fin")

    col3, col4 = st.columns(2)

    with col3:
        h_fin = st.selectbox(
            "Heures fin",
            range(24),
            index=10,
            format_func=lambda x: f"{x:02d}"
        )

    with col4:
        m_fin = st.selectbox(
            "Minutes fin",
            range(60),
            index=30,
            format_func=lambda x: f"{x:02d}"
        )

    submitted = st.form_submit_button(
        "Enregistrer la seance"
    )

# Valider et enregistrer la seance
if submitted:

    module = module.strip()
    date_sql = date_seance.isoformat()

    debut_sql = f"{h_debut:02d}:{m_debut:02d}"
    fin_sql = f"{h_fin:02d}:{m_fin:02d}"

    # Validation
    if not module:
        st.error("Veuillez saisir le nom du module.")

    elif fin_sql <= debut_sql:
        st.error("L'heure de fin doit etre apres l'heure de debut.")

    else:
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
            # Verifier les chevauchements
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
                # Ajouter la seance
                cursor.execute("""
                    INSERT INTO seances
                    (module, date, heure_debut, heure_fin)
                    VALUES (?, ?, ?, ?)
                """, (module, date_sql, debut_sql, fin_sql))

                conn.commit()
                st.success("Seance enregistree avec succes !")
        conn.close()

# Modifier une seance
st.subheader("Modifier une seance")

# Preparer les choix disponibles
options_modification = {}

for _, ligne in df_seances.iterrows():

    label = (
        f"{ligne['Module']} | {ligne['Date']} | "
        f"{ligne['Debut']} - {ligne['Fin']} | ID {ligne['ID']}"
    )

    options_modification[label] = int(ligne["ID"])

# Choisir la seance
if options_modification:

    choix = st.selectbox(
        "Choisir une seance a modifier",
        list(options_modification.keys()),
        key="choix_modification_page"
    )

    id_modification = options_modification[choix]

    # Recuperer les informations de la seance
    ligne_selectionnee = df_seances[
        df_seances["ID"] == id_modification
    ].iloc[0]

    # Afficher les informations
    st.info(f"Seance selectionnee : ID {id_modification}")

    st.write("Module :", ligne_selectionnee["Module"])
    st.write("Date :", ligne_selectionnee["Date"])
    st.write("Debut :", ligne_selectionnee["Debut"])
    st.write("Fin :", ligne_selectionnee["Fin"])

    # Recuperer les horaires actuels
    h_debut_actuel, m_debut_actuel = map(
        int, ligne_selectionnee["Debut"].split(":")
    )

    h_fin_actuel, m_fin_actuel = map(
        int, ligne_selectionnee["Fin"].split(":")
    )

    # Formulaire de modification
    with st.form(f"form_modifier_seance_{id_modification}"):

        nouveau_module = st.text_input(
            "Nouveau nom du module",
            value=ligne_selectionnee["Module"],
            key=f"edit_module_{id_modification}"
        )

        nouvelle_date = st.date_input(
            "Nouvelle date",
            value=date.fromisoformat(ligne_selectionnee["Date"]),
            key=f"edit_date_{id_modification}"
        )

        st.write("Nouvelle heure de debut")

        col1, col2 = st.columns(2)

        with col1:
            h_debut_mod = st.selectbox(
                "Heures debut modification",
                range(24),
                index=h_debut_actuel,
                format_func=lambda x: f"{x:02d}",
                key=f"edit_hd_{id_modification}"
            )

        with col2:
            m_debut_mod = st.selectbox(
                "Minutes debut modification",
                range(60),
                index=m_debut_actuel,
                format_func=lambda x: f"{x:02d}",
                key=f"edit_md_{id_modification}"
            )

        st.write("Nouvelle heure de fin")

        col3, col4 = st.columns(2)

        with col3:
            h_fin_mod = st.selectbox(
                "Heures fin modification",
                range(24),
                index=h_fin_actuel,
                format_func=lambda x: f"{x:02d}",
                key=f"edit_hf_{id_modification}"
            )

        with col4:
            m_fin_mod = st.selectbox(
                "Minutes fin modification",
                range(60),
                index=m_fin_actuel,
                format_func=lambda x: f"{x:02d}",
                key=f"edit_mf_{id_modification}"
            )

        # Confirmation de la seance selectionnee
        confirmation = st.checkbox(
            f"Je confirme la modification de : "
            f"{ligne_selectionnee['Module']} | "
            f"{ligne_selectionnee['Date']} | "
            f"{ligne_selectionnee['Debut']} - "
            f"{ligne_selectionnee['Fin']} | "
            f"ID {id_modification}",
            key=f"confirmation_mod_{id_modification}"
        )

        modifier = st.form_submit_button(
            "Valider la modification"
        )

    # Tester le formulaire

    # Valider et enregistrer la modification
    if modifier and not confirmation:
        st.error("Veuillez confirmer la seance a modifier.")

    elif modifier:

        nouveau_module = nouveau_module.strip()
        date_sql = nouvelle_date.isoformat()

        debut_sql = f"{h_debut_mod:02d}:{m_debut_mod:02d}"
        fin_sql = f"{h_fin_mod:02d}:{m_fin_mod:02d}"

        # Verifier le nom du module
        if not nouveau_module:
            st.error("Veuillez saisir le nom du module.")

        # Verifier les horaires
        elif fin_sql <= debut_sql:
            st.error(
                "L'heure de fin doit etre apres l'heure de debut."
            )

        elif (
            nouveau_module == ligne_selectionnee["Module"]
            and date_sql == ligne_selectionnee["Date"]
            and debut_sql == ligne_selectionnee["Debut"]
            and fin_sql == ligne_selectionnee["Fin"]
        ):
            st.warning("Aucune modification detectee.")

        else:
            conn = connect()
            try:
                # Interdire les changements historiques sur une séance pointée.
                nombre_presences = conn.execute("""
                    SELECT COUNT(*) FROM attendance_seances WHERE seance_id = ?
                """, (id_modification,)).fetchone()[0]

                if nombre_presences:
                    st.error(
                        "Modification refusee : cette seance contient "
                        f"{nombre_presences} pointage(s). "
                        "Conservez l'historique existant."
                    )
                else:
                    conflits = conn.execute("""
                        SELECT module, heure_debut, heure_fin
                        FROM seances
                        WHERE id != ? AND date = ?
                          AND heure_debut < ? AND heure_fin > ?
                    """, (id_modification, date_sql, fin_sql, debut_sql)).fetchall()

                    if conflits:
                        st.error("Modification refusee : chevauchement detecte !")
                        for conflit in conflits:
                            st.warning(
                                f"Seance existante : {conflit[0]} "
                                f"({conflit[1]} - {conflit[2]})"
                            )
                    else:
                        ancien_module = ligne_selectionnee["Module"]
                        with conn:
                            conn.execute("""
                                UPDATE seances
                                SET module = ?, date = ?,
                                    heure_debut = ?, heure_fin = ?
                                WHERE id = ?
                            """, (nouveau_module, date_sql, debut_sql, fin_sql,
                                  id_modification))
                            if nouveau_module != ancien_module:
                                nettoyer_couleur_orpheline(conn, ancien_module)
                        st.success("Seance modifiee avec succes !")
            finally:
                conn.close()

else:
    st.warning("Aucune seance disponible.")


# =====================================
# SUPPRIMER UNE SEANCE
# =====================================

st.divider()
st.subheader("Supprimer une seance")

if options_modification:

    choix_suppression = st.selectbox(
        "Choisir une seance a supprimer",
        list(options_modification.keys()),
        key="choix_suppression"
    )

    id_suppression = options_modification[choix_suppression]

    # Verifier les pointages avant la suppression
    conn_verif = sqlite3.connect(DB_PATH)

    nombre_pointages = conn_verif.execute("""
        SELECT COUNT(*)
        FROM attendance_seances
        WHERE seance_id = ?
    """, (id_suppression,)).fetchone()[0]

    conn_verif.close()

    if nombre_pointages > 0:
        st.error(
            f"Suppression impossible : "
            f"{nombre_pointages} pointage(s) "
            "enregistre(s) pour cette seance."
        )
    else:
        st.info(
            "Aucun pointage enregistre. "
            "Cette seance peut etre supprimee."
        )


    with st.form("form_suppression_seance"):

        st.warning(
            f"Attention : suppression de la seance "
            f"{choix_suppression}"
        )

        confirmation_suppression = st.checkbox(
            "Je confirme la suppression definitive"
        )


        supprimer = st.form_submit_button(
            "Supprimer la seance",
            disabled=nombre_pointages > 0
        )


    if supprimer:

        if not confirmation_suppression:
            st.error("Veuillez confirmer la suppression.")

        else:
            conn = connect()
            conn.execute("BEGIN IMMEDIATE")

            # Verifier les presences liees a la seance
            total_pointages = conn.execute("""
                SELECT COUNT(*)
                FROM attendance_seances
                WHERE seance_id = ?
            """, (id_suppression,)).fetchone()[0]

            if total_pointages > 0:
                conn.rollback()
                st.error(
                    "Suppression refusee : "
                    f"{total_pointages} pointage(s) "
                    "sont lies a cette seance."
                )


            else:
                # Recuperer le module avant la suppression
                ligne_module = conn.execute("""
                    SELECT module
                    FROM seances
                    WHERE id = ?
                """, (id_suppression,)).fetchone()

                if ligne_module is None:
                    conn.rollback()
                    st.error("Seance introuvable.")

                else:
                    module_supprime = ligne_module[0]

                    # Supprimer la seance
                    conn.execute("""
                        DELETE FROM seances
                        WHERE id = ?
                    """, (id_suppression,))

                    # Supprimer la couleur uniquement si
                    # aucune autre seance du module n'existe
                    nettoyer_couleur_orpheline(conn, module_supprime)

                    conn.commit()

                    st.success(
                        f"Seance ID {id_suppression} supprimee ! "
                        "Actualisez la page pour voir "
                        "la liste et le planning mis a jour."
                    )


            conn.close()

else:
    st.info("Aucune seance a supprimer.")

# =====================================
# EMPLOI DU TEMPS HEBDOMADAIRE
# =====================================

st.divider()
st.subheader("Emploi du temps hebdomadaire")

# Choisir une date


# Initialiser le planning avec la date actuelle
if "planning_date" not in st.session_state:
    st.session_state["planning_date"] = date.today()


# Fonction pour changer de semaine
def changer_semaine(nombre_semaines):
    st.session_state["planning_date"] += timedelta(
        weeks=nombre_semaines
    )

# Revenir a la semaine actuelle
def revenir_semaine_actuelle():
    st.session_state["planning_date"] = date.today()

# Boutons de navigation
col_prec, col_actuelle, col_suiv = st.columns(3)

with col_prec:
    st.button(
        "Semaine precedente",
        on_click=changer_semaine,
        args=(-1,),
        use_container_width=True
    )

with col_actuelle:
    st.button(
        "Cette semaine",
        on_click=revenir_semaine_actuelle,
        use_container_width=True
    )

with col_suiv:
    st.button(
        "Semaine suivante",
        on_click=changer_semaine,
        args=(1,),
        use_container_width=True
    )


# Choisir aussi une date manuellement
date_choisie = st.date_input(
    "Choisir une semaine",
    key="planning_date"
)


# Calculer lundi et samedi
lundi = date_choisie - timedelta(
    days=date_choisie.weekday()
)

samedi = lundi + timedelta(days=5)

st.write(
    f"Semaine du {lundi.strftime('%d/%m/%Y')} "
    f"au {samedi.strftime('%d/%m/%Y')}"
)

# Charger les seances de la semaine
conn = sqlite3.connect(DB_PATH)

seances_semaine = conn.execute("""
    SELECT id, module, date, heure_debut, heure_fin
    FROM seances
    WHERE date BETWEEN ? AND ?
    ORDER BY date, heure_debut
""", (
    lundi.isoformat(),
    samedi.isoformat()
)).fetchall()

# Garder les couleurs enregistrées, créer celles des nouveaux modules.
modules_couleurs = synchroniser_couleurs(conn)

conn.close()

st.write(
    "Nombre de seances cette semaine :",
    len(seances_semaine)
)


# =====================================
# AFFICHAGE VISUEL DU PLANNING
# =====================================

st.subheader("Planning visuel")

jours = [
    "Lundi", "Mardi", "Mercredi",
    "Jeudi", "Vendredi", "Samedi"
]

fig = go.Figure()


for seance in seances_semaine:
    id_seance, module, date_seance, debut, fin = seance

    # Position du jour (0 = lundi, 5 = samedi)
    jour_index = date.fromisoformat(date_seance).weekday()

    # Convertir HH:MM en heures decimales
    h_debut, m_debut = map(int, debut.split(":"))
    h_fin, m_fin = map(int, fin.split(":"))

    heure_debut = h_debut + m_debut / 60
    heure_fin = h_fin + m_fin / 60

    # Donner une couleur au module

    # Donner une couleur stable au module
    couleur = modules_couleurs[module]


    # Dessiner le bloc de la seance

    # Dessiner la seance horizontalement
    fig.add_shape(
        type="rect",
        x0=heure_debut,
        x1=heure_fin,
        y0=jour_index - 0.42,
        y1=jour_index + 0.42,
        fillcolor=couleur,
        line=dict(color=couleur)
    )

    # Ajouter le texte dans le bloc

    # Calculer la duree en minutes
    duree = round((heure_fin - heure_debut) * 60)

    # Adapter le texte selon la duree
    if duree >= 60:
        texte_seance = f"<b>{module}</b><br>{debut} - {fin}"
        taille_texte = 13

    elif duree >= 30:
        texte_seance = f"<b>{module}</b>"
        taille_texte = 11



    else:
        texte_seance = None

        # Afficher le nom a droite des seances courtes
        fig.add_annotation(
            x=heure_fin + 0.1,
            y=jour_index,
            text=f"<b>{module}</b>",
            showarrow=False,
            xanchor="left",
            font=dict(
                color="white",
                size=11
            ),
            bgcolor="rgba(0,0,0,0.75)",
            borderpad=4
        )

    # Afficher le texte dans la seance
    if texte_seance is not None:
        fig.add_annotation(
            x=(heure_debut + heure_fin) / 2,
            y=jour_index,
            text=texte_seance,
            showarrow=False,
            font=dict(
                color="white",
                size=taille_texte
            ),
            bgcolor="rgba(0,0,0,0.55)",
            borderpad=4,
            align="center"
        )

    # Point interactif au centre de la seance
    fig.add_trace(
        go.Scatter(
            x=[(heure_debut + heure_fin) / 2],
            y=[jour_index],
            customdata=[[id_seance]],
            mode="markers",
            marker=dict(
                size=45,
                color="rgba(255,255,255,0.01)"
            ),
            hovertemplate=(
                f"<b>{module}</b><br>"
                f"ID : {id_seance}<br>"
                f"Date : {date_seance}<br>"
                f"Horaire : {debut} - {fin}"
                "<extra></extra>"
            ),
            showlegend=False
        )
    )

# Legende des modules de la semaine
modules_semaine = sorted({
    seance[1] for seance in seances_semaine
})

for nom_module in modules_semaine:
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(
                size=12,
                color=modules_couleurs[nom_module]
            ),
            name=nom_module,
            showlegend=True,
            hoverinfo="skip"
        )
    )

# Configurer les axes

# Axe X : les heures

# Adapter les horaires automatiquement
heure_min = 8
heure_max = 20

for seance in seances_semaine:
    debut = seance[3]
    fin = seance[4]

    h_debut, m_debut = map(int, debut.split(":"))
    h_fin, m_fin = map(int, fin.split(":"))

    debut_decimal = h_debut + m_debut / 60
    fin_decimal = h_fin + m_fin / 60

    heure_min = min(heure_min, int(debut_decimal))
    heure_max = max(
        heure_max,
        min(24, int(fin_decimal) + 1)
    )

# Axe X : horaires adaptes
fig.update_xaxes(
    tickvals=list(range(heure_min, heure_max + 1)),
    ticktext=[
        f"{h:02d}:00"
        for h in range(heure_min, heure_max + 1)
    ],
    range=[heure_min, heure_max],
    side="top",
    showgrid=True,
    title="Heure"
)


# Axe Y : les jours
fig.update_yaxes(
    tickvals=list(range(6)),
    ticktext=[
        f"{jours[i]} - "
        f"{(lundi + timedelta(days=i)).strftime('%d/%m')}"
        for i in range(6)
    ],
    range=[5.5, -0.5],
    showgrid=True,
    title="Jour"
)

fig.update_layout(
    height=550,
    margin=dict(l=40, r=20, t=40, b=90),
    showlegend=True,
    legend=dict(
        orientation="h",
        yanchor="top",
        y=-0.08,
        xanchor="left",
        x=0
    )
)

# Activer la selection des seances
event = st.plotly_chart(
    fig,
    width="stretch",
    key="planning_selection",
    on_select="rerun",
    selection_mode="points"
)

# Recuperer la seance selectionnee
points = event.selection.points


if points:
    id_selectionne = int(points[0]["customdata"][0])

    st.success(
        f"Seance selectionnee : ID {id_selectionne}"
    )

    # Retrouver le choix correspondant dans le formulaire
    label_selectionne = next(
        (
            label
            for label, id_option in options_modification.items()
            if id_option == id_selectionne
        ),
        None
    )

    if label_selectionne:

        # Executer avant le prochain affichage du formulaire
        def charger_seance(label):
            st.session_state["choix_modification_page"] = label

        st.button(
            "Charger dans Modifier une seance",
            key="charger_depuis_planning",
            on_click=charger_seance,
            args=(label_selectionne,)
        )

        st.markdown(
            "[⬆️ Aller au formulaire de modification](#modifier-une-seance)"
        )

        # Charger la seance dans le formulaire de suppression
        def charger_suppression(label):
            st.session_state["choix_suppression"] = label

        st.button(
            "Supprimer cette seance",
            key="supprimer_depuis_planning",
            on_click=charger_suppression,
            args=(label_selectionne,),
            type="secondary"
        )

        st.markdown(
            "[Aller au formulaire de suppression](#supprimer-une-seance)"
        )



    else:
        st.warning("Seance introuvable dans le formulaire.")
