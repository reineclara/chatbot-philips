Ajoute dans mon rapport une explication pédagogique détaillée de comment fonctionne le function calling natif de Claude, en te basant sur mon architecture réelle (le code de `assistant.py`). Place ça soit en développement de la section 3.4.5 ("Orchestration : une boucle agentique native, sans framework tiers"), soit juste après le schéma simplifié de flux de la section 3.4.1 — choisis l'endroit qui s'intègre le mieux à la structure actuelle du document, sans dupliquer ce qui est déjà écrit ailleurs.

Contenu à intégrer (à reformuler dans le style académique du reste du document, pas à copier-coller tel quel) :

## Le principe

Le function calling permet à Claude de **demander** l'exécution d'une fonction Python avec des paramètres précis, sans jamais exécuter de code lui-même — Claude ne manipule que du texte : il décide uniquement *quelle* fonction appeler et *avec quels arguments*. C'est le code applicatif (`assistant.py`) qui exécute réellement la fonction et lui renvoie le résultat.

## Le déroulé en sept étapes, ancré dans le code réel

1. **Déclaration des outils disponibles** — la liste `TOOLS` dans `assistant.py` : pour chaque tool, un `name`, une `description` en langage naturel (c'est elle qui guide le choix de Claude, il n'y a aucun code de routage écrit manuellement), et un `input_schema` (schéma JSON des paramètres attendus).

2. **Envoi de la question et de la liste des tools à l'API** — `client.messages.create(model=MODEL, messages=messages, tools=TOOLS, ...)`. Claude lit la question, voit les descriptions des six tools disponibles, et décide lui-même s'il a besoin d'un tool ou s'il peut répondre directement (cas des questions couvertes par le glossaire).

3. **Deux issues possibles, indiquées par `stop_reason`** : soit Claude répond directement en texte (pas de tool nécessaire), soit `stop_reason == "tool_use"` et sa réponse contient un ou plusieurs blocs `tool_use`, chacun précisant `name` (quel tool), `input` (les paramètres, ex. `{"district": "Nord Est"}`) et un `id` unique identifiant cette demande.

4. **Exécution réelle de la fonction côté application** — dans `poser_question()`, les blocs `tool_use` sont lus et la fonction Python correspondante est appelée via la table de dispatch `FONCTIONS_TOOLS` (ex. `data_layer.get_kpis_par_district(district="Nord Est")`). Claude ne voit à aucun moment le code Python ni le DataFrame sous-jacent — il a seulement demandé l'exécution d'une fonction nommée avec des paramètres.

5. **Renvoi du résultat à Claude** — la valeur retournée par la fonction est sérialisée en JSON et renvoyée sous forme de bloc `tool_result`, portant le même `id` que la demande initiale de Claude, pour qu'il puisse faire la correspondance.

6. **Formulation de la réponse finale** — disposant désormais du résultat réellement calculé, Claude rédige une réponse en langage naturel à partir de cette donnée.

7. **Répétition possible de la boucle** — si Claude estime avoir besoin d'un appel supplémentaire pour compléter sa réponse, les étapes 3 à 6 se répètent ; c'est pour cette raison que `poser_question()` implémente une boucle `while True` qui continue tant que `stop_reason` vaut `"tool_use"`, et s'arrête dès que Claude répond sans redemander de tool.

## Exemple concret à inclure, tracé pas à pas

Pour la question « Combien d'équipements non couverts dans le district Nord Est ? » :

```
Claude lit la question + les six descriptions de tools
        ↓
Claude décide : get_kpis_par_district convient (et non get_kpis_par_site
ni get_top_sites — grâce aux descriptions qui désambiguïsent les tools proches)
        ↓
Claude renvoie : tool_use { name: "get_kpis_par_district",
                             input: {"district": "Nord Est"} }
        ↓
Le code exécute : data_layer.get_kpis_par_district(district="Nord Est")
        ↓
Résultat structuré : {"resume": "...", "districts": [...], "graphique": {...}}
        ↓
Renvoyé à Claude comme tool_result
        ↓
Claude rédige : "Dans le district Nord Est, il y a 4991 équipements
                 non couverts..."
```

## Point conceptuel clé à faire ressortir explicitement

Claude ne "connaît" jamais directement les données du projet : il choisit uniquement quelle fonction appeler et avec quels paramètres, sur la seule base des descriptions textuelles des tools. Toute la logique métier et le calcul réel résident dans le code Python (`data_layer.py`), jamais dans le modèle de langage lui-même — ce qui est cohérent avec, et renforce, l'argument déjà développé en 3.4.2 sur la fiabilité des chiffres et l'absence d'hallucination.

Garde un ton cohérent avec le reste du document (académique mais clair), et si un schéma existe déjà en 3.4.1, adapte cette explication pour qu'elle le complète sans le répéter mot pour mot.
