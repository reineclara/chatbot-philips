import pandas as pd
from datetime import date

pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)

# ── ÉTAPE 1 : Chargement des fichiers ─────────────────────────────────────
df = pd.read_excel("Base_HPM_2026 Q2.xlsx")
df_modeles = pd.read_excel("modeles.xlsx")

# ── ÉTAPE 2 : Jointure — filtrer les 31 630 équipements valides ───────────
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
print(f"Équipements après jointure : {len(df)}")

# ── ÉTAPE 2B : Nettoyage PMIS et DEFB ─────────────────────────────────────
def nettoyage_pmis_defb(ligne):
    libelle_fl    = ligne["Libelle FL"]
    serial_number = ligne["Serial Number"]
    if pd.isnull(libelle_fl) or pd.isnull(serial_number):
        return "Garder"
    libelle = str(libelle_fl).upper().strip()
    serial  = str(serial_number)
    if libelle.startswith("DEFB"):
        return "Supprimer"
    elif libelle.startswith("PMIS"):
        return "Garder"
    elif "-" in serial:
        return "Supprimer"
    else:
        return "Garder"

df["Nettoyage PMIS et DEFB"] = df.apply(nettoyage_pmis_defb, axis=1)
avant = len(df)
df = df[df["Nettoyage PMIS et DEFB"] == "Garder"].copy()
apres = len(df)
print(f"Avant nettoyage PMIS/DEFB : {avant}")
print(f"Après nettoyage PMIS/DEFB : {apres}")
print(f"Lignes supprimées         : {avant - apres}")

# ── ÉTAPE 3 : Nettoyage des colonnes texte ────────────────────────────────
df["ContratSAP_clean"] = df["Contrat SAP"].astype(str).str.upper().str.strip().replace("NAN", "")
df["ContratGA_clean"]  = df["Contrat GA"].astype(str).str.upper().str.strip().replace("NAN", "")
df["Type_clean"]       = df["Type"].astype(str).str.upper().str.strip().replace("NAN", "")

# ── ÉTAPE 4 : Conversion des dates ────────────────────────────────────────
df["Debut_date"] = pd.to_datetime(df["Debut"], errors="coerce").dt.date
df["Fin_date"]   = pd.to_datetime(df["Fin"],   errors="coerce").dt.date
df["DFG_date"]   = pd.to_datetime(df["DFG"],   errors="coerce").dt.date

# ── ÉTAPE 5 : Calcul de la colonne Couverture ─────────────────────────────
def calculer_couverture(ligne):
    today = date.today()
    contrat_sap = ligne["ContratSAP_clean"]
    contrat_ga  = ligne["ContratGA_clean"]
    type_val    = ligne["Type_clean"]
    debut       = ligne["Debut_date"]
    fin         = ligne["Fin_date"]
    dfg         = ligne["DFG_date"]

    has_contrat_sap = contrat_sap != ""
    has_contrat_ga  = contrat_ga  != ""
    dates_valides   = (
        debut is not None and not pd.isnull(debut) and
        fin   is not None and not pd.isnull(fin)   and
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

df["Couverture"] = df.apply(calculer_couverture, axis=1)

print("\nRépartition des couvertures :")
print(df["Couverture"].value_counts())

# ── ÉTAPE 6 : Comparaison par district ───────────────────────────────────
couverts_vals = ["Sous contrat", "Extension de garantie", "Garantie constructeur"]

df_district = df.groupby("District SFDC").agg(
    total        = ("Equipement", "nunique"),
    couverts     = ("Couverture", lambda x: x.isin(couverts_vals).sum()),
    non_couverts = ("Couverture", lambda x: (x == "Non couvert").sum())
).reset_index()

print("\nRépartition par district :")
print(df_district.to_string())

# ── ÉTAPE 7 : Répartition par site (TOP 10) ──────────────────────────────
print("\n=== GRAPHIQUE 2 : PAR SITE (TOP 10) ===")
df_site = df.groupby(["SH Name", "District SFDC"]).agg(
    total        = ("Equipement", "nunique"),
    couverts     = ("Couverture", lambda x: x.isin(couverts_vals).sum()),
    non_couverts = ("Couverture", lambda x: (x == "Non couvert").sum())
).reset_index()

top10_couverts = df_site.nlargest(10, "couverts")
print("\nTop 10 sites par équipements couverts :")
print(top10_couverts[["SH Name", "District SFDC", "total", "couverts", "non_couverts"]].to_string())

top10_non_couverts = df_site.nlargest(10, "non_couverts")
print("\nTop 10 sites par équipements non couverts :")
print(top10_non_couverts[["SH Name", "District SFDC", "total", "couverts", "non_couverts"]].to_string())

# ── ÉTAPE 8 : Anticipation par mois/année ────────────────────────────────
print("\n=== GRAPHIQUE 3 : ANTICIPATION PAR MOIS/ANNÉE ===")

# Convertir les dates proprement
df["DFG_dt"]  = pd.to_datetime(df["DFG"],  errors="coerce")
df["Fin_dt"]  = pd.to_datetime(df["Fin"],  errors="coerce")

# Prendre la date de fin de couverture selon le type
def get_fin_couverture(ligne):
    couverture = ligne["Couverture"]
    if couverture == "Garantie constructeur":
        return ligne["DFG_dt"]
    elif couverture == "Extension de garantie":
        return ligne["Fin_dt"]
    elif couverture == "Sous contrat":
        return ligne["Fin_dt"]
    else:
        return pd.NaT

df["Fin_couverture"] = df.apply(get_fin_couverture, axis=1)

# Filtrer uniquement les équipements couverts avec une date de fin future
today_ts = pd.Timestamp(date.today())
df_anticip = df[
    (df["Couverture"].isin(couverts_vals)) &
    (df["Fin_couverture"].notna()) &
    (df["Fin_couverture"] >= today_ts)
].copy()

# Grouper par mois/année
df_anticip["Mois_Annee"] = df_anticip["Fin_couverture"].dt.to_period("M")
df_mois = df_anticip.groupby("Mois_Annee").agg(
    nb_equipements = ("Equipement", "nunique")
).reset_index()

df_mois = df_mois.sort_values("Mois_Annee")
print(df_mois.to_string())