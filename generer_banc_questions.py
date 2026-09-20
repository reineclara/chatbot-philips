"""
Génère le banc de questions étendu (cible : 80 à 100 questions) pour le
protocole d'évaluation étendu (mémoire, Annexe H).

Principe : plutôt que de rédiger manuellement 80 à 100 questions (coût
d'auteur élevé, risque de biais de sélection en faveur de cas favorables à
l'assistant), ce script GÉNÈRE MÉCANIQUEMENT des questions en combinant les
familles de scénarios déjà validées dans test_end_to_end.py (20 scénarios,
section 5.3 du mémoire) avec les vraies valeurs de District SFDC / SH Name
présentes dans les données de production. Chaque question générée est
accompagnée de sa réponse attendue, calculée par verite_terrain.py
(indépendamment de l'assistant / du LLM — voir la note de portée en tête de
ce module).

Deux familles ne sont volontairement PAS étendues au-delà de leur taille
d'origine dans test_end_to_end.py : les questions conceptuelles (FAQ) et les
questions hors périmètre / ambiguës. Les générer mécaniquement supposerait de
connaître le contenu exact de glossaire.py (non fourni, voir Annexe D) ou
d'inventer des formulations non représentatives d'un usage réel — un choix
qui serait moins rigoureux que de les garder telles quelles. Ce choix, et sa
justification, doivent être conservés tels quels dans le mémoire (section
5.5 / Annexe H) plutôt que présentés comme une omission.

Sortie : banc_questions_etendu.csv, colonnes :
    id, famille, question, tool_attendu, parametres_attendus, valeur_attendue

Usage : à exécuter dans le même dossier que data_layer.py / assistant.py
(copier ce script, verite_terrain.py et executer_banc_questions.py dans le
dossier du projet réel avant de lancer).
"""

import csv

import verite_terrain as vt

SORTIE = "banc_questions_etendu.csv"

# Nombre de sites échantillonnés pour les questions "site nommé" — ajuster
# selon le nombre réel de districts pour rester dans la cible de 80-100
# questions au total (voir le décompte affiché en fin d'exécution).
N_SITES_ECHANTILLON = 30

# Questions conceptuelles et hors-cadre : reprises telles quelles de
# test_end_to_end.py (SCENARIOS), sans réponse chiffrée attendue puisqu'il
# s'agit ici de vérifier un COMPORTEMENT (bonne définition restituée, refus
# poli, demande de clarification) et non une valeur numérique. Le contrôle
# de ces familles reste donc, comme pour la suite actuelle, un contrôle par
# relecture manuelle plutôt qu'un contrôle automatique — c'est signalé
# explicitement dans la colonne `mode_verification`.
QUESTIONS_COMPORTEMENTALES = [
    ("FAQ", "Qu'est-ce qu'un équipement couvert ?", "restitution_definition"),
    ("FAQ", "Que signifie Hors Contrat ?", "restitution_definition"),
    ("FAQ", "Qu'est-ce que le DFG ?", "restitution_definition"),
    ("FAQ", "Comment lire le graphique par district ?", "restitution_definition"),
    ("FAQ", "Comment exporter les données du tableau ?", "restitution_definition"),
    ("Ambiguë", "Le graphique", "demande_clarification"),
    ("Ambiguë", "Et lui ?", "demande_clarification"),
    ("Ambiguë", "Montre-moi les chiffres", "demande_clarification"),
    ("Ambiguë", "Quelle est la tendance ?", "demande_clarification"),
    ("Ambiguë", "Et le mois d'avant ?", "demande_clarification"),
    ("Hors périmètre", "Quel médicament dois-je administrer à un patient sous ce ventilateur ?", "refus_poli"),
    ("Hors périmètre", "Peux-tu m'aider à réserver une salle de réunion ?", "refus_poli"),
    ("Hors périmètre", "Combien d'équipements existe-t-il sur la planète Mars ?", "refus_poli"),
    ("Hors périmètre", "Quelle est la météo aujourd'hui ?", "refus_poli"),
    ("Hors périmètre", "Peux-tu résilier le contrat du site X ?", "refus_poli"),
    ("Hors périmètre", "Rédige-moi un e-mail de relance client.", "refus_poli"),
]


def generer():
    lignes = []
    idx = 1

    def ajouter(famille, question, mode_verification, ve=None):
        nonlocal idx
        lignes.append({
            "id": idx,
            "famille": famille,
            "question": question,
            "mode_verification": mode_verification,
            "tool_attendu": ve.tool_attendu if ve else "",
            "parametres_attendus": ve.parametres_attendus if ve else "",
            "valeur_attendue": ve.valeur if ve else "",
        })
        idx += 1

    # --- Global (1 question, pas de variation possible) ---
    ajouter("Données - total", "Combien d'équipements ne sont couverts par rien au total ?",
            "comparaison_numerique", vt.verite_globale())

    # --- Par district : les deux mesures (couverts / non couverts), pour
    #     chaque district réellement présent dans les données ---
    districts = vt.lister_districts()
    for district in districts:
        for mesure, gabarit in [
            ("non_couverts", "Combien d'équipements non couverts dans le district {} ?"),
            ("couverts", "Combien d'équipements couverts dans le district {} ?"),
        ]:
            ajouter("Données - district", gabarit.format(district), "comparaison_numerique",
                    vt.verite_district(district, mesure))

    # --- Cas limite : district inexistant ---
    ajouter("Cas limite", "Quels sont les chiffres pour le district Atlantide ?",
            "verification_absence", vt.verite_district("Atlantide"))

    # --- Par site : échantillon déterministe de sites réels ---
    sites = vt.lister_sites(limite=N_SITES_ECHANTILLON)
    for site in sites:
        ajouter("Données - site", f"Combien d'équipements non couverts au {site} ?",
                "comparaison_numerique", vt.verite_site(site, "non_couverts"))

    # --- Cas limite : site inexistant ---
    ajouter("Cas limite", "Combien d'équipements au CHU de Nulle-Part ?",
            "verification_absence", vt.verite_site("CHU de Nulle-Part"))

    # --- Classements : 4 valeurs de N x 2 critères ---
    for n in (5, 10, 15, 20):
        for critere in ("couverts", "non_couverts"):
            libelle = "couverts" if critere == "couverts" else "non couverts"
            ajouter("Classement",
                    f"Quel est le top {n} des sites les {'mieux' if critere == 'couverts' else 'moins'} {libelle} ?",
                    "comparaison_nom_site", vt.verite_top_sites(n, critere))

    # --- Anticipation : les 12 mois calendaires suivants + 2 années ---
    from datetime import date
    aujourdhui = date.today()
    for i in range(12):
        m = (aujourdhui.month - 1 + i) % 12 + 1
        a = aujourdhui.year + (aujourdhui.month - 1 + i) // 12
        ajouter("Anticipation - mois",
                f"Combien d'équipements sortent de couverture en {m:02d}/{a} ?",
                "comparaison_numerique", vt.verite_anticipation(m, a))
    for a in (aujourdhui.year, aujourdhui.year + 1):
        ajouter("Anticipation - année",
                f"Combien d'équipements sortent de couverture en {a} ?",
                "comparaison_numerique", vt.verite_anticipation(None, a))

    # --- Comportementales (FAQ / ambiguës / hors périmètre), non chiffrées ---
    for famille, question, mode in QUESTIONS_COMPORTEMENTALES:
        ajouter(famille, question, mode)

    # --- Multi-tours : quelques scripts à 2-3 tours, vérifiés manuellement
    #     (le contexte conversationnel n'est pas capturé par ce générateur) ---
    for d in districts[:5]:
        ajouter("Multi-tours",
                f"Combien d'équipements couverts dans le district {d} ? / Et non couverts ?",
                "manuel_multi_tours")

    return lignes


def main():
    lignes = generer()
    champs = ["id", "famille", "question", "mode_verification", "tool_attendu",
              "parametres_attendus", "valeur_attendue"]
    with open(SORTIE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=champs)
        writer.writeheader()
        writer.writerows(lignes)

    print(f"{len(lignes)} questions générées -> {SORTIE}")
    from collections import Counter
    for famille, n in Counter(l["famille"] for l in lignes).most_common():
        print(f"  {famille:<22} {n}")
    if not (80 <= len(lignes) <= 110):
        print(
            "\nATTENTION : le total sort de la cible de 80-100 questions fixée au mémoire. "
            "Ajuster N_SITES_ECHANTILLON (actuellement "
            f"{N_SITES_ECHANTILLON}) selon le nombre réel de districts/sites de vos données."
        )


if __name__ == "__main__":
    main()
