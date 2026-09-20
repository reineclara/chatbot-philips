"""
Vérité terrain indépendante pour le protocole d'évaluation étendu (chapitre 5,
section 5.5, et Annexe H du mémoire).

Portée et limite assumée de ce module (à lire avant tout usage) :
----------------------------------------------------------------
Ce module calcule la réponse "attendue" à chaque question de banc en appelant
DIRECTEMENT les fonctions de data_layer.py, SANS PASSER PAR L'ASSISTANT NI PAR
LE LLM (assistant.poser_question n'est jamais importé ici). Il constitue donc
une vérité terrain indépendante de la couche d'orchestration LLM (sélection
du tool, extraction des paramètres depuis le langage naturel, reformulation
de la réponse en prose) : c'est précisément cette couche que le protocole
étendu cherche à évaluer, alors que le protocole actuel (section 5.3 du
mémoire) ne la vérifiait que par relecture manuelle d'un échantillon de 20
scénarios.

Ce module N'EST PAS une vérité terrain indépendante de data_layer.py
lui-même : si _calculer_couverture() contient une erreur, cette erreur se
retrouve à la fois dans la réponse de l'assistant ET dans la vérité terrain
calculée ici, et le test ne la détectera pas. La correction de data_layer.py
est vérifiée séparément, par un canal différent, au chapitre 5 section 5.2
du mémoire (comptage croisé avec le modèle Power BI / la requête DAX). Ne pas
présenter les résultats produits par ce module comme couvrant cette
dimension-là : ils couvrent la fiabilité de l'assistant conversationnel
ÉTANT DONNÉ un data_layer.py correct.

Prérequis : ce fichier doit être placé dans le même dossier que
data_layer.py (et donc avoir accès à Base_HPM_2026 Q2.xlsx et modeles.xlsx
au même chemin que data_layer.py les attend).
"""

from __future__ import annotations

from dataclasses import dataclass

import data_layer


@dataclass
class ValeurAttendue:
    valeur: int | float | str
    tool_attendu: str
    parametres_attendus: dict


def verite_globale() -> ValeurAttendue:
    kpis = data_layer.get_kpis_globaux()
    return ValeurAttendue(
        valeur=kpis["equipements_non_couverts"],
        tool_attendu="get_kpis_globaux",
        parametres_attendus={},
    )


def verite_district(district: str, mesure: str = "non_couverts") -> ValeurAttendue:
    """mesure : 'total', 'couverts' ou 'non_couverts'."""
    res = data_layer.get_kpis_par_district(district)
    if not res.get("districts"):
        return ValeurAttendue(valeur=None, tool_attendu="get_kpis_par_district",
                               parametres_attendus={"district": district})
    ligne = res["districts"][0]
    return ValeurAttendue(
        valeur=int(ligne[mesure]),
        tool_attendu="get_kpis_par_district",
        parametres_attendus={"district": district},
    )


def verite_site(site: str, mesure: str = "non_couverts") -> ValeurAttendue:
    res = data_layer.get_kpis_par_site(site)
    if not res.get("sites"):
        return ValeurAttendue(valeur=None, tool_attendu="get_kpis_par_site",
                               parametres_attendus={"site": site})
    ligne = res["sites"][0]
    return ValeurAttendue(
        valeur=int(ligne[mesure]),
        tool_attendu="get_kpis_par_site",
        parametres_attendus={"site": site},
    )


def verite_top_sites(n: int, critere: str) -> ValeurAttendue:
    res = data_layer.get_top_sites(n=n, critere=critere)
    noms = [s["SH Name"] for s in res["sites"]]
    return ValeurAttendue(
        valeur=noms[0] if noms else None,
        tool_attendu="get_top_sites",
        parametres_attendus={"n": n, "critere": critere},
    )


def verite_anticipation(mois: int | None, annee: int | None) -> ValeurAttendue:
    res = data_layer.get_anticipation(mois=mois, annee=annee)
    total = sum(m["nb_equipements"] for m in res.get("mois", []))
    return ValeurAttendue(
        valeur=total,
        tool_attendu="get_anticipation",
        parametres_attendus={"mois": mois, "annee": annee},
    )


def lister_districts() -> list[str]:
    """Districts commerciaux réels uniquement (ex: "Nord Est", "Sud Ouest"),
    à l'exclusion des catégories administratives ("Dealers(FR)", "Dom
    Tom(FR)", "non affecté") qui ne sont pas des districts au sens du
    mémoire (cf. section 3, tableau 3.1). Le suffixe "(FR)" présent dans la
    colonne brute "District SFDC" est retiré des questions générées : le
    matching de data_layer.get_kpis_par_district est fait par contains sur
    texte normalisé (voir data_layer.py), donc "Nord Est" retrouve bien
    "Nord Est(FR)" — retirer le suffixe rapproche les questions générées de
    la formulation réelle attendue d'un utilisateur (cf. exemples du system
    prompt dans assistant.py, qui utilisent aussi "Nord Est"/"Sud Ouest")."""
    df = data_layer.charger_donnees()
    exclus = {"dealers(fr)", "dom tom(fr)", "non affecté", "non affecte"}
    bruts = sorted(d for d in df["District SFDC"].dropna().unique().tolist())
    return [
        d[:-4].strip() if d.lower().endswith("(fr)") else d
        for d in bruts
        if d.lower().strip() not in exclus
    ]


def lister_sites(limite: int | None = None) -> list[str]:
    df = data_layer.charger_donnees()
    sites = sorted(s for s in df["SH Name"].dropna().unique().tolist())
    if limite is not None:
        # Échantillon déterministe (pas aléatoire) pour la reproductibilité :
        # un site pris régulièrement tous les `pas` éléments plutôt qu'un
        # tirage aléatoire, afin que deux exécutions produisent le même banc.
        pas = max(1, len(sites) // limite)
        sites = sites[::pas][:limite]
    return sites
