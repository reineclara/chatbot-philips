# Script de démo — soutenance

## Avant de commencer (checklist)

- [ ] Lancer l'app **15-20 minutes avant** ton passage et ouvrir la page une fois toi-même (pré-chauffe le cache Excel, sinon la 1ère question de quelqu'un d'autre prendrait ~40s).
- [ ] Vérifier la connexion internet (l'app appelle l'API Claude en direct — sans réseau, rien ne fonctionne).
- [ ] Avoir le dashboard Power BI ouvert dans un onglet, et l'app Streamlit dans un **autre onglet à côté** (voir note ci-dessous sur l'intégration).
- [ ] Fermer les autres apps/onglets qui pourraient ralentir la machine ou distraire.
- [ ] Avoir ce fichier ouvert sur un second écran ou imprimé, pour suivre le script sans stresser.

**Décision finale sur l'intégration Power BI** : après plusieurs tests (Jour 8, puis reprise du 19/07), l'intégration directe dans un visuel Power BI n'est pas retenue — les visuels gratuits (HTML Content, Shielded HTML Viewer en version d'essai) ne peuvent pas exécuter l'application JavaScript de Streamlit (limitation de sécurité de la plateforme, pas un problème de configuration ; une vraie solution existerait mais est payante). L'app se montre donc dans un **onglet de navigateur séparé, à côté du dashboard Power BI**. Devant le jury, présente ça comme un choix assumé : la technique d'exposition (tunnel + visuel externe) a été testée et documentée, la limitation identifiée est celle de l'écosystème de visuels gratuits Power BI, pas de l'assistant lui-même.

---

## Les 2-3 questions à poser en live (répétées à l'avance)

Choisies pour montrer les trois capacités clés de l'assistant en un minimum de questions.

### 1. Une question pédagogique (montre le glossaire)
> **"Qu'est-ce qu'un équipement couvert ?"**

Réponse attendue : explication simple des 3 types de couverture (garantie constructeur, extension, contrat SAP), sans appel de tool. Montre que l'assistant peut expliquer le dashboard à quelqu'un de non technique.

### 2. Une question chiffrée avec graphique (montre le tool-calling + Plotly)
> **"Quel site a le plus d'équipements non couverts ?"**

Réponse attendue : le nom du site + un graphique en barres Philips. Montre que les chiffres viennent d'un vrai calcul (pas d'hallucination) et que le rendu visuel fonctionne.

### 3. Une question de suivi (montre le multi-tours)
> **"Et le deuxième ?"** ou **"Et dans le district [X] ?"**

Réponse attendue : l'assistant comprend qu'on continue sur le même sujet sans qu'on répète tout. Montre la mémoire conversationnelle.

*(Optionnel, si le temps le permet)* une question hors périmètre pour montrer les garde-fous :
> **"Quel médicament dois-je administrer à ce patient ?"** → doit décliner poliment.

---

## Si quelque chose plante en direct

- **Erreur API / lenteur** : rester calme, dire "je vais montrer une capture d'écran de cet échange" et passer aux captures de secours (voir plus bas).
- **Pas de réseau** : passer directement aux captures de secours.
- **Le graphique ne s'affiche pas** : ce n'est pas grave, la réponse texte contient déjà le chiffre — continuer normalement.

## Captures d'écran de secours (à préparer avant le jour J)

Ouvre l'app toi-même et prends une capture d'écran (question + réponse + graphique visible) pour chacune des 3 questions ci-dessus, et mets-les dans un dossier `captures_secours/` ou une slide dédiée. Si le direct plante, tu montres ces captures à la place — le jury voit quand même que ça fonctionne.
