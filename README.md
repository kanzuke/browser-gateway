# Browser Gateway

Microservice FastAPI + Playwright pour le contournement de protections anti-bot
(DataDome, Cloudflare, PerimeterX, Akamai).

## Déploiement

```bash
# Build et démarrage
docker compose up -d

# Vérifier l'état
curl http://127.0.0.1:8000/health
```

Le conteneur démarre avec:
- `restart: always` — survit aux redémarrages du VPS
- Xvfb (display virtuel :99) — Chromium en mode headed (requis par DataDome)
- Volume persistant `/data` — profil Chromium conservé entre redémarrages
- `BROWSER_HEADLESS=false` + `BROWSER_USER_AGENT` Windows Chrome 131

## API REST

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/health` | État du service |
| GET | `/identity` | Identité du navigateur (score, état, métriques) |
| POST | `/warmup` | Pré-chauffe un domaine (`{"domain": "..."}`) |
| POST | `/fetch` | Charge une URL (`{"url": "...", "wait": N}`) |
| POST | `/screenshot` | Capture d'écran (`{"url": "...", "full_page": true}`) |

## Architecture

```
FastAPI → BrowserService → BrowserIdentity → BrowserManager → Playwright/Chromium
                           ├── DomainSession (1 par domaine, onglet persistant)
                           ├── IdentityPolicy (scores, seuils, rotation)
                           ├── IdentityHistory (deque limitée)
                           ├── IdentityMetrics (compteurs)
                           └── ProtectionDetector (DataDome/Cloudflare/PX/Akamai)
```

Le `PageController.navigate()` inclut un solveur de captcha DataDome automatique:
- Détection de l'iframe `DataDome CAPTCHA`
- Localisation du slider `.slider`
- Simulation de glissement humain (courbe de Bézier, jitter, overshoot)
- Vérification du résultat (`slider-success` / `slider-error`)

## Contournement DataDome

Le solveur de captcha slider fonctionne (le slider est résolu en `slider-success`),
mais DataDome bloque au niveau IP sur les IP de datacenter (OVH, AWS, etc.).

**Pour un bypass complet**, il faut ajouter un proxy résidentiel:

1. Configurer un proxy SOCKS5/HTTP résidentiel dans `docker-compose.yml`:
   ```yaml
   environment:
     - HTTPS_PROXY=socks5://user:pass@proxy-host:port
   ```
   ou via les args de launch de Chromium dans `browser_manager.py`.

2. Avec une IP résidentielle, le navigateur headed + stealth + captcha solver
   devrait passer DataDome complètement.

## Intégration Spoty

Le module `post_to_nc_tables.py` de Spoty peut utiliser le browser-gateway pour
scrapper La Centrale:

```python
import requests

# 1. Warmup du domaine
requests.post("http://127.0.0.1:8000/warmup",
              json={"domain": "www.lacentrale.fr"})

# 2. Fetch avec solveur de captcha automatique
resp = requests.post("http://127.0.0.1:8000/fetch",
                    json={"url": search_url, "wait": 15})
data = resp.json()
html = data["html"]

# 3. Parser le HTML avec BeautifulSoup
from bs4 import BeautifulSoup
soup = BeautifulSoup(html, "html.parser")
# Extraire les annonces...
```

## Fichiers

- `app/main.py` — FastAPI app + lifespan
- `app/api/routes.py` — 5 endpoints REST
- `app/services/browser_service.py` — orchestration
- `app/browser/browser_identity.py` — cœur métier (scores, rotation)
- `app/browser/browser_manager.py` — gestion Chromium + Xvfb + stealth
- `app/browser/page_controller.py` — navigation + solveur DataDome
- `app/browser/protection_detector.py` — détection anti-bot
- `app/browser/stealth.py` — scripts JS anti-détection
- `app/config/settings.py` — configuration Pydantic Settings
- `Dockerfile` — image Python 3.13 + Playwright + Xvfb
- `docker-compose.yml` — déploiement permanent
