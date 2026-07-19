"""
Jour 5 : system prompt complet + garde-fous conversationnels.

Claude reçoit la question + la liste des tools + un system prompt contenant le
rôle, le ton, le glossaire, et des règles de comportement (jamais de chiffre
sans tool, demander une précision si la question est ambiguë, décliner
poliment si hors périmètre).
"""

import json
import os
import sys

from anthropic import Anthropic
from dotenv import load_dotenv

import data_layer
from glossaire import GLOSSAIRE

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()


def _charger_cle_api() -> str:
    """En local : .env. Sur Streamlit Community Cloud : secrets du dashboard
    (pas de fichier .env là-bas, donc on retombe sur st.secrets)."""
    cle = os.environ.get("ANTHROPIC_API_KEY")
    if cle:
        return cle
    try:
        import streamlit as st
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        raise RuntimeError(
            "ANTHROPIC_API_KEY introuvable (ni dans .env, ni dans st.secrets)."
        )


client = Anthropic(api_key=_charger_cle_api())

MODEL = "claude-sonnet-5"
# Note : `temperature` n'est pas supporté par claude-sonnet-5 (paramètre déprécié
# pour ce modèle) — la fiabilité des chiffres repose sur le tool-calling (règle 1
# du system prompt), pas sur un réglage de température.

SYSTEM_PROMPT = f"""--- RÔLE ---
Tu es l'assistant intégré au dashboard Power BI de suivi des équipements médicaux Philips (HPM). Tes utilisateurs sont des commerciaux, responsables de district et managers, sans formation informatique. Ton rôle est de les aider à comprendre le dashboard et à obtenir les chiffres dont ils ont besoin, jamais de te substituer à un avis médical ou technique sur les équipements eux-mêmes.

--- TON ---
Réponds toujours en français, dans un langage simple et pédagogique, sans jargon informatique inutile. Reste concis : privilégie des réponses courtes et directes, quitte à proposer d'aller plus loin si l'utilisateur le souhaite.

--- RÈGLES ---
1. Pour toute question chiffrée ou sur des données précises (totaux, par district, par site, classements, échéances), utilise TOUJOURS un des tools disponibles. Ne donne jamais un chiffre de mémoire ou inventé — un chiffre non obtenu via un tool ne doit jamais apparaître dans ta réponse.
2. Pour les questions conceptuelles ou d'utilisation du dashboard, base-toi uniquement sur le glossaire ci-dessous. N'invente rien qui n'y figure pas.
3. Si une question est ambiguë ou trop vague pour choisir le bon tool ou la bonne entrée du glossaire (ex: "le graphique", "et lui ?", "montre-moi les chiffres"), ne devine pas : demande une précision à l'utilisateur (quel graphique, quel district, quelle période, etc.).
4. Si une question sort de ton périmètre (question médicale, RH, juridique, ou tout sujet sans rapport avec le dashboard et la couverture des équipements), décline poliment en expliquant que ce n'est pas ton domaine, sans tenter d'y répondre.
5. Si la question porte sur un district, un site ou une période qui n'existe pas dans les données, dis-le clairement plutôt que d'inventer un résultat.

--- GLOSSAIRE ---
{GLOSSAIRE}
--- FIN DU GLOSSAIRE ---
"""

TOOLS = [
    {
        "name": "get_kpis_globaux",
        "description": (
            "Renvoie les KPIs globaux du dashboard de couverture des équipements : "
            "nombre total d'équipements, nombre couverts et non couverts, répartition "
            "par type de couverture (Garantie constructeur, Extension de garantie, "
            "Sous contrat), et nombre de sites hospitaliers 100% hors contrat. "
            "N'accepte aucun paramètre."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_kpis_par_district",
        "description": (
            "Renvoie la répartition des équipements couverts/non couverts par district "
            "commercial SFDC (ex: 'Nord Est', 'Sud Ouest'). Si un district est précisé, "
            "renvoie uniquement ses chiffres ; sinon renvoie tous les districts. À utiliser "
            "pour des questions du type 'combien d'équipements non couverts dans le district "
            "X' ou pour comparer plusieurs districts entre eux."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "district": {
                    "type": "string",
                    "description": (
                        "Nom (ou partie du nom) du district SFDC à filtrer, ex: 'Nord Est'. "
                        "Laisser vide pour obtenir tous les districts."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_kpis_par_site",
        "description": (
            "Renvoie la répartition des équipements couverts/non couverts pour un ou "
            "plusieurs sites hospitaliers (SH Name) déjà identifiés, avec filtre optionnel "
            "par nom de site et/ou par district. À utiliser quand l'utilisateur nomme un "
            "site précis (ex: 'combien d'équipements non couverts au CHU Amiens'). "
            "NE PAS utiliser pour un classement/palmarès (ex: 'quel site a le plus de...') "
            "— utiliser get_top_sites dans ce cas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "site": {
                    "type": "string",
                    "description": (
                        "Nom (ou partie du nom) du site hospitalier à filtrer, ex: 'CHU AMIENS'. "
                        "Laisser vide pour lister tous les sites."
                    ),
                },
                "district": {
                    "type": "string",
                    "description": "Filtrer en plus par district SFDC. Optionnel.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_top_sites",
        "description": (
            "Renvoie le classement (top N) des sites hospitaliers par nombre d'équipements "
            "couverts ou non couverts. À utiliser pour toute question de classement du type "
            "'quel site a le plus d'équipements non couverts', 'top 10 des sites les mieux "
            "couverts', etc. NE PAS utiliser pour les chiffres d'un site déjà nommé par "
            "l'utilisateur — utiliser get_kpis_par_site dans ce cas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {
                    "type": "integer",
                    "description": "Nombre de sites à renvoyer dans le classement. Par défaut 10.",
                },
                "critere": {
                    "type": "string",
                    "enum": ["couverts", "non_couverts"],
                    "description": (
                        "Classer par nombre d'équipements couverts ou non couverts. "
                        "Par défaut 'couverts'."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_anticipation",
        "description": (
            "Renvoie le nombre d'équipements dont la couverture (garantie, extension ou "
            "contrat) arrive à échéance, groupé par mois/année, pour anticiper les sorties "
            "de couverture à venir. Filtre optionnel par mois et/ou année. À utiliser pour "
            "des questions du type 'quels équipements vont sortir de couverture bientôt' ou "
            "'combien d'équipements sortent de couverture en mars 2027'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mois": {"type": "integer", "description": "Mois à filtrer (1-12). Optionnel."},
                "annee": {"type": "integer", "description": "Année à filtrer, ex: 2027. Optionnel."},
            },
            "required": [],
        },
    },
]

# Dispatch table : nom du tool -> fonction Python réelle à appeler.
FONCTIONS_TOOLS = {
    "get_kpis_globaux": data_layer.get_kpis_globaux,
    "get_kpis_par_district": data_layer.get_kpis_par_district,
    "get_kpis_par_site": data_layer.get_kpis_par_site,
    "get_top_sites": data_layer.get_top_sites,
    "get_anticipation": data_layer.get_anticipation,
}


def executer_tool(nom: str, entree: dict) -> dict:
    fonction = FONCTIONS_TOOLS[nom]
    return fonction(**entree)


def poser_question(messages: list, question: str) -> tuple[str, list[dict]]:
    """Ajoute la question à l'historique `messages` (muté en place pour garder
    le contexte multi-tours) et renvoie (réponse en texte, liste des graphiques
    trouvés dans les résultats de tools appelés pendant ce tour)."""
    messages.append({"role": "user", "content": question})
    graphiques = []

    while True:
        reponse = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if reponse.stop_reason != "tool_use":
            texte = next(bloc.text for bloc in reponse.content if bloc.type == "text")
            return texte, graphiques

        messages.append({"role": "assistant", "content": reponse.content})

        resultats_tools = []
        for bloc in reponse.content:
            if bloc.type != "tool_use":
                continue
            print(f"[Outil appelé] {bloc.name}({bloc.input})")
            resultat = executer_tool(bloc.name, bloc.input)
            if "graphique" in resultat:
                graphiques.append(resultat["graphique"])
            resultats_tools.append({
                "type": "tool_result",
                "tool_use_id": bloc.id,
                "content": json.dumps(resultat, ensure_ascii=False, default=str),
            })

        messages.append({"role": "user", "content": resultats_tools})


if __name__ == "__main__":
    questions_test = [
        "Le graphique",
        "Quel médicament dois-je administrer à un patient sous ce ventilateur ?",
        "Combien d'équipements non couverts dans le district Nord Est ?",
    ]
    historique = []
    for question in questions_test:
        print(f"Question : {question}\n")
        texte, graphiques = poser_question(historique, question)
        print(f"Réponse : {texte}")
        if graphiques:
            print(f"[{len(graphiques)} graphique(s) renvoyé(s)]")
        print("\n" + "=" * 80 + "\n")
