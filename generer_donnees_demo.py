"""
Génère un jeu de données factice (demo_data/) avec les mêmes colonnes que
Base_HPM_2026 Q2.xlsx / modeles.xlsx, mais des sites, districts et chiffres
entièrement inventés — utilisé uniquement pour l'hébergement public de
démonstration (Streamlit Community Cloud), jamais pour les vraies données.

À relancer si le format des vraies colonnes change.
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
AUJOURD_HUI = date(2026, 7, 19)

DISTRICTS = ["District Démo Nord", "District Démo Sud", "District Démo Est", "District Démo Ouest"]
SITES_PAR_DISTRICT = {
    "District Démo Nord": ["Hôpital Démo Nord A", "CHU Démonstration Nord"],
    "District Démo Sud": ["Clinique Démo Sud", "Hôpital Test Sud B"],
    "District Démo Est": ["CH Exemple Est", "Polyclinique Démo Est"],
    "District Démo Ouest": ["Hôpital Fictif Ouest", "CHU Test Ouest"],
}
MATERIELS = [
    ("MAT-SCAN", "Scanner Démo X1"),
    ("MAT-MONITOR", "Moniteur Patient Démo"),
    ("MAT-VENTIL", "Ventilateur Démo V2"),
    ("MAT-ECHO", "Echographe Démo"),
]
SITUATIONS = ["ga_active", "sap_billable_active", "sap_nonbillable_active", "expire", "aucun"]
PROBABILITES = [0.15, 0.25, 0.05, 0.20, 0.35]

N_EQUIPEMENTS = 600

lignes = []
for i in range(N_EQUIPEMENTS):
    district = rng.choice(DISTRICTS)
    site = rng.choice(SITES_PAR_DISTRICT[district])
    material, libelle = MATERIELS[rng.integers(0, len(MATERIELS))]
    libelle_fl = rng.choice(
        ["FL-STANDARD", "FL-STANDARD", "FL-STANDARD", "PMIS-DEMO", "DEFB-DEMO"]
    )
    situation = rng.choice(SITUATIONS, p=PROBABILITES)

    debut = fin = dfg = contrat_sap = contrat_ga = ""
    type_contrat = ""

    if situation == "ga_active":
        contrat_ga = f"GA-{i}"
        dfg = AUJOURD_HUI + timedelta(days=int(rng.integers(30, 900)))
    elif situation == "sap_billable_active":
        contrat_sap = f"SAP-{i}"
        type_contrat = "BILLABLE"
        debut = AUJOURD_HUI - timedelta(days=int(rng.integers(30, 400)))
        fin = AUJOURD_HUI + timedelta(days=int(rng.integers(30, 400)))
    elif situation == "sap_nonbillable_active":
        contrat_sap = f"SAP-{i}"
        type_contrat = "NON BILLABLE"
        debut = AUJOURD_HUI - timedelta(days=int(rng.integers(30, 400)))
        fin = AUJOURD_HUI + timedelta(days=int(rng.integers(30, 400)))
    elif situation == "expire":
        contrat_sap = f"SAP-{i}"
        type_contrat = "BILLABLE"
        debut = AUJOURD_HUI - timedelta(days=800)
        fin = AUJOURD_HUI - timedelta(days=int(rng.integers(1, 300)))
    # "aucun" : tout reste vide -> Non couvert

    lignes.append({
        "Equipement": 90000000 + i,
        "Material": material,
        "Libelle": libelle,
        "Libelle FL": libelle_fl,
        "Serial Number": f"DEMO{100000 + i}",  # sans tiret : un tiret déclenche la règle de nettoyage PMIS/DEFB
        "Contrat SAP": contrat_sap,
        "Contrat GA": contrat_ga,
        "Type": type_contrat,
        "Debut": debut,
        "Fin": fin,
        "DFG": dfg,
        "District SFDC": district,
        "SH Name": site,
    })

df_base = pd.DataFrame(lignes)
df_base.to_excel("demo_data/Base_Demo.xlsx", index=False)

df_modeles = pd.DataFrame(
    [{"Material": m, "Libelle": l, "Décision": "Garder"} for m, l in MATERIELS]
)
df_modeles.to_excel("demo_data/modeles_demo.xlsx", index=False)

print(f"Générés : demo_data/Base_Demo.xlsx ({len(df_base)} lignes), demo_data/modeles_demo.xlsx")
