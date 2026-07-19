"""
Jour 7 : graphiques Plotly + branding Philips.

Reprend la boucle de tool-calling de assistant.py. Quand un résultat de tool
contient une clé "graphique", on la convertit en figure Plotly (bar pour un
graphique simple, bar_groupe pour une comparaison couverts/non couverts par
catégorie) et on l'affiche sous la réponse texte.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

import data_layer
from assistant import poser_question

COULEUR_PRINCIPALE = "#003057"  # bleu marine Philips
COULEUR_ACCENT = "#0091DA"      # bleu clair Philips

QUESTIONS_EXEMPLES = [
    "Combien d'équipements sont couverts au total ?",
    "Quel site a le plus d'équipements non couverts ?",
    "Qu'est-ce qu'un équipement couvert ?",
    "Quels équipements vont sortir de couverture bientôt ?",
]

st.set_page_config(page_title="Assistant Philips HPM", page_icon="💬", layout="centered")

# Bandeau façon dashboard Philips (logo texte en attendant un vrai fichier logo à intégrer).
st.markdown(
    f"""
    <div style="background-color:{COULEUR_PRINCIPALE}; padding: 16px 24px; border-radius: 8px; margin-bottom: 16px;">
        <span style="color:white; font-size: 1.4rem; font-weight: 700; letter-spacing: 1px;">PHILIPS</span>
        <span style="color:{COULEUR_ACCENT}; font-size: 1.1rem; margin-left: 12px;">Assistant HPM</span>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("Pose une question sur le dashboard de couverture des équipements.")


@st.cache_resource(show_spinner="Chargement des données Philips HPM...")
def precharger_donnees():
    """Force le chargement/traitement de l'Excel dès le démarrage du serveur,
    plutôt que de le faire au moment de la première question d'un utilisateur
    (sinon la première question de la journée prend ~40s au lieu de quelques
    secondes). st.cache_resource garantit un seul appel pour tout le process,
    partagé entre toutes les sessions."""
    return data_layer.charger_donnees()


precharger_donnees()


def construire_figure(graphique: dict):
    """Convertit un dict 'graphique' renvoyé par un tool en figure Plotly."""
    titre = graphique.get("titre", "")

    if graphique["type"] == "bar":
        fig = px.bar(
            x=graphique["labels"],
            y=graphique["valeurs"],
            title=titre,
            labels={"x": "", "y": "Équipements"},
            color_discrete_sequence=[COULEUR_PRINCIPALE],
        )
    elif graphique["type"] == "bar_groupe":
        lignes = [
            {"Catégorie": label, "Série": serie, "Valeur": valeur}
            for serie, valeurs in graphique["series"].items()
            for label, valeur in zip(graphique["labels"], valeurs)
        ]
        fig = px.bar(
            pd.DataFrame(lignes),
            x="Catégorie",
            y="Valeur",
            color="Série",
            barmode="group",
            title=titre,
            color_discrete_map={"Couverts": COULEUR_ACCENT, "Non couverts": COULEUR_PRINCIPALE},
        )
    else:
        return None

    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        font_color=COULEUR_PRINCIPALE,
        margin=dict(t=50, l=10, r=10, b=10),
    )
    return fig


if "messages_api" not in st.session_state:
    st.session_state.messages_api = []
if "messages_affichage" not in st.session_state:
    st.session_state.messages_affichage = []

st.markdown("**Questions fréquentes**")
colonnes = st.columns(len(QUESTIONS_EXEMPLES))
question_bouton = None
for colonne, exemple in zip(colonnes, QUESTIONS_EXEMPLES):
    if colonne.button(exemple, use_container_width=True):
        question_bouton = exemple

for i, message in enumerate(st.session_state.messages_affichage):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        for j, graphique in enumerate(message.get("graphiques", [])):
            fig = construire_figure(graphique)
            if fig:
                st.plotly_chart(fig, use_container_width=True, key=f"graphique-{i}-{j}")

question = st.chat_input("Écris ta question ici...") or question_bouton

if question:
    st.session_state.messages_affichage.append({"role": "user", "content": question, "graphiques": []})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Réflexion..."):
            texte, graphiques = poser_question(st.session_state.messages_api, question)
        st.markdown(texte)
        for j, graphique in enumerate(graphiques):
            fig = construire_figure(graphique)
            if fig:
                st.plotly_chart(fig, use_container_width=True, key=f"graphique-nouveau-{j}")

    st.session_state.messages_affichage.append({"role": "assistant", "content": texte, "graphiques": graphiques})
