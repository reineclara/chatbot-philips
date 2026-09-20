# Assistant Philips HPM

Chatbot conversationnel adossé à un dashboard Power BI de suivi de la couverture (garantie, extension de garantie, contrat de maintenance) du parc d'équipements médicaux Philips. Il permet à des utilisateurs non techniques (commerciaux, responsables de district, managers) d'obtenir en langage naturel des chiffres qui, autrement, demanderaient de naviguer dans les filtres du dashboard.

Ce projet est réalisé dans le cadre d'un mémoire de fin d'études : au-delà de l'assistant lui-même, le dépôt contient le protocole d'évaluation qui a servi à en mesurer la fiabilité (exactitude des chiffres, absence de fuite de données brutes, temps de réponse).

## Ce que fait l'assistant

- **Répondre aux questions conceptuelles** sur le dashboard (« Qu'est-ce qu'un équipement couvert ? », « Que signifie DFG ? ») à partir d'un glossaire dédié, sans jamais inventer une définition qui n'y figure pas.
- **Donner des chiffres exacts, jamais inventés** : toute question chiffrée déclenche l'exécution d'une fonction Python qui interroge les données réelles — le modèle ne génère jamais un nombre de mémoire.
  - KPIs globaux (total, couverts/non couverts, répartition par type de couverture)
  - Répartition par district commercial ou par site hospitalier
  - Classement des sites (top N couverts / non couverts)
  - Anticipation des sorties de couverture à venir, filtrable par mois, année, site et/ou district
- **Gérer la conversation multi-tours** (« Et pour Nord Est ? » après une première question sur un autre district) sans jamais confondre ou récapituler spontanément les tours précédents.
- **Décliner poliment** les questions hors périmètre (médical, RH, etc.) et demander une précision plutôt que deviner quand une question est ambiguë.

## Architecture

```
app.py          → Interface Streamlit (chat, style Philips, boutons de questions exemples)
assistant.py    → Orchestration LLM : system prompt, déclaration des tools, boucle
                  agentique (function calling natif Claude), aucun framework tiers
data_layer.py   → Chargement/nettoyage des données Excel, calcul de la couverture,
                  fonctions d'agrégation exposées comme tools au LLM
glossaire.py    → FAQ pédagogique injectée telle quelle dans le system prompt
```

Le flux est simple : l'utilisateur pose une question dans Streamlit → `assistant.py` l'envoie à Claude avec la liste des tools disponibles → si Claude a besoin d'une donnée, il demande l'exécution d'un tool (ex. `get_kpis_par_district(district="Nord Est")`) → `data_layer.py` exécute réellement le calcul sur les données → le résultat est renvoyé à Claude, qui formule la réponse finale en langage naturel.

### Comment la couverture d'un équipement est calculée

Un équipement est classé selon trois protections possibles, dans cet ordre de priorité :

1. **Garantie constructeur** — un contrat GA existe et la date de fin de garantie (DFG) n'est pas encore passée.
2. **Extension de garantie** — un contrat SAP de type `NON BILLABLE` est actif (date du jour comprise entre début et fin).
3. **Sous contrat** — un contrat SAP de type `BILLABLE` est actif.
4. Sinon, l'équipement est **Non couvert**.

En amont, les données sont nettoyées : exclusion des équipements marqués « à supprimer » dans le référentiel des modèles, et retrait des lignes PMIS/DEFB non pertinentes.

### Garde-fou sur les données sensibles

Toutes les fonctions exposées au LLM ne renvoient que des agrégats calculés. Une vérification automatique (`_verifier_allowlist` dans `data_layer.py`) fait échouer bruyamment tout résultat qui contiendrait une colonne brute (numéro de série, matériel, contrat, adresse, etc.), pour éviter qu'un futur ajout de champ ne fuite une donnée sensible par erreur.

## Installation

**Prérequis** : Python 3.10+, une clé API Anthropic.

```bash
pip install -r requirements.txt
```

Créez un fichier `.env` à la racine :

```
ANTHROPIC_API_KEY=votre_clé_ici
```

**Données** : ce dépôt ne contient pas les données réelles (confidentielles). Placez à la racine du projet :
- `Base_HPM_2026 Q2.xlsx` — export du parc d'équipements
- `modeles.xlsx` — référentiel des modèles à exclure

(voir `FICHIER_BASE` / `FICHIER_MODELES` dans `data_layer.py` pour les colonnes attendues).

**Lancement** :

```bash
streamlit run app.py
```

## Évaluation et tests

Le dépôt inclut le protocole utilisé pour valider la fiabilité de l'assistant :

- `test_end_to_end.py` — une vingtaine de scénarios (FAQ, données, classements, anticipation, cas limites, multi-tours) vérifiant l'absence de fuite de champ sensible et un temps de réponse acceptable.
- `generer_banc_questions.py` / `executer_banc_questions.py` — génération et exécution d'un banc de questions étendu, avec comparaison automatique à une valeur attendue calculée indépendamment.
- `verite_terrain.py` — calcule la réponse « attendue » à chaque question en appelant directement `data_layer.py`, sans passer par le LLM ni l'assistant, pour isoler la fiabilité de la couche d'orchestration de celle des données.
- `executer_comparaison_h2.py` — protocole de comparaison entre l'approche tool-calling (celle de ce projet) et une approche alternative texte-vers-code (génération de pandas à la volée), pour objectiver le choix d'architecture.
- `lire_excel.py` — script exploratoire original ayant servi à valider la logique de nettoyage et de calcul de couverture, aujourd'hui reprise à l'identique dans `data_layer.py`.

Les résultats chiffrés de ces bancs de test (contenant de vraies données métier) ne sont volontairement pas versionnés — voir `.gitignore`.

## Limites connues

- Les données proviennent d'un export Excel trimestriel : l'assistant reflète la situation au dernier export, pas le temps réel.
- Les fonctions de données renvoient une structure de graphique (`"graphique"`) pensée pour un affichage Plotly dans le chat, mais celui-ci n'est pas encore branché côté interface — les réponses restent pour l'instant uniquement textuelles.
- L'intégration native dans un visuel Power BI n'a pas été retenue (limitation des visuels HTML gratuits de Power BI face à une application Streamlit) ; l'assistant est prévu pour être ouvert dans un onglet à côté du dashboard.
