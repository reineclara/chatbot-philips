"""
Protocole H.2 : comparaison chiffrée à une architecture alternative
(génération de requêtes dynamiques, paradigme text-to-SQL / pandas — voir
Annexe H.2 et section 2.3.1 du mémoire), sur le même banc de questions que
le volet H.1 (banc_questions_etendu.csv), pour permettre un test apparié
(McNemar) entre les deux architectures.

À EXÉCUTER EN LOCAL, sur la machine où se trouvent Base_HPM_2026 Q2.xlsx,
modeles.xlsx et la clé ANTHROPIC_API_KEY (fichier .env) — jamais dans un
environnement où ces éléments ne se trouvent pas déjà légitimement.
Ce script consomme des appels API payants (un appel par question du banc).

Principe de l'architecture comparée ("Architecture B") :
---------------------------------------------------------
Au lieu des cinq tools fixes de data_layer.py (Architecture A, déjà en
production), le LLM reçoit le schéma d'un DataFrame pandas et doit écrire
LUI-MÊME, en une seule expression, le calcul pandas qui répond à la
question. Cette expression est exécutée dans un environnement restreint
(sans __builtins__, sans import, avec une liste blanche de colonnes) et son
résultat est comparé à la même vérité terrain que celle utilisée pour
l'Architecture A (verite_terrain.py), donc à un jeu de questions commun.

Point méthodologique à ne pas passer sous silence dans le mémoire :
---------------------------------------------------------------------
Le DataFrame transmis au LLM est filtré en amont sur la liste noire
CHAMPS_INTERDITS de data_layer.py, pour rester une comparaison honnête
plutôt qu'un procès à charge de l'architecture alternative. Mais ce
filtrage est une mitigation appliquée UNE FOIS avant l'exécution, alors que
data_layer.py applique son garde-fou (_verifier_allowlist) au moment même
de la sortie de CHAQUE tool, quelle que soit la question posée. Rien
n'empêche structurellement, dans l'Architecture B, un prompt suffisamment
retors de faire écrire au LLM une expression qui recompose une colonne
interdite à partir d'une colonne autorisée avant de l'inclure dans une
réponse en prose. C'est une différence d'architecture, pas un simple détail
d'implémentation : à documenter telle quelle dans la discussion du
résultat, plutôt que présentée comme un détail secondaire.

Entrées attendues (dans le même dossier) :
    - data_layer.py, assistant.py (déjà en place pour l'architecture A)
    - banc_questions_etendu.csv (généré par generer_banc_questions.py pour H.1)
    - verite_terrain.py (déjà en place)
    - un fichier donnant le verdict CORRECT/INCORRECT de l'Architecture A par
      question : resultats_banc_etendu.csv (si vous avez fait tourner
      executer_banc_questions.py) OU grille_scoring_100_questions.xlsx
      complétée (si le volet H.1 a été dépouillé manuellement, colonne
      "Correct ?", ce qui est le cas documenté en section 5.3.1 du mémoire)

Sorties :
    - resultats_comparaison_h2.csv : un résultat détaillé par question,
      les deux architectures côte à côte
    - un résumé imprimé en console : table de contingence appariée, test de
      McNemar, taux de requêtes invalides (Architecture B), latences
      comparées, jetons consommés par requête (Architecture B) — à reporter
      tels quels dans le mémoire (section 5.3.2 / Annexe H.2), avec le coût
      par requête calculé à partir de la tarification publique en vigueur
      au moment de l'exécution (ne pas recopier une estimation ancienne).

Usage :
    python executer_comparaison_h2.py               # banc complet
    python executer_comparaison_h2.py --limite 10    # pilote (coût réduit)
"""

import argparse
import csv
import io
import os
import re
import time
from contextlib import redirect_stdout
from math import sqrt

import pandas as pd
from anthropic import Anthropic
from dotenv import load_dotenv

import data_layer

load_dotenv()

BANC = "banc_questions_etendu.csv"
RESULTATS_A_CSV = "resultats_banc_etendu.csv"
GRILLE_A_XLSX = "grille_scoring_100_questions.xlsx"
SORTIE = "resultats_comparaison_h2.csv"

MODEL = "claude-sonnet-5"  # même modèle que assistant.py : seule
                           # l'architecture varie, pas le modèle sous-jacent

RE_NOMBRE = re.compile(r"\d[\d\s]*\d|\d")

# Uniquement les modes du banc H.1 scorables automatiquement des deux côtés
# (les familles comportementales — FAQ, ambiguës, hors périmètre,
# multi-tours — supposent un glossaire et une gestion du dialogue qu'un
# simple générateur de requêtes n'a, par construction, aucune raison de
# posséder ; les comparer serait comparer deux choses différentes, pas la
# même chose par deux moyens différents).
MODES_COMPARABLES = {"comparaison_numerique", "comparaison_nom_site", "verification_absence"}

# Instructions données au LLM de l'Architecture B. Les colonnes disponibles
# sont injectées dynamiquement (colonnes_autorisees, voir main()) : le LLM
# ne voit jamais les colonnes de CHAMPS_INTERDITS.
SYSTEM_PROMPT_TEXT_TO_PANDAS = """Tu convertis une question en français en UNE SEULE expression pandas.

Un DataFrame nommé `df` est disponible, avec ces colonnes : {colonnes}
Valeurs possibles de la colonne "Couverture" : "Sous contrat", "Extension de garantie", "Garantie constructeur", "Non couvert".

Règles strictes :
1. Réponds UNIQUEMENT avec l'expression pandas, sur une seule ligne, sans texte autour, sans balises de code, sans commentaire.
2. N'utilise que `df` et `pd` (pandas déjà importé). Aucun import, aucun accès fichier/réseau, aucun appel à des fonctions commençant par "_".
3. Pour un total ou un compte, utilise .nunique() sur la colonne "Equipement" quand c'est pertinent (un équipement peut apparaître sur plusieurs lignes).
4. Si la question porte sur un district ou un site qui n'existe pas dans les données, écris une expression qui renvoie un résultat vide ou 0 (ex: filtrage qui ne matchera rien) plutôt que d'inventer une valeur.
5. Pour un classement (top N), renvoie une Series ou un DataFrame trié, pas juste un nom.

Exemple : "Combien d'équipements non couverts dans le district Nord Est ?"
Réponse : df[(df["District SFDC"].str.upper().str.contains("NORD EST", na=False)) & (df["Couverture"] == "Non couvert")]["Equipement"].nunique()
"""


def colonnes_autorisees(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.strip().lower() not in data_layer.CHAMPS_INTERDITS]


def code_suspect(code: str) -> str | None:
    """Vérification défensive avant exécution (le code vient du LLM, pas
    d'une entrée utilisateur directe, mais l'hygiène reste la même)."""
    motifs_interdits = [
        "import", "open(", "exec(", "eval(", "__", "os.", "sys.", "subprocess",
        ".to_csv", ".to_excel", ".to_pickle", "input(", "globals(", "locals(",
    ]
    bas = code.lower()
    for motif in motifs_interdits:
        if motif in bas:
            return motif
    return None


def executer_pandas_genere(code: str, df_autorise: pd.DataFrame):
    """Exécute l'expression générée dans un environnement restreint.
    Lève une exception si le code est invalide ou l'exécution échoue —
    c'est volontaire : ces cas comptent comme des requêtes invalides."""
    suspect = code_suspect(code)
    if suspect:
        raise ValueError(f"motif interdit détecté dans le code généré : '{suspect}'")
    environnement_global = {
        "__builtins__": {
            "len": len, "sum": sum, "min": min, "max": max, "abs": abs,
            "round": round, "sorted": sorted, "list": list, "dict": dict,
            "str": str, "int": int, "float": float, "True": True, "False": False,
        }
    }
    environnement_local = {"df": df_autorise, "pd": pd}
    return eval(code, environnement_global, environnement_local)  # noqa: S307 (restreint volontairement)


def resultat_vers_texte(resultat) -> str:
    if isinstance(resultat, pd.Series):
        return "; ".join(f"{i} : {v}" for i, v in resultat.items())
    if isinstance(resultat, pd.DataFrame):
        return resultat.to_string()
    return str(resultat)


def scorer(mode: str, valeur_attendue: str, texte_resultat: str) -> str:
    if mode == "comparaison_numerique":
        attendu = str(valeur_attendue).replace(" ", "").replace("\xa0", "")
        trouves = [n.replace(" ", "").replace("\xa0", "") for n in RE_NOMBRE.findall(texte_resultat)]
        return "CORRECT" if attendu in trouves else "INCORRECT"
    if mode == "comparaison_nom_site":
        attendu = str(valeur_attendue).strip().lower()
        return "CORRECT" if attendu and attendu in texte_resultat.lower() else "INCORRECT"
    if mode == "verification_absence":
        vide = texte_resultat.strip() in ("", "0", "[]", "{}", "None") or not RE_NOMBRE.search(texte_resultat)
        return "CORRECT" if vide else "INCORRECT"
    return "A_RELIRE"


def charger_banc() -> list[dict]:
    with open(BANC, encoding="utf-8") as f:
        return [l for l in csv.DictReader(f) if l["mode_verification"] in MODES_COMPARABLES]


def charger_verdicts_architecture_a(ids_attendus: set) -> dict:
    """Renvoie {id: 'CORRECT'|'INCORRECT'} pour l'Architecture A (les cinq
    tools fixes, déjà en production), à partir de la première source
    disponible. Les deux sources sont acceptées car le volet H.1 a été
    dépouillé manuellement (grille Excel), pas via executer_banc_questions.py
    (voir section 5.3.1 et Annexe H.4 du mémoire) — mais le script accepte
    aussi ce second format si vous l'avez généré par ailleurs."""
    if os.path.exists(RESULTATS_A_CSV):
        with open(RESULTATS_A_CSV, encoding="utf-8") as f:
            lignes = list(csv.DictReader(f))
        return {l["id"]: l["verdict"] for l in lignes if l["id"] in ids_attendus}

    if os.path.exists(GRILLE_A_XLSX):
        import openpyxl
        wb = openpyxl.load_workbook(GRILLE_A_XLSX, data_only=True)
        ws = wb.active
        entetes = [str(c.value or "").strip() for c in next(ws.iter_rows(min_row=1, max_row=1))]
        col_id = entetes.index("N°")
        col_verdict = next(i for i, e in enumerate(entetes) if e.startswith("Correct ?"))
        verdicts = {}
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[col_id] is None:
                continue
            id_ligne = str(int(row[col_id]))
            brut = str(row[col_verdict] or "").strip().upper()
            if brut in ("CORRECT", "INCORRECT"):
                verdicts[id_ligne] = brut
        return {k: v for k, v in verdicts.items() if k in ids_attendus}

    raise FileNotFoundError(
        f"Ni {RESULTATS_A_CSV} ni {GRILLE_A_XLSX} trouvé dans ce dossier. "
        "Il faut le verdict CORRECT/INCORRECT de l'Architecture A (déjà en "
        "production) par question pour faire un test apparié — copiez ici "
        "votre grille_scoring_100_questions.xlsx complétée (celle utilisée "
        "pour la section 5.3.1 du mémoire)."
    )


def mcnemar(a_correct_b_correct: int, a_correct_b_incorrect: int,
            a_incorrect_b_correct: int, a_incorrect_b_incorrect: int) -> tuple[float, float]:
    """Test de McNemar avec correction de continuité. Renvoie (statistique, p).
    N'utilise que le calcul en forme fermée (chi2 à 1 ddl) pour éviter une
    dépendance supplémentaire à statsmodels ; scipy (déjà utilisé ailleurs
    dans le protocole étendu pour Wilcoxon) fournit la loi du chi2."""
    from scipy.stats import chi2
    b = a_correct_b_incorrect
    c = a_incorrect_b_correct
    n_discordant = b + c
    if n_discordant == 0:
        return 0.0, 1.0
    stat = (abs(b - c) - 1) ** 2 / n_discordant
    p = 1 - chi2.cdf(stat, df=1)
    return stat, p


def percentile(valeurs: list[float], p: float) -> float:
    if not valeurs:
        return 0.0
    s = sorted(valeurs)
    k = (len(s) - 1) * p
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=None,
                         help="Limiter le nombre de questions (pilote à coût réduit)")
    args = parser.parse_args()

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    banc = charger_banc()
    if args.limite:
        banc = banc[: args.limite]
    ids_banc = {l["id"] for l in banc}

    verdicts_a = charger_verdicts_architecture_a(ids_banc)
    banc = [l for l in banc if l["id"] in verdicts_a]  # jeu de questions commun strict
    print(f"{len(banc)} questions communes aux deux architectures (sur {len(ids_banc)} candidates du banc).")

    df = data_layer.charger_donnees()
    df_autorise = df[colonnes_autorisees(df)].copy()
    colonnes_txt = ", ".join(f'"{c}"' for c in df_autorise.columns)
    system_prompt = SYSTEM_PROMPT_TEXT_TO_PANDAS.format(colonnes=colonnes_txt)

    resultats = []
    for ligne in banc:
        debut = time.perf_counter()
        code_genere, in_tok, out_tok, erreur_llm = None, 0, 0, None
        try:
            reponse = client.messages.create(
                model=MODEL,
                max_tokens=300,
                system=system_prompt,
                messages=[{"role": "user", "content": ligne["question"]}],
            )
            code_genere = "".join(b.text for b in reponse.content if b.type == "text").strip()
            code_genere = code_genere.strip("`").replace("python\n", "").strip()
            in_tok = reponse.usage.input_tokens
            out_tok = reponse.usage.output_tokens
        except Exception as e:  # erreur d'appel API : comptée comme requête invalide
            erreur_llm = str(e)

        verdict_b, texte_resultat, erreur_exec = "INVALIDE", "", None
        if code_genere is not None:
            try:
                resultat_brut = executer_pandas_genere(code_genere, df_autorise)
                texte_resultat = resultat_vers_texte(resultat_brut)
                verdict_b = scorer(ligne["mode_verification"], ligne["valeur_attendue"], texte_resultat)
            except Exception as e:
                erreur_exec = str(e)
                verdict_b = "INVALIDE"

        duree = time.perf_counter() - debut
        resultats.append({
            **ligne,
            "verdict_a": verdicts_a[ligne["id"]],
            "code_genere": (code_genere or "").replace("\n", " "),
            "resultat_b": texte_resultat.replace("\n", " ")[:200],
            "verdict_b": verdict_b,
            "erreur_llm": erreur_llm or "",
            "erreur_exec": erreur_exec or "",
            "duree_s": round(duree, 2),
            "tokens_entree": in_tok,
            "tokens_sortie": out_tok,
        })
        print(f"[{ligne['id']:>3}] A={verdicts_a[ligne['id']]:<10} B={verdict_b:<10} "
              f"{duree:5.1f}s  {ligne['question'][:60]}")

    champs = list(resultats[0].keys())
    with open(SORTIE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=champs)
        writer.writeheader()
        writer.writerows(resultats)

    # --- Table de contingence appariée et test de McNemar ---
    aa = sum(1 for r in resultats if r["verdict_a"] == "CORRECT" and r["verdict_b"] == "CORRECT")
    ab = sum(1 for r in resultats if r["verdict_a"] == "CORRECT" and r["verdict_b"] != "CORRECT")
    ba = sum(1 for r in resultats if r["verdict_a"] != "CORRECT" and r["verdict_b"] == "CORRECT")
    bb = sum(1 for r in resultats if r["verdict_a"] != "CORRECT" and r["verdict_b"] != "CORRECT")
    stat, p = mcnemar(aa, ab, ba, bb)

    n_invalides = sum(1 for r in resultats if r["verdict_b"] == "INVALIDE")
    durees_a = None  # non recalculé ici : reprendre duree_s de resultats_banc_etendu.csv si dispo
    durees_b = [r["duree_s"] for r in resultats]
    tokens_in = [r["tokens_entree"] for r in resultats if r["tokens_entree"]]
    tokens_out = [r["tokens_sortie"] for r in resultats if r["tokens_sortie"]]

    print("\n" + "=" * 78)
    print(f"Jeu de questions commun : {len(resultats)}")
    print(f"Exactitude Architecture A (tools fixes)      : {aa + ab}/{len(resultats)} "
          f"= {(aa + ab) / len(resultats):.1%}")
    print(f"Exactitude Architecture B (text-to-pandas)    : {aa + ba}/{len(resultats)} "
          f"= {(aa + ba) / len(resultats):.1%}")
    print("\nTable de contingence appariée (A x B) :")
    print(f"  A correct / B correct     : {aa}")
    print(f"  A correct / B incorrect   : {ab}")
    print(f"  A incorrect / B correct   : {ba}")
    print(f"  A incorrect / B incorrect : {bb}")
    print(f"\nTest de McNemar (avec correction de continuité) : statistique = {stat:.3f}, p = {p:.4f}")
    print("(p < 0.05 : les deux architectures diffèrent significativement en exactitude, "
          "pas seulement par hasard d'échantillonnage)")
    print(f"\nRequêtes invalides (Architecture B, erreur LLM ou d'exécution) : "
          f"{n_invalides}/{len(resultats)} = {n_invalides / len(resultats):.1%}")
    print(f"Latence Architecture B : p50={percentile(durees_b, .5):.2f}s  "
          f"p90={percentile(durees_b, .9):.2f}s")
    if tokens_in:
        print(f"Jetons Architecture B (moyenne/requête) : "
              f"{sum(tokens_in) / len(tokens_in):.0f} entrée, {sum(tokens_out) / len(tokens_out):.0f} sortie")
        print("Rappel : appliquer la tarification publique du modèle en vigueur à la date "
              "d'exécution pour convertir ces jetons en coût par requête (ne pas recopier "
              "une estimation antérieure potentiellement obsolète — cf. Annexe H.2 du mémoire).")
    print(f"\nDétail complet -> {SORTIE}")


if __name__ == "__main__":
    main()
