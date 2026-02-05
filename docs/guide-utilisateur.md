# Guide Utilisateur — compta-ecom

Outil de Génération d'Écritures Comptables E-commerce Multi-canal.

---

## 1. Qu'est-ce que compta-ecom ?

compta-ecom est un outil en ligne de commande qui automatise la génération des écritures comptables à partir des exports CSV de vos canaux de vente :

- **Shopify** (avec paiements Stripe, PayPal, Klarna)
- **ManoMano**
- **Décathlon**
- **Leroy Merlin**

Il produit un fichier Excel (.xlsx) avec deux onglets :

- **Écritures** : toutes les écritures comptables (vente, règlement/commission, reversement), prêtes à copier-coller dans ACD ou Pennylane
- **Anomalies** : les incohérences détectées (TVA, matching, écarts de montants)

---

## 2. Prérequis

- Python 3.11 ou supérieur installé sur votre machine
- Les fichiers CSV exportés depuis chaque plateforme

### Installation

```bash
# Depuis le répertoire du projet
pip install -e .
```

Pour vérifier que l'installation est correcte :

```bash
compta-ecom --help
```

---

## 3. Préparer vos fichiers CSV

### Principe

Déposez tous vos fichiers CSV du mois dans un **seul répertoire**. L'outil détecte automatiquement quel fichier correspond à quel canal grâce aux noms de fichiers.

### Nommage des fichiers attendu

Le nommage doit correspondre aux patterns configurés. Par défaut :

| Canal | Fichier(s) attendu(s) | Séparateur |
|-------|----------------------|------------|
| Shopify — Ventes | `Ventes Shopify*.csv` | Virgule (,) |
| Shopify — Transactions | `Transactions Shopify*.csv` | Virgule (,) |
| Shopify — Versements PSP | `Détails versements*.csv` | Virgule (,) |
| Shopify — Detail transactions (optionnel) | `Detail transactions par versements/*.csv` | Virgule (,) |
| ManoMano — CA | `CA Manomano*.csv` | Point-virgule (;) |
| ManoMano — Versements | `Detail versement Manomano*.csv` | Point-virgule (;) |
| Décathlon | `Decathlon*.csv` | Point-virgule (;) |
| Leroy Merlin | `Leroy Merlin*.csv` | Point-virgule (;) |

Le `*` signifie que le nom peut contenir une suite quelconque (date, suffixe, etc.). Par exemple :
- `Ventes Shopify janvier 2026.csv` correspond au pattern `Ventes Shopify*.csv`
- `CA Manomano 2026-01.csv` correspond au pattern `CA Manomano*.csv`

### Fichiers Shopify (3 fichiers requis + 1 optionnel)

Pour que le canal Shopify soit traité, les **3 fichiers** doivent être présents :

1. **Ventes** : exporté depuis Shopify Admin > Commandes > Exporter
2. **Transactions** : exporté depuis Shopify Admin > Finances > Transactions
3. **Versements PSP** : exporté depuis Shopify Admin > Finances > Versements

Optionnel — pour le lettrage par commande sur le compte 511 :

4. **Detail transactions par versement** : un fichier CSV par versement, déposé dans le sous-dossier `Detail transactions par versements/`. Chaque fichier contient le détail des transactions composant un versement, ce qui permet de ventiler les écritures de reversement (compte 511) commande par commande au lieu d'un montant agrégé par versement. Si ces fichiers sont absents, le traitement fonctionne normalement en mode agrégé (comportement identique à avant).

### Fichiers ManoMano (2 fichiers requis)

1. **CA** : rapport de chiffre d'affaires depuis le back-office ManoMano
2. **Versements** : détail des versements depuis le back-office ManoMano

### Fichiers Décathlon / Leroy Merlin (1 fichier chacun)

Un seul fichier par marketplace, contenant à la fois les ventes et les reversements (export Mirakl).

### Ce qui se passe si un fichier manque

- Si un fichier est manquant pour un canal, le canal est ignoré avec un message d'erreur dans le résumé
- Les autres canaux sont traités normalement
- Si **aucun** fichier n'est trouvé, l'outil s'arrête avec un message explicite

---

## 4. Exécuter l'outil

### Commande de base

```bash
compta-ecom ./input/ ./output/ecritures_janvier_2026.xlsx
```

- `./input/` : le répertoire contenant vos fichiers CSV
- `./output/ecritures_janvier_2026.xlsx` : le fichier Excel de sortie (créé automatiquement)

### Options disponibles

| Option | Défaut | Description |
|--------|--------|-------------|
| `--config-dir` | `./config/` | Répertoire contenant les fichiers de configuration YAML |
| `--log-level` | `INFO` | Niveau de détail des logs : `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Exemples

```bash
# Traitement standard
compta-ecom ./csv_janvier/ ./sortie/compta_2026-01.xlsx

# Avec logs détaillés (utile pour diagnostiquer un problème)
compta-ecom ./csv_janvier/ ./sortie/compta_2026-01.xlsx --log-level DEBUG

# Avec un dossier de configuration personnalisé
compta-ecom ./csv_janvier/ ./sortie/compta_2026-01.xlsx --config-dir ./ma_config/
```

### Codes de sortie

| Code | Signification |
|------|---------------|
| 0 | Succès — fichier Excel produit (même s'il y a des anomalies, elles sont dans l'Excel) |
| 1 | Erreur inattendue — consulter les logs |
| 2 | Erreur de configuration — vérifier les fichiers YAML dans `config/` |
| 3 | Aucun résultat — aucun canal n'a pu être traité, vérifier les fichiers CSV |

---

## 5. Comprendre le fichier Excel de sortie

### Onglet "Écritures"

Chaque ligne est une écriture comptable individuelle (une ligne = un débit ou un crédit).

| Colonne | Description |
|---------|-------------|
| `date` | Date de l'écriture (date de commande pour vente/règlement, date de payout pour reversement) |
| `journal` | Code journal (ex: `VE` pour ventes, `BQ` pour banque) |
| `account` | Numéro de compte (ex: `411SHOPIFY`, `70701250`, `4457250`) |
| `label` | Libellé de l'écriture |
| `debit` | Montant au débit (0.00 si crédit) |
| `credit` | Montant au crédit (0.00 si débit) |
| `piece_number` | Numéro de pièce = référence commande du fichier source |
| `lettrage` | Référence de lettrage — toutes les écritures d'une même commande partagent le même lettrage |
| `channel` | Canal source (`shopify`, `manomano`, `decathlon`, `leroy_merlin`) |
| `entry_type` | Type d'écriture : `sale`, `refund`, `settlement`, `commission`, `payout` |

### Comment copier dans ACD / Pennylane

1. Ouvrez le fichier Excel
2. Sélectionnez les colonnes pertinentes pour votre logiciel (typiquement : date, journal, compte, libellé, débit, crédit, pièce, lettrage)
3. Copier-coller dans le module d'import de votre logiciel comptable
4. Les colonnes `channel` et `entry_type` sont informatives — elles vous aident à filtrer mais ne sont pas nécessaires à l'import

### Onglet "Anomalies"

Liste les incohérences détectées pendant le traitement. **Les anomalies ne bloquent pas la génération des écritures** — elles sont signalées pour que vous puissiez les vérifier.

| Colonne | Description |
|---------|-------------|
| `type` | Type d'anomalie (voir tableau ci-dessous) |
| `severity` | `error`, `warning`, ou `info` |
| `reference` | Référence de la commande concernée |
| `channel` | Canal source |
| `detail` | Description détaillée |
| `expected_value` | Valeur attendue (si applicable) |
| `actual_value` | Valeur trouvée (si applicable) |

### Types d'anomalies

| Type | Sévérité | Signification | Action recommandée |
|------|----------|---------------|-------------------|
| `tva_mismatch` | warning | Le taux de TVA appliqué ne correspond pas au pays de livraison | Vérifier la commande dans la plateforme source |
| `amount_mismatch` | warning | Écart entre le montant de la vente et du règlement (> 0.01 EUR) | Vérifier s'il y a un remboursement partiel ou un ajustement |
| `orphan_refund` | warning | Remboursement sans vente correspondante | Vérifier que la vente d'origine est dans les fichiers |
| `unknown_country` | warning | Pays de livraison non reconnu dans la table TVA | Ajouter le pays dans `config/vat_table.yaml` |
| `missing_payout` | info | Transaction sans date de reversement | Normal en cours de mois — le reversement n'a pas encore eu lieu |
| `payout_detail_mismatch` | error | La somme des nets du fichier detail ne correspond pas au total du versement | Vérifier le fichier detail et le fichier versements PSP pour ce payout |
| `payout_missing_details` | warning | Versement sans fichier detail correspondant (mode agrégé utilisé) | Fournir le fichier detail ou ignorer si le mode agrégé est acceptable |
| `orphan_payout_detail` | warning | Fichier detail dont le Payout ID ne correspond à aucun versement | Vérifier que le fichier Détails versements couvre la même période |
| `unknown_psp_detail` | warning | Ligne detail sans méthode de paiement identifiable | Vérifier la colonne Payment Method Name dans le fichier detail |

Les anomalies `info` (notamment `missing_payout`) sont normales et attendues si vous traitez des données en cours de mois.

---

## 6. Personnaliser la configuration

Les fichiers de configuration se trouvent dans le répertoire `config/`. Ce sont des fichiers YAML modifiables avec un éditeur de texte.

### `config/chart_of_accounts.yaml` — Plan comptable

Contient les numéros de compte utilisés pour chaque canal.

**Quand le modifier :**
- Si vos numéros de compte clients (411) ou fournisseurs (401) diffèrent
- Si vous ajoutez un nouveau canal de vente

### `config/vat_table.yaml` — Table TVA/pays

Contient les taux de TVA standard par pays (code ISO 3166-1 numérique).

**Quand le modifier :**
- Si vous vendez dans un pays non encore présent dans la table
- Si un taux de TVA change dans un pays

Exemple pour ajouter un pays :

```yaml
countries:
  # ... pays existants ...
  "826":
    name: "Royaume-Uni"
    rate: 20.0
    alpha2: "GB"
```

Le code numérique ISO est celui utilisé par vos fichiers CSV pour identifier le pays. Vous pouvez trouver les codes sur [Wikipedia — ISO 3166-1 numérique](https://fr.wikipedia.org/wiki/ISO_3166-1_num%C3%A9rique).

### `config/channels.yaml` — Paramètres des canaux

Définit les patterns de noms de fichiers, l'encodage et le séparateur CSV pour chaque canal.

**Quand le modifier :**
- Si les noms de vos fichiers CSV ne correspondent pas aux patterns par défaut
- Si l'encodage de vos fichiers est différent (ex: `latin-1` au lieu de `utf-8`)

Encodages supportés : `utf-8`, `utf-8-sig`, `latin-1`, `iso-8859-1`.

---

## 7. Comprendre le résumé console

Après chaque exécution, un résumé s'affiche dans le terminal :

```
=== Résumé ===
Transactions traitées : 85
  decathlon : 25
  manomano : 18
  shopify : 42
Écritures générées : 231
  commission : 43
  payout : 6
  refund : 12
  sale : 85
  settlement : 85
Anomalies : 7 warning/error, 5 info
  Par type :
    tva_mismatch        : 3
    amount_mismatch     : 2
    orphan_refund       : 1
    unknown_country     : 1
    missing_payout      : 5  (info)
  Par canal :
    shopify             : 7
    manomano            : 3
    decathlon           : 2
```

**Points clés :**
- Le total d'anomalies distingue les `warning/error` (à vérifier) des `info` (informatif)
- Les `missing_payout` marquées `(info)` sont normales en cours de mois
- Si un canal est en erreur (fichier manquant ou malformé), il apparaît dans "Canaux en erreur"

---

## 8. Cas d'usage courant — Clôture mensuelle

1. **Exporter** les fichiers CSV depuis chaque plateforme pour le mois à clôturer
2. **Renommer** les fichiers si nécessaire pour qu'ils correspondent aux patterns attendus (voir Section 3)
3. **Déposer** tous les fichiers dans un même répertoire (ex: `./csv_janvier/`)
4. **Exécuter** la commande :
   ```bash
   compta-ecom ./csv_janvier/ ./sortie/compta_2026-01.xlsx
   ```
5. **Vérifier le résumé** console : nombre de transactions, anomalies détectées
6. **Ouvrir** le fichier Excel et inspecter l'onglet Anomalies
7. **Traiter les anomalies** warning/error manuellement si nécessaire
8. **Copier-coller** l'onglet Écritures dans ACD ou Pennylane

---

## 9. Dépannage

| Problème | Cause probable | Solution |
|----------|---------------|----------|
| Code de sortie 2 | Fichier de configuration YAML invalide | Vérifier la syntaxe des fichiers dans `config/` |
| Code de sortie 3 | Aucun fichier CSV reconnu | Vérifier le nommage des fichiers (voir Section 3) |
| Canal absent du résumé | Fichiers manquants ou mal nommés pour ce canal | Vérifier que tous les fichiers requis sont présents |
| `unknown_country` | Pays absent de la table TVA | Ajouter le pays dans `config/vat_table.yaml` |
| `tva_mismatch` | Taux TVA dans le CSV différent du taux dans la config | Vérifier la commande source ou mettre à jour la table TVA |
| Beaucoup de `missing_payout` | Traitement en cours de mois | Normal — les reversements n'ont pas encore eu lieu |
| Erreur d'encodage | Fichier CSV avec encodage inattendu | Modifier `encoding` dans `config/channels.yaml` |

Pour un diagnostic détaillé, relancez avec `--log-level DEBUG` :

```bash
compta-ecom ./csv_janvier/ ./sortie/compta_2026-01.xlsx --log-level DEBUG
```

---

## 10. Référence rapide — Plan comptable

### Comptes clients (411)

| Compte | Canal |
|--------|-------|
| 411SHOPIFY | Shopify |
| 411MANO | ManoMano |
| CDECATHLON | Décathlon |
| 411LM | Leroy Merlin |

### Comptes fournisseurs (401)

| Compte | Marketplace |
|--------|------------|
| FMANO | ManoMano |
| FDECATHLON | Décathlon |
| FADEO | Leroy Merlin (ADEO) |

### Comptes PSP

| Compte | PSP | Commission associée |
|--------|-----|-------------------|
| 51150007 | Stripe | 62700002 |
| 51150004 | PayPal | 62700001 |
| 51150011 | Klarna | 62700003 |

### Comptes de vente (707) — dynamiques

Format : `707XXYYYY` avec XX = code canal, YYYY = code pays ISO numérique.

| Code canal | Canal |
|------------|-------|
| 01 | Shopify |
| 02 | ManoMano |
| 03 | Décathlon |
| 04 | Leroy Merlin |

Exemple : `70701250` = Vente Shopify, France.

### Comptes TVA (4457) — dynamiques

Format : `4457YYY` avec YYY = code pays ISO numérique.

Exemple : `4457250` = TVA collectée, France.

---

*Document rédigé le 31/01/2026, mis à jour le 02/02/2026 — Version 1.1*
*Source : PRD v4, Architecture v1.0, Brief v2.0*
