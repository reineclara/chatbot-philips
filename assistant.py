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
from datetime import date

from anthropic import Anthropic
from dotenv import load_dotenv

import data_layer
from glossaire import GLOSSAIRE

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL = "claude-sonnet-5"
# Note : `temperature` n'est pas supporté par claude-sonnet-5 (paramètre déprécié
# pour ce modèle) — la fiabilité des chiffres repose sur le tool-calling (règle 1
# du system prompt), pas sur un réglage de température.

MOIS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def construire_system_prompt() -> str:
    """Reconstruit le system prompt à chaque appel pour que la date du jour
    (utilisée pour résoudre des expressions relatives comme "ce mois-ci" ou
    "l'année prochaine" en mois/année à passer à get_anticipation) reste
    toujours exacte, y compris si le processus tourne plusieurs jours."""
    aujourdhui = date.today()
    date_str = f"{aujourdhui.day} {MOIS_FR[aujourdhui.month - 1]} {aujourdhui.year}"
    return f"""--- RÔLE ---
Tu es l'assistant intégré au dashboard Power BI de suivi des équipements médicaux Philips (HPM). Tes utilisateurs sont des commerciaux, responsables de district et managers, sans formation informatique. Ton rôle est de les aider à comprendre le dashboard et à obtenir les chiffres dont ils ont besoin, jamais de te substituer à un avis médical ou technique sur les équipements eux-mêmes.

--- DATE DU JOUR ---
Nous sommes le {date_str}. Utilise cette date pour résoudre toute référence temporelle relative dans les questions de l'utilisateur ("ce mois-ci", "le mois prochain", "cette année", "d'ici 3 mois", etc.) en mois/année précis avant d'appeler un tool. Ne demande jamais à l'utilisateur la date du jour ni de préciser une période déjà déductible de cette date.

--- TON ---
Réponds toujours en français, dans un langage simple et pédagogique, sans jargon informatique inutile. Reste concis : privilégie des réponses courtes et directes, quitte à proposer d'aller plus loin si l'utilisateur le souhaite.

--- RÈGLES ---
1. Pour toute question chiffrée ou sur des données précises (totaux, par district, par site, classements, échéances), utilise TOUJOURS un des tools disponibles. Ne donne jamais un chiffre de mémoire ou inventé — un chiffre non obtenu via un tool ne doit jamais apparaître dans ta réponse.
2. Pour les questions conceptuelles ou d'utilisation du dashboard, base-toi uniquement sur le glossaire ci-dessous. N'invente rien qui n'y figure pas.
3. Si une question est ambiguë ou trop vague pour choisir le bon tool ou la bonne entrée du glossaire (ex: "le graphique", "et lui ?", "montre-moi les chiffres"), ne devine pas : demande une précision à l'utilisateur (quel graphique, quel district, quelle période, etc.).
4. Si une question sort de ton périmètre (question médicale, RH, juridique, ou tout sujet sans rapport avec le dashboard et la couverture des équipements), décline poliment en expliquant que ce n'est pas ton domaine, sans tenter d'y répondre.
5. Si la question porte sur un district, un site ou une période qui n'existe pas dans les données, dis-le clairement plutôt que d'inventer un résultat.
6. Réponds UNIQUEMENT à la question posée dans ce tour, rien d'autre. Même si l'historique de la conversation contient des questions et réponses précédentes, ne les récapitule JAMAIS spontanément dans ta réponse — l'utilisateur les a déjà vues, les répéter est une erreur. N'inclus une information d'un tour précédent que si l'utilisateur la redemande explicitement (ex: "et pour le précédent ?").
   Exemple concret à ne PAS reproduire : l'utilisateur demande d'abord "Combien d'équipements à ADOPS 14 ?", tu réponds, puis il demande "Combien d'équipements à AEC SAS ?" — ta réponse à cette deuxième question ne doit mentionner QUE AEC SAS. Ne commence surtout pas par "ADOPS 14 : ..." avant de parler d'AEC SAS.

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
            "de couverture à venir. Filtres optionnels par mois, année, site hospitalier "
            "et/ou district commercial (cumulables). À utiliser pour des questions du type "
            "'quels équipements vont sortir de couverture bientôt', 'combien d'équipements "
            "sortent de couverture en mars 2027', ou 'combien d'équipements sortent de "
            "couverture en janvier 2027 au CHU Amiens'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mois": {"type": "integer", "description": "Mois à filtrer (1-12). Optionnel."},
                "annee": {"type": "integer", "description": "Année à filtrer, ex: 2027. Optionnel."},
                "site": {
                    "type": "string",
                    "description": (
                        "Nom (ou partie du nom) du site hospitalier à filtrer, ex: 'CHU AMIENS'. "
                        "Optionnel."
                    ),
                },
                "district": {
                    "type": "string",
                    "description": "Nom (ou partie du nom) du district SFDC à filtrer, ex: 'Nord Est'. Optionnel.",
                },
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
            system=construire_system_prompt(),
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
