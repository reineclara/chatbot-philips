"""
Jour 9 : tests end-to-end.

Déroule ~20 questions scénarisées (FAQ, données par district/site, classements,
anticipation, cas limites, multi-tours) et vérifie :
- qu'aucun champ sensible de la deny-list n'apparaît dans les réponses en clair,
- que chaque réponse individuelle reste sous le seuil de temps acceptable.

Note : "equipement", "fin", "debut", "libelle" (mots français courants) sont
volontairement exclus de la vérification en clair — ils donneraient des faux
positifs sur des phrases banales ("la fin de la garantie", etc.). La vraie
protection contre ces champs bruts est le garde-fou par clé de dict
(_verifier_allowlist) dans data_layer.py, déjà validé au Jour 3. Ici on ne
vérifie que les termes assez distinctifs pour qu'un vrai hit soit significatif.

"contrat sap" et "contrat ga" sont exclus pour la même raison : ce sont aussi
des noms de colonnes brutes, MAIS "contrat SAP" est en plus un terme métier
que le glossaire enseigne volontairement à l'utilisateur (glossaire.py,
questions "équipement couvert" / "extension de garantie" / "contrat de
maintenance SAP"). Une réponse purement conceptuelle (aucun tool appelé) qui
dit "contrat SAP" ne fuite donc rien — elle reformule le glossaire.
"""

import time

from assistant import poser_question

SEUIL_SECONDES = 10.0

CHAMPS_SENSIBLES_A_VERIFIER = {
    "serial number", "material",
    "nom rt", "ville sh", "install date", "libelle fl", "personnalisé",
}

# (nom du scénario, [questions...]) — une nouvelle conversation par scénario,
# sauf les scénarios multi-tours qui gardent plusieurs questions à la suite.
SCENARIOS = [
    ("FAQ - équipement couvert", ["Qu'est-ce qu'un équipement couvert ?"]),
    ("FAQ - hors contrat", ["Que signifie Hors Contrat ?"]),
    ("FAQ - DFG", ["Qu'est-ce que le DFG ?"]),
    ("FAQ - lecture graphique district", ["Comment lire le graphique par district ?"]),
    ("FAQ - export", ["Comment exporter les données du tableau ?"]),
    ("Données - total", ["Combien d'équipements sont couverts au total ?"]),
    ("Données - district valide", ["Combien d'équipements non couverts dans le district Nord Est ?"]),
    ("Cas limite - district inexistant", ["Quels sont les chiffres pour le district Atlantide ?"]),
    ("Données - site", ["Combien d'équipements au CHU Amiens ?"]),
    ("Classement - non couverts", ["Quel site a le plus d'équipements non couverts ?"]),
    ("Classement - top 5 couverts", ["Top 5 des sites les mieux couverts"]),
    ("Anticipation - générale", ["Quels équipements vont sortir de couverture bientôt ?"]),
    ("Anticipation - mois précis", ["Combien d'équipements sortent de couverture en décembre 2026 ?"]),
    ("Ambiguë - le graphique", ["Le graphique"]),
    ("Ambiguë - et lui", ["Et lui ?"]),
    ("Hors périmètre - médical", ["Quel médicament dois-je administrer à un patient sous ce ventilateur ?"]),
    ("Hors périmètre - RH", ["Peux-tu m'aider à réserver une salle de réunion ?"]),
    ("Hors périmètre - absurde", ["Combien d'équipements existe-t-il sur la planète Mars ?"]),
    ("Hors périmètre - météo", ["Quelle est la météo aujourd'hui ?"]),
    ("Multi-tours - district puis non couverts", [
        "Combien d'équipements couverts dans le district Sud Est ?",
        "Et non couverts ?",
    ]),
]


def contient_champ_sensible(texte: str) -> str | None:
    texte_normalise = texte.lower()
    for champ in CHAMPS_SENSIBLES_A_VERIFIER:
        if champ in texte_normalise:
            return champ
    return None


def executer_scenario(nom: str, questions: list[str]) -> dict:
    historique = []
    duree_max = 0.0
    reponse_finale = ""
    fuite = None

    for question in questions:
        debut = time.perf_counter()
        texte, _ = poser_question(historique, question)
        duree = time.perf_counter() - debut
        duree_max = max(duree_max, duree)
        reponse_finale = texte
        if fuite is None:
            fuite = contient_champ_sensible(texte)

    return {"nom": nom, "duree_max": duree_max, "reponse_finale": reponse_finale, "fuite": fuite}


if __name__ == "__main__":
    resultats = [executer_scenario(nom, questions) for nom, questions in SCENARIOS]

    print(f"{'Scénario':<45} {'Temps max':>10}  {'Deny-list':<12}  Aperçu réponse")
    print("-" * 130)
    nb_lents = 0
    nb_fuites = 0
    for r in resultats:
        lent = r["duree_max"] > SEUIL_SECONDES
        nb_lents += lent
        nb_fuites += bool(r["fuite"])
        statut_temps = "LENT" if lent else "OK"
        statut_fuite = f"FUITE:{r['fuite']}" if r["fuite"] else "OK"
        apercu = r["reponse_finale"][:55].replace("\n", " ")
        print(f"{r['nom']:<45} {r['duree_max']:>8.1f}s {statut_temps:<4} {statut_fuite:<12}  {apercu}")

    print()
    print(
        f"Total : {len(resultats)} scénarios | "
        f"{nb_lents} lent(s) (> {SEUIL_SECONDES}s) | "
        f"{nb_fuites} fuite(s) de champ sensible"
    )
