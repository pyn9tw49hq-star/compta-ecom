# Backend API — compta-ecom

API REST FastAPI pour le traitement comptable e-commerce.

## URL de production

`<YOUR-RENDER-URL>` (ex: `https://compta-ecom-api.onrender.com`)

## Déploiement Render

### Prérequis

- Compte Render (tier Free)
- Repository Git connecté

### Configuration du service

| Paramètre | Valeur |
|-----------|--------|
| Type | Web Service (Docker) |
| Region | Frankfurt (EU) |
| Branch | `main` |
| Root Directory | `compta-ecom` |
| Dockerfile Path | `api/Dockerfile` |
| Instance | Free (512 MB RAM, shared CPU, 750h/mois) |
| Health Check Path | `/api/health` |

### Variables d'environnement

| Variable | Description | Valeur production |
|----------|-------------|-------------------|
| `CORS_ORIGINS` | Origines autorisées (séparées par virgule) | `<YOUR-VERCEL-URL>` |
| `CONFIG_DIR` | Répertoire des fichiers YAML | `./config` (défaut) |

### Re-déploiement

Push sur `main` → Render détecte le changement et redéploie automatiquement.

### Rollback

1. Aller sur le dashboard Render → Service → Events
2. Cliquer sur un déploiement précédent
3. Sélectionner "Rollback to this deploy"

### Cold start

Le free tier Render met le service en veille après 15 minutes d'inactivité. La première requête après cette période prend ~30s (cold start). Le health check `/api/health` est la première requête à aboutir.

## Développement local

```bash
# Depuis la racine compta-ecom/
pip install -e .
pip install -r api/requirements.txt
uvicorn api.app.main:app --reload --port 8000
```

## Build Docker local

```bash
# Depuis la racine compta-ecom/
docker build -f api/Dockerfile -t compta-ecom-api .
docker run -p 8000:8000 compta-ecom-api
curl http://localhost:8000/api/health
# → {"status":"ok"}
```

## Endpoints

| Méthode | URL | Description |
|---------|-----|-------------|
| `GET` | `/api/health` | Health check → `{"status": "ok"}` |
| `POST` | `/api/process` | Upload CSV → JSON (entries, anomalies, summary) |
| `POST` | `/api/download/excel` | Upload CSV → fichier .xlsx |
