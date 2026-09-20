#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Génère le journal d'exécution réel de test_end_to_end.py, horodaté, pour
# l'Annexe C du mémoire (le mémoire y renvoie explicitement à un
# "emplacement réservé pour le journal d'exécution complet ... sortie
# console horodatée").
#
# À exécuter DANS le même dossier que assistant.py, data_layer.py,
# glossaire.py, app.py et test_end_to_end.py (l'environnement réel où le
# chatbot fonctionne, avec un accès réel au LLM — pas un mock).
#
# Usage :
#   chmod +x executer_test_end_to_end.sh
#   ./executer_test_end_to_end.sh
#
# Produit un fichier journal_execution_test_end_to_end.txt à côté du
# script, contenant l'horodatage de début, la sortie console complète et
# brute du script (le tableau des 20 scénarios + la ligne de synthèse), et
# l'horodatage de fin. C'est ce fichier qu'il faut renvoyer tel quel.
# ---------------------------------------------------------------------------
set -uo pipefail

OUT="journal_execution_test_end_to_end.txt"

if [ ! -f "test_end_to_end.py" ]; then
  echo "Erreur : test_end_to_end.py introuvable dans le dossier courant."
  echo "Lancez ce script depuis le dossier contenant assistant.py, data_layer.py, glossaire.py, app.py et test_end_to_end.py."
  exit 1
fi

PYTHON_BIN="python"
command -v python >/dev/null 2>&1 || PYTHON_BIN="python3"

{
  echo "=== Journal d'exécution réel — test_end_to_end.py ==="
  echo "Horodatage début : $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "Commande         : ${PYTHON_BIN} test_end_to_end.py"
  echo
  "${PYTHON_BIN}" test_end_to_end.py
  STATUT=$?
  echo
  echo "Code de sortie   : ${STATUT}"
  echo "Horodatage fin   : $(date '+%Y-%m-%d %H:%M:%S %Z')"
} | tee "${OUT}"

echo
echo "Journal enregistré dans : ${OUT}"
echo "Renvoyez ce fichier (ou son contenu copié-collé intégralement) pour intégration à l'Annexe C du mémoire."
