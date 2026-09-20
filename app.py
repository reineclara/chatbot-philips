import streamlit as st

import data_layer
from assistant import poser_question

# ── Configuration de la page (DOIT être le premier appel Streamlit) ───────
st.set_page_config(
    page_title="Assistant Philips HPM",
    page_icon="🏥",
    layout="wide"
)

# ── Constantes ─────────────────────────────────────────────────────────────
COULEUR_PRINCIPALE = "#003057"  # bleu marine Philips
COULEUR_ACCENT      = "#0091DA"  # bleu clair Philips
COULEUR_BORDURE     = "#D7E4EC"

QUESTIONS_EXEMPLES = [
    "Combien d'équipements sont couverts au total ?",
    "Quel site a le plus d'équipements non couverts ?",
    "Qu'est-ce qu'un équipement couvert ?",
    "Quels équipements vont sortir de couverture bientôt ?",
]

# ── Style ────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <style>
        html, body, [class*="css"] {{
            font-family: "Segoe UI", -apple-system, BlinkMacSystemFont,
                         "Helvetica Neue", Arial, sans-serif;
        }}

        .stApp {{
            background: linear-gradient(180deg, #F4F7FA 0%, #EDF3F8 100%);
        }}

        #MainMenu, footer, [data-testid="stToolbar"] {{
            visibility: hidden;
        }}

        .stButton > button {{
            border-radius: 20px;
            border: 1px solid {COULEUR_BORDURE};
            background-color: #FFFFFF;
            color: {COULEUR_PRINCIPALE};
            font-size: 0.85rem;
            padding: 8px 18px;
            transition: all 0.15s ease;
            min-height: 64px;
            white-space: normal;
            word-wrap: break-word;
            line-height: 1.25;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
        }}
        .stButton > button:hover {{
            border-color: {COULEUR_ACCENT};
            color: {COULEUR_ACCENT};
            box-shadow: 0 2px 10px rgba(0, 145, 218, 0.18);
        }}

        [data-testid="stChatInput"] {{
            border-radius: 24px;
            border: 1.5px solid {COULEUR_BORDURE};
        }}

        [data-testid="stChatMessage"] {{
            border-radius: 14px;
            box-shadow: 0 1px 4px rgba(0, 48, 87, 0.06);
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Bandeau Philips ────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div style="
        background: linear-gradient(120deg, {COULEUR_PRINCIPALE} 0%, #012B4E 100%);
        padding: 18px 28px;
        border-radius: 14px;
        margin-bottom: 22px;
        box-shadow: 0 4px 18px rgba(0, 48, 87, 0.2);
        display: flex;
        align-items: center;
        gap: 16px;
    ">
        <span style="font-size: 2.1rem;">🩺</span>
        <div>
            <div style="color:white; font-size: 1.5rem; font-weight: 700; letter-spacing: 0.4px;">
                PHILIPS <span style="color:{COULEUR_ACCENT}; font-weight: 400;">— Assistant HPM</span>
            </div>
            <div style="color:#AFC6D9; font-size: 0.88rem; margin-top: 3px;">
                Posez une question sur la couverture de vos équipements médicaux
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Préchargement des données ──────────────────────────────────────────────
@st.cache_resource(show_spinner="Chargement des données Philips HPM...")
def precharger_donnees():
    """Force le chargement de l'Excel dès le démarrage du serveur."""
    return data_layer.charger_donnees()

precharger_donnees()

# ── Initialisation session ─────────────────────────────────────────────────
if "messages_api" not in st.session_state:
    st.session_state.messages_api = []
if "messages_affichage" not in st.session_state:
    st.session_state.messages_affichage = []

# ── Questions fréquentes + nouvelle conversation ───────────────────────────
col_titre, col_bouton = st.columns([5, 1])
with col_titre:
    st.markdown(
        f'<p style="color:{COULEUR_PRINCIPALE}; font-weight:700;">💬 Essayez par exemple :</p>',
        unsafe_allow_html=True,
    )
with col_bouton:
    if st.button("🔄 Nouvelle conversation", use_container_width=True):
        st.session_state.messages_api = []
        st.session_state.messages_affichage = []
        st.rerun()

colonnes = st.columns(len(QUESTIONS_EXEMPLES))
question_bouton = None
for colonne, exemple in zip(colonnes, QUESTIONS_EXEMPLES):
    if colonne.button(exemple, use_container_width=True):
        question_bouton = exemple

st.write("")

# ── Historique des messages ────────────────────────────────────────────────
for i, message in enumerate(st.session_state.messages_affichage):
    avatar = "🩺" if message["role"] == "assistant" else None
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# ── Zone de saisie ─────────────────────────────────────────────────────────
question = st.chat_input("Écris ta question ici...") or question_bouton

if question:
    st.session_state.messages_affichage.append({
        "role": "user",
        "content": question,
        "graphiques": []
    })
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant", avatar="🩺"):
        with st.spinner("Réflexion..."):
            texte, graphiques = poser_question(
                st.session_state.messages_api,
                question
            )
        st.markdown(texte)

    st.session_state.messages_affichage.append({
        "role": "assistant",
        "content": texte,
        "graphiques": graphiques,
    })
