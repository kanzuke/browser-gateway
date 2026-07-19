#!/bin/bash
# Script d'entrée: démarre Xvfb (display virtuel) puis lance l'application.
# Xvfb est requis car DataDome détecte le mode headless de Chromium.
# Avec un display virtuel, on peut lancer Chromium en mode headed (new headless = headed).

set -e

# Démarre Xvfb en arrière-plan
export DISPLAY=:99
Xvfb :99 -screen 0 1920x1080x24 -nolisten -ac &
XVFB_PID=$!

# Attend que Xvfb soit prêt
sleep 1

# Lance la commande principale (CMD)
exec "$@"
