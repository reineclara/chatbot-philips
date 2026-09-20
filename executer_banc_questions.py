"""
Score l'Architecture A (les cinq tools fixes de data_layer.py, déjà en
production, orchestrés par assistant.poser_question) sur les questions du
banc étendu (banc_questions_etendu.csv, généré par generer_banc_questions.py)
dont le mode de vérification est automatisable.

Nécessaire pour le protocole H.2 (executer_comparaison_h2.py) : ce dernier a
besoin d'un verdict CORRECT/INCORRECT par question, indépendant de son
propre jugement sur l'Architecture B, pour former le test apparié de
McNemar. Utilise exactement la même fonction scorer() qu'executer_comparaison_h2.py
(import direct, pas de copie) pour que les deux architectures soient jugées
avec la même règle — condition nécessaire pour que le test apparié soit
valide.

Ne score PAS les familles comportementales (FAQ, Ambiguë, Hors périmètre,
Multi-tours) : leur mode_verification n'est pas dans MODES_COMPARABLES
(evaluation par relecture manuelle uniquement, cf. generer_banc_questions.py
et section 5.5 du mémoire).

À EXÉCUTER EN LOCAL, dans le même dossier que assistant.py / data_layer.py,
avec la clé ANTHROPIC_API_KEY (.env). Consomme des appels API payants (un
appel, potentiellement plusieurs tool-calls, par question).

Sortie : resultats_banc_etendu.csv, colonnes : id, verdict, reponse, duree_s

Usage :
    python executer_banc_questions.py               # banc complet
    python executer_banc_questions.py --limite 10    # pilote (coût réduit)
"""

import argparse
import csv
import time

from assistant import poser_question
from executer_comparaison_h2 import MODES_COMPARABLES, scorer

BANC = "banc_questions_etendu.csv"
SORTIE = "resultats_banc_etendu.csv"


def charger_banc_comparable() -> list[dict]:
    with open(BANC, encoding="utf-8") as f:
        return [l for l in csv.DictReader(f) if l["mode_verification"] in MODES_COMPARABLES]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=None,
                         help="Limiter le nombre de questions (pilote à coût réduit)")
    args = parser.parse_args()

    banc = charger_banc_comparable()
    if args.limite:
        banc = banc[: args.limite]
    print(f"{len(banc)} questions à mode de vérification automatisable (Architecture A).")

    resultats = []
    for ligne in banc:
        debut = time.perf_counter()
        try:
            texte, _ = poser_question([], ligne["question"])
        except Exception as e:
            texte = ""
            verdict = "ERREUR"
            print(f"[{ligne['id']:>3}] ERREUR : {e}")
        else:
            verdict = scorer(ligne["mode_verification"], ligne["valeur_attendue"], texte)
        duree = time.perf_counter() - debut

        resultats.append({
            "id": ligne["id"],
            "verdict": verdict,
            "reponse": texte.replace("\n", " ")[:300],
            "duree_s": round(duree, 2),
        })
        print(f"[{ligne['id']:>3}] {verdict:<10} {duree:5.1f}s  {ligne['question'][:60]}")

    with open(SORTIE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "verdict", "reponse", "duree_s"])
        writer.writeheader()
        writer.writerows(resultats)

    nb_correct = sum(1 for r in resultats if r["verdict"] == "CORRECT")
    print(f"\nArchitecture A : {nb_correct}/{len(resultats)} = {nb_correct / len(resultats):.1%} correct")
    print(f"Détail complet -> {SORTIE}")


if __name__ == "__main__":
    main()
