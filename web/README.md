# Frontend Web — compta-ecom

Interface web Next.js pour le traitement comptable e-commerce.

## URL de production

`<YOUR-VERCEL-URL>` (ex: `https://compta-ecom.vercel.app`)

## Déploiement Vercel

### Prérequis

- Compte Vercel (tier Hobby/Free)
- Repository Git connecté

### Configuration du projet

| Paramètre | Valeur |
|-----------|--------|
| Framework Preset | Next.js (auto-détecté) |
| Root Directory | `compta-ecom/web` |
| Build Command | `npm run build` |
| Output Directory | `.next` (défaut Next.js) |
| Node.js Version | 20.x (LTS — Node 18 est EOL depuis avril 2025) |

### Variable d'environnement

| Variable | Description | Valeur production |
|----------|-------------|-------------------|
| `NEXT_PUBLIC_API_URL` | URL du backend Render | `<YOUR-RENDER-URL>` |

En développement local, cette variable n'est pas définie — le fallback `http://localhost:8000` dans `src/lib/api.ts` est utilisé automatiquement.

### Re-déploiement

Push sur `main` → Vercel détecte le changement et redéploie automatiquement.

**Important** : `NEXT_PUBLIC_API_URL` est injectée au **build-time** par Next.js (préfixe `NEXT_PUBLIC_`). Si la valeur change, un re-build est nécessaire.

## Développement local

```bash
npm install
npm run dev
# → http://localhost:3000
```

Le backend doit tourner en parallèle sur `http://localhost:8000`.

## Tests

```bash
npx vitest run        # 105 tests
npm run build         # Build production (0 erreur)
npm run lint          # ESLint (0 erreur)
```

## Stack

- Next.js 14 (App Router)
- TypeScript 5 (strict mode)
- TailwindCSS 3
- shadcn/ui (composants copiés)
