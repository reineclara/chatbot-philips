"""
Couche de données du chatbot Philips HPM.

Reprend exactement la logique validée de lire_excel.py (jointure modeles.xlsx,
nettoyage PMIS/DEFB, calcul de la colonne Couverture) et expose des fonctions
d'agrégation destinées à être appelées comme des "tools" par le LLM. Chaque
fonction renvoie un dict JSON-sérialisable : un texte prêt à lire pour le LLM,
et si pertinent des données de graphique pour l'affichage Streamlit/Plotly.
"""

import os
from datetime import date
from functools import lru_cache

import pandas as pd

# MODE_DEMO=true (variable d'environnement) bascule sur un jeu de données
# factice — utilisé uniquement pour l'hébergement public de démonstration
# (Streamlit Community Cloud). En local, sans cette variable, on utilise les
# vraies données comme avant.
MODE_DEMO = os.environ.get("MODE_DEMO", "").lower() in ("1", "true", "yes")

if MODE_DEMO:
    FICHIER_BASE = "demo_data/Base_Demo.xlsx"
    FICHIER_MODELES = "demo_data/modeles_demo.xlsx"
else:
    FICHIER_BASE = "Base_HPM_2026 Q2.xlsx"
    FICHIER_MODELES = "modeles.xlsx"

COUVERTS = ["Sous contrat", "Extension de garantie", "Garantie constructeur"]

# Colonnes brutes de l'Excel qui ne doivent jamais sortir d'un tool (garde-fou
# défense-en-profondeur : les fonctions get_* ne doivent renvoyer que des
# agrégats calculés, jamais de données brutes potentiellement sensibles).
CHAMPS_INTERDITS = {
    "serial number", "material", "contrat sap", "contrat ga",
    "nom rt", "ville sh", "install date", "libelle fl", "libelle",
    "personnalisé", "equipement", "dfg", "debut", "fin",
}


def _verifier_allowlist(resultat: dict) -> dict:
    """Lève une erreur si le résultat d'un tool contient un champ interdit.

    Parcourt récursivement toutes les clés (dicts imbriqués, listes de dicts)
    et compare chacune à CHAMPS_INTERDITS. Pensé pour échouer bruyamment si un
    futur ajout de colonne dans un get_* réexpose une donnée brute par erreur.
    """

    def _cles(obj):
        if isinstance(obj, dict):
            for cle, val in obj.items():
                yield cle
                yield from _cles(val)
        elif isinstance(obj, list):
            for item in obj:
                yield from _cles(item)

    for cle in _cles(resultat):
        if str(cle).strip().lower() in CHAMPS_INTERDITS:
            raise ValueError(f"Champ interdit détecté dans un résultat de tool : '{cle}'")
    return resultat


def _nettoyage_pmis_defb(ligne):
    libelle_fl = ligne["Libelle FL"]
    serial_number = ligne["Serial Number"]
    if pd.isnull(libelle_fl) or pd.isnull(serial_number):
        return "Garder"
    libelle = str(libelle_fl).upper().strip()
    serial = str(serial_number)
    if libelle.startswith("DEFB"):
        return "Supprimer"
    elif libelle.startswith("PMIS"):
        return "Garder"
    elif "-" in serial:
        return "Supprimer"
    else:
        return "Garder"


def _calculer_couverture(ligne, today):
    contrat_sap = ligne["ContratSAP_clean"]
    contrat_ga = ligne["ContratGA_clean"]
    type_val = ligne["Type_clean"]
    debut = ligne["Debut_date"]
    fin = ligne["Fin_date"]
    dfg = ligne["DFG_date"]

    has_contrat_sap = contrat_sap != ""
    has_contrat_ga = contrat_ga != ""
    dates_valides = (
        debut is not None and not pd.isnull(debut) and
        fin is not None and not pd.isnull(fin) and
        debut <= fin
    )
    couvert_ga = (
        has_contrat_ga and
        dfg is not None and not pd.isnull(dfg) and
        today <= dfg
    )
    couvert_extension = (
        has_contrat_sap and type_val == "NON BILLABLE" and
        dates_valides and debut <= today <= fin
    )
    couvert_sap_billable = (
        has_contrat_sap and type_val == "BILLABLE" and
        dates_valides and debut <= today <= fin
    )

    if couvert_ga:
        return "Garantie constructeur"
    elif couvert_extension:
        return "Extension de garantie"
    elif couvert_sap_billable:
        return "Sous contrat"
    else:
        return "Non couvert"


@lru_cache(maxsize=1)
def charger_donnees() -> pd.DataFrame:
    """Charge, nettoie et calcule la Couverture. Mis en cache (le fichier fait ~28 Mo)."""
    df = pd.read_excel(FICHIER_BASE)
    df_modeles = pd.read_excel(FICHIER_MODELES)

    df_modeles["Personnalisé"] = (
        df_modeles["Material"].astype(str).str.upper().str.strip()
        + "|" +
        df_modeles["Libelle"].astype(str).str.upper().str.strip()
    )
    df["Personnalisé"] = (
        df["Material"].astype(str).str.upper().str.strip()
        + "|" +
        df["Libelle"].astype(str).str.upper().str.strip()
    )
    a_supprimer = df_modeles[df_modeles["Décision"] == "Supprimer"]["Personnalisé"]
    df = df[~df["Personnalisé"].isin(a_supprimer)].copy()

    df["Nettoyage PMIS et DEFB"] = df.apply(_nettoyage_pmis_defb, axis=1)
    df = df[df["Nettoyage PMIS et DEFB"] == "Garder"].copy()

    df["ContratSAP_clean"] = df["Contrat SAP"].astype(str).str.upper().str.strip().replace("NAN", "")
    df["ContratGA_clean"] = df["Contrat GA"].astype(str).str.upper().str.strip().replace("NAN", "")
    df["Type_clean"] = df["Type"].astype(str).str.upper().str.strip().replace("NAN", "")

    df["Debut_date"] = pd.to_datetime(df["Debut"], errors="coerce").dt.date
    df["Fin_date"] = pd.to_datetime(df["Fin"], errors="coerce").dt.date
    df["DFG_date"] = pd.to_datetime(df["DFG"], errors="coerce").dt.date

    today = date.today()
    df["Couverture"] = df.apply(lambda ligne: _calculer_couverture(ligne, today), axis=1)

    df["DFG_dt"] = pd.to_datetime(df["DFG"], errors="coerce")
    df["Fin_dt"] = pd.to_datetime(df["Fin"], errors="coerce")

    def _fin_couverture(ligne):
        if ligne["Couverture"] == "Garantie constructeur":
            return ligne["DFG_dt"]
        elif ligne["Couverture"] in ("Extension de garantie", "Sous contrat"):
            return ligne["Fin_dt"]
        return pd.NaT

    df["Fin_couverture"] = df.apply(_fin_couverture, axis=1)

    return df


def _filtrer_district(df: pd.DataFrame, district: str | None) -> pd.DataFrame:
    if not district:
        return df
    district_norm = district.strip().upper()
    return df[df["District SFDC"].astype(str).str.upper().str.contains(district_norm, na=False)]


def get_kpis_globaux() -> dict:
    """KPIs globaux du dashboard (page Couverture)."""
    df = charger_donnees()
    total = df["Equipement"].nunique()
    par_type = df["Couverture"].value_counts().to_dict()
    couverts = sum(par_type.get(t, 0) for t in COUVERTS)
    non_couverts = par_type.get("Non couvert", 0)

    df_site = df.groupby("SH Name")["Couverture"].apply(
        lambda s: (s == "Non couvert").all()
    )
    sites_100_hors_contrat = int(df_site.sum())

    return _verifier_allowlist({
        "resume": (
            f"Sur un total de {total} équipements, {couverts} sont couverts "
            f"({', '.join(f'{par_type.get(t, 0)} en {t}' for t in COUVERTS)}) et "
            f"{non_couverts} ne sont couverts par rien. "
            f"{sites_100_hors_contrat} sites hospitaliers sont 100% hors contrat."
        ),
        "total_equipements": int(total),
        "equipements_couverts": int(couverts),
        "equipements_non_couverts": int(non_couverts),
        "repartition_par_type": {t: int(par_type.get(t, 0)) for t in COUVERTS + ["Non couvert"]},
        "nb_sites_100_pourcent_hors_contrat": sites_100_hors_contrat,
        "graphique": {
            "type": "bar",
            "titre": "Répartition des équipements par type de couverture",
            "labels": COUVERTS + ["Non couvert"],
            "valeurs": [int(par_type.get(t, 0)) for t in COUVERTS + ["Non couvert"]],
        },
    })


def get_kpis_par_district(district: str | None = None) -> dict:
    """Répartition couverts/non couverts par district SFDC, ou un district précis si fourni."""
    df = charger_donnees()
    df_district = df.groupby("District SFDC").agg(
        total=("Equipement", "nunique"),
        couverts=("Couverture", lambda s: s.isin(COUVERTS).sum()),
        non_couverts=("Couverture", lambda s: (s == "Non couvert").sum()),
    ).reset_index()

    if district:
        filtre = _filtrer_district(df, district)
        if filtre.empty:
            return {"resume": f"Aucun district ne correspond à '{district}'.", "districts": []}
        district_reel = filtre["District SFDC"].iloc[0]
        ligne = df_district[df_district["District SFDC"] == district_reel].iloc[0]
        return _verifier_allowlist({
            "resume": (
                f"Le district {ligne['District SFDC']} compte {int(ligne['total'])} équipements : "
                f"{int(ligne['couverts'])} couverts et {int(ligne['non_couverts'])} non couverts."
            ),
            "districts": [ligne.to_dict()],
        })

    resume_lignes = [
        f"{r['District SFDC']} : {int(r['total'])} équipements, {int(r['couverts'])} couverts, "
        f"{int(r['non_couverts'])} non couverts"
        for _, r in df_district.iterrows()
    ]
    return _verifier_allowlist({
        "resume": "Répartition par district :\n" + "\n".join(resume_lignes),
        "districts": df_district.to_dict(orient="records"),
        "graphique": {
            "type": "bar_groupe",
            "titre": "Équipements couverts / non couverts par district",
            "labels": df_district["District SFDC"].tolist(),
            "series": {
                "Couverts": df_district["couverts"].tolist(),
                "Non couverts": df_district["non_couverts"].tolist(),
            },
        },
    })


def get_kpis_par_site(site: str | None = None, district: str | None = None) -> dict:
    """Répartition couverts/non couverts par site hospitalier (SH Name), avec filtre optionnel."""
    df = charger_donnees()
    df = _filtrer_district(df, district)

    df_site = df.groupby(["SH Name", "District SFDC"]).agg(
        total=("Equipement", "nunique"),
        couverts=("Couverture", lambda s: s.isin(COUVERTS).sum()),
        non_couverts=("Couverture", lambda s: (s == "Non couvert").sum()),
    ).reset_index()

    if site:
        site_norm = site.strip().upper()
        filtre = df_site[df_site["SH Name"].str.upper().str.contains(site_norm, na=False)]
        if filtre.empty:
            return {"resume": f"Aucun site ne correspond à '{site}'.", "sites": []}
        lignes = [
            f"{r['SH Name']} ({r['District SFDC']}) : {int(r['total'])} équipements, "
            f"{int(r['couverts'])} couverts, {int(r['non_couverts'])} non couverts"
            for _, r in filtre.iterrows()
        ]
        return _verifier_allowlist({"resume": "\n".join(lignes), "sites": filtre.to_dict(orient="records")})

    return _verifier_allowlist({
        "resume": f"{len(df_site)} sites trouvés" + (f" dans le district {district}" if district else ""),
        "sites": df_site.to_dict(orient="records"),
    })


def get_top_sites(n: int = 10, critere: str = "couverts") -> dict:
    """Top N sites par équipements couverts ou non couverts."""
    if critere not in ("couverts", "non_couverts"):
        critere = "couverts"
    df = charger_donnees()
    df_site = df.groupby(["SH Name", "District SFDC"]).agg(
        total=("Equipement", "nunique"),
        couverts=("Couverture", lambda s: s.isin(COUVERTS).sum()),
        non_couverts=("Couverture", lambda s: (s == "Non couvert").sum()),
    ).reset_index()

    top = df_site.nlargest(n, critere)
    label = "équipements couverts" if critere == "couverts" else "équipements non couverts"
    lignes = [
        f"{i+1}. {r['SH Name']} ({r['District SFDC']}) : {int(r[critere])} {label} sur {int(r['total'])} au total"
        for i, (_, r) in enumerate(top.iterrows())
    ]
    return _verifier_allowlist({
        "resume": f"Top {n} sites par {label} :\n" + "\n".join(lignes),
        "sites": top.to_dict(orient="records"),
        "graphique": {
            "type": "bar",
            "titre": f"Top {n} sites par {label}",
            "labels": top["SH Name"].tolist(),
            "valeurs": top[critere].tolist(),
        },
    })


def get_anticipation(mois: int | None = None, annee: int | None = None) -> dict:
    """Équipements dont la couverture (garantie, extension ou contrat) arrive à échéance, par mois/année."""
    df = charger_donnees()
    today_ts = pd.Timestamp(date.today())
    df_anticip = df[
        df["Couverture"].isin(COUVERTS) &
        df["Fin_couverture"].notna() &
        (df["Fin_couverture"] >= today_ts)
    ].copy()

    df_anticip["Mois_Annee"] = df_anticip["Fin_couverture"].dt.to_period("M")
    df_mois = df_anticip.groupby("Mois_Annee").agg(
        nb_equipements=("Equipement", "nunique")
    ).reset_index().sort_values("Mois_Annee")
    df_mois["Mois_Annee_str"] = df_mois["Mois_Annee"].astype(str)

    if annee is not None:
        df_mois = df_mois[df_mois["Mois_Annee"].dt.year == annee]
    if mois is not None:
        df_mois = df_mois[df_mois["Mois_Annee"].dt.month == mois]

    if df_mois.empty:
        return {"resume": "Aucun équipement ne sort de couverture sur cette période.", "mois": []}

    lignes = [
        f"{r['Mois_Annee_str']} : {int(r['nb_equipements'])} équipements sortent de couverture"
        for _, r in df_mois.iterrows()
    ]
    return _verifier_allowlist({
        "resume": "\n".join(lignes),
        "mois": df_mois[["Mois_Annee_str", "nb_equipements"]].to_dict(orient="records"),
        "graphique": {
            "type": "bar",
            "titre": "Anticipation des sorties de couverture par mois",
            "labels": df_mois["Mois_Annee_str"].tolist(),
            "valeurs": df_mois["nb_equipements"].tolist(),
        },
    })


if __name__ == "__main__":
    kpis = get_kpis_globaux()
    print(kpis["resume"])
    print()
    print("Vérification par rapport aux chiffres de référence Power BI :")
    print(f"  Total attendu 31630, obtenu {kpis['total_equipements']}")
    print(f"  Couverts attendu 9138, obtenu {kpis['equipements_couverts']}")
    print(f"  Non couverts attendu 22492, obtenu {kpis['equipements_non_couverts']}")
    rep = kpis["repartition_par_type"]
    print(f"  Sous contrat attendu 5384, obtenu {rep['Sous contrat']}")
    print(f"  Garantie constructeur attendu 3504, obtenu {rep['Garantie constructeur']}")
    print(f"  Extension de garantie attendu 250, obtenu {rep['Extension de garantie']}")
