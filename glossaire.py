"""
Jour 4 : glossaire / FAQ pédagogique.

Questions récurrentes des utilisateurs non-techniques du dashboard (commerciaux,
responsables de district, managers), avec des réponses courtes en langage simple.
Injecté tel quel comme bloc de texte dans le system prompt de l'assistant — pas
besoin de recherche vectorielle vu la taille réduite du contenu.
"""

GLOSSAIRE = """
Q: Qu'est-ce qu'un équipement "couvert" ?
R: Un équipement est couvert quand il bénéficie d'au moins une des trois protections suivantes : la garantie constructeur, une extension de garantie, ou un contrat de maintenance SAP actif. Tant qu'une de ces trois couvertures est active, l'équipement est "couvert".

Q: Qu'est-ce que la "Garantie constructeur" ?
R: C'est la couverture donnée automatiquement par Philips à l'achat de l'équipement, sans contrat à signer. Elle dure jusqu'à une date appelée DFG (date de fin de garantie).

Q: Qu'est-ce qu'une "Extension de garantie" ?
R: C'est une prolongation de la garantie constructeur au-delà de sa date de fin initiale. C'est un contrat SAP de type "non billable" (gratuit), avec une date de début et de fin.

Q: Qu'est-ce qu'un "Contrat de maintenance SAP" ?
R: C'est un contrat commercial payant signé entre Philips et l'hôpital pour assurer la maintenance de l'équipement. Dans les données, c'est un contrat SAP de type "billable".

Q: Que signifie "Non couvert" ?
R: L'équipement n'a aucune des trois couvertures actives (ni garantie constructeur en cours, ni extension, ni contrat SAP en cours). Il n'y a donc aucune maintenance garantie par Philips sur cet équipement en ce moment.

Q: Que signifie "Hors contrat" ?
R: C'est la même idée que "Non couvert" : l'équipement n'a pas de contrat de maintenance actif. C'est le terme utilisé dans la colonne "Situation Contrat" du dashboard.

Q: Qu'est-ce que le "DFG" ?
R: DFG veut dire "Date de Fin de Garantie". C'est la date à laquelle la garantie constructeur (gratuite, automatique) se termine pour un équipement donné.

Q: Que signifie "BILLABLE" et "NON BILLABLE" ?
R: Ce sont deux types de contrats SAP. "BILLABLE" veut dire que l'hôpital paie pour ce contrat (contrat de maintenance classique). "NON BILLABLE" veut dire que c'est gratuit — c'est le cas des extensions de garantie.

Q: Qu'est-ce qu'un "District SFDC" ?
R: C'est la zone commerciale Philips à laquelle est rattaché un site hospitalier (par exemple "Nord Est" ou "Sud Ouest"). SFDC est le nom du système commercial dans lequel ces districts sont définis.

Q: Qu'est-ce que "SH Name" ?
R: C'est le nom du site hospitalier (par exemple "CHU AMIENS" ou "CHRU BREST") où l'équipement est installé.

Q: Comment lire le graphique "Répartition par type de couverture" ?
R: C'est un graphique en barres qui montre, pour l'ensemble du parc, combien d'équipements sont dans chaque catégorie : Garantie constructeur, Extension de garantie, Sous contrat, ou Non couvert. Plus la barre "Non couvert" est haute, plus il y a d'équipements à risque sans maintenance.

Q: Comment lire le graphique par district ?
R: C'est un graphique en barres groupées : pour chaque district, deux barres côte à côte montrent le nombre d'équipements couverts et le nombre d'équipements non couverts. Ça permet de comparer rapidement les districts entre eux.

Q: Comment lire le classement "Top 10 des sites" ?
R: Ce graphique classe les sites hospitaliers du plus grand au plus petit nombre d'équipements couverts (ou non couverts, selon le critère choisi). Le site en haut de la liste est celui qui a le plus d'équipements dans la catégorie sélectionnée.

Q: Comment lire le graphique d'anticipation par mois ?
R: Ce graphique montre, mois par mois, combien d'équipements vont sortir de leur couverture actuelle (fin de garantie, d'extension ou de contrat). Les mois avec une barre haute sont des périodes à anticiper commercialement, car beaucoup d'équipements vont devenir "non couverts" si rien n'est fait.

Q: Comment utiliser le filtre par district ou par site dans le dashboard ?
R: Il suffit de cliquer sur la valeur souhaitée (un district ou un nom de site) dans un des visuels ou dans le panneau de filtres à gauche du dashboard Power BI. Tous les graphiques et chiffres de la page se recalculent alors automatiquement sur cette sélection. Un second clic sur la même valeur retire le filtre.

Q: Comment exporter les données d'un tableau ou d'un graphique Power BI ?
R: Il faut survoler le visuel, cliquer sur les trois petits points "..." qui apparaissent en haut à droite, puis choisir "Exporter les données". Power BI propose ensuite un export au format Excel ou CSV.

Q: À quelle fréquence les données du dashboard sont-elles mises à jour ?
R: Les données viennent d'un export Excel qui est actualisé tous les trimestres (tous les 3 mois). Les chiffres du dashboard reflètent donc la situation au moment du dernier export, pas en temps réel.

Q: Que faire si un site apparaît "100% hors contrat" ?
R: Ça veut dire qu'aucun équipement de ce site n'a de couverture active en ce moment. C'est un signal à remonter à l'équipe commerciale du district concerné, car ce site représente une opportunité de vente de contrats ou d'extensions de garantie.
""".strip()
