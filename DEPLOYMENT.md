# Déploiement — compta-ecom

## URLs de production

| Service | URL | Plateforme |
|---------|-----|------------|
| Backend API | `<YOUR-RENDER-URL>` | Render (Free) |
| Frontend Web | `<YOUR-VERCEL-URL>` | Vercel (Hobby) |

## Variables d'environnement

### Backend — Render

| Variable | Valeur | Description |
|----------|--------|-------------|
| `CORS_ORIGINS` | `<YOUR-VERCEL-URL>` | Domaine frontend autorisé (CORS). Plusieurs domaines séparés par virgule. |
| `CONFIG_DIR` | `./config` | Répertoire des fichiers YAML de configuration (optionnel, valeur par défaut). |

### Frontend — Vercel

| Variable | Valeur | Description |
|----------|--------|-------------|
| `NEXT_PUBLIC_API_URL` | `<YOUR-RENDER-URL>` | URL du backend. Injectée au build-time (préfixe `NEXT_PUBLIC_`). |

## Premier déploiement — Step by step

### 1. Backend sur Render

1. Créer un compte sur [render.com](https://render.com) et connecter le repository Git
2. Créer un **Web Service** avec :
   - **Name** : `compta-ecom-api` (ou nom de votre choix)
   - **Region** : Frankfurt (EU)
   - **Branch** : `main`
   - **Root Directory** : `compta-ecom`
   - **Runtime** : Docker
   - **Dockerfile Path** : `api/Dockerfile`
   - **Instance Type** : Free
   - **Health Check Path** : `/api/health`
3. Ajouter les variables d'environnement (voir tableau ci-dessus). `CORS_ORIGINS` sera mis à jour après le déploiement frontend.
4. Lancer le déploiement. Vérifier dans les logs :
   - Build Docker réussi
   - uvicorn démarre sur le port 8000
5. Tester : `curl <YOUR-RENDER-URL>/api/health` → `{"status":"ok"}`

### 2. Frontend sur Vercel

1. Créer un compte sur [vercel.com](https://vercel.com) et connecter le repository Git
2. Configurer le projet :
   - **Framework Preset** : Next.js (auto-détecté)
   - **Root Directory** : `compta-ecom/web`
   - **Build Command** : `npm run build`
   - **Node.js Version** : 20.x
3. Ajouter la variable d'environnement `NEXT_PUBLIC_API_URL` = `<YOUR-RENDER-URL>`
4. Lancer le déploiement. Vérifier que la page d'accueil s'affiche.

### 3. Mettre à jour CORS sur Render

1. Sur le dashboard Render, mettre à jour `CORS_ORIGINS` avec l'URL Vercel réelle (ex: `https://compta-ecom.vercel.app`)
2. Render redéploie automatiquement quand une variable d'environnement change

### 4. Smoke test

1. Ouvrir l'URL Vercel dans un navigateur
2. Glisser-déposer des fichiers CSV de test
3. Vérifier : résultats affichés, écritures, anomalies, tableau de bord
4. Télécharger Excel → vérifier 2 onglets (Écritures + Anomalies) avec données
5. Télécharger CSV → vérifier en-têtes et données dans les 2 fichiers
6. DevTools > Network : pas d'erreur CORS, preflight OPTIONS OK

## Re-déploiement

Push sur `main` → les deux plateformes détectent le changement et redéploient automatiquement.

**Attention** : `NEXT_PUBLIC_API_URL` est injectée au build-time. Si l'URL Render change, mettre à jour la variable sur Vercel et déclencher un re-build.

## Rollback

### Render
1. Dashboard → Service → Events
2. Cliquer sur un déploiement précédent → "Rollback to this deploy"

### Vercel
1. Dashboard → Deployments
2. Cliquer sur un déploiement précédent → "Promote to Production"

## Cold start

Le free tier Render met le service en veille après **15 minutes d'inactivité**. La première requête après cette période prend environ **30 secondes** (cold start).

- Le frontend affiche un spinner pendant l'attente
- Budget total (cold start + traitement) : < 60s (NFR12)
- Cold start mesuré : `<TO-MEASURE>` secondes

## Coût

**0 EUR/mois** — les deux services sont sur des tiers gratuits.

## Limites connues

| Limite | Service | Détail |
|--------|---------|--------|
| 512 MB RAM | Render Free | Suffisant pour ~400 transactions (~100-200 MB utilisés) |
| 750h/mois | Render Free | ~31 jours complets, mais cold start après 15 min d'inactivité |
| Cold start ~30s | Render Free | Première requête après inactivité |
| 100 GB bandwidth/mois | Vercel Hobby | Usage prévu négligeable (1 utilisateur, quelques sessions) |
| Pas d'authentification | MVP | URL = seule protection. Ne pas diffuser publiquement. |
