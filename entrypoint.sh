#!/bin/bash
# Script d'entrée: démarre Xvfb (display virtuel) puis lance l'application.
# Xvfb est requis car DataDome détecte le mode headless de Chromium.
# Avec un display virtuel, on peut lancer Chromium en mode headed.
#
# V2.1 — juillet 2026: cleanup des locks X11 et profil Chromium au démarrage
# pour éviter les crashes après un restart du conteneur.

set -e

# --- Nettoyage des locks X11 (si un précédent Xvfb n'a pas été tué proprement) ---
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99 2>/dev/null || true

# --- Nettoyage des locks de profil Chromium (évite "profile in use" après restart) ---
find /data/browser-profile -name "SingletonLock" -delete 2>/dev/null || true
find /data/browser-profile -name "SingletonSocket" -delete 2>/dev/null || true
find /data/browser-profile -name "SingletonCookie" -delete 2>/dev/null || true

# Démarre Xvfb en arrière-plan
export DISPLAY=:99
Xvfb :99 -screen 0 1920x1080x24 -nolisten -ac &
XVFB_PID=$!

# Attend que Xvfb soit prêt
sleep 1

# Lance la commande principale (CMD)
exec "$@"
