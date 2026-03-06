# Gabarit d'ecritures comptables par canal

Ce document decrit les schemas d'ecritures comptables generes par MAPP E-COMMERCE pour chaque canal de vente. Chaque ecriture est equilibree (total debits = total credits) et identifiee par un journal, un numero de piece et un code lettrage pour le rapprochement.

---

## Sommaire

1. [Shopify](#1-shopify)
2. [ManoMano](#2-manomano)
3. [Decathlon](#3-decathlon)
4. [Leroy Merlin](#4-leroy-merlin)
5. [Annexe : Plan comptable par defaut](#5-annexe--plan-comptable-par-defaut)

---

## 1. Shopify

### 1.1 Ecritures de vente (Journal VE)

Generees pour chaque commande Shopify (vente ou avoir).

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| VE | 411SHOPIFY | Client Shopify | TTC | | Ref commande |
| VE | 70701xxxx | Vente produit HT (par pays) | | HT | |
| VE | 708501xxxx | Port HT (par zone geo) | | Port HT | |
| VE | 4457xxxx | TVA collectee (par pays) | | TVA | |

**Notes :**
- Le compte de vente `707` est suffixe du code canal `01` (Shopify) et du code pays ISO.
- Le compte de port `7085` est suffixe du code canal et de la zone geographique (`00` France, `01` Hors UE, `02` UE).
- Le compte TVA `4457` est suffixe du code pays.
- Les lignes port et TVA sont omises si leur montant est nul (ex : vente hors UE sans TVA).
- Pour un avoir (remboursement), les sens debit/credit sont inverses et le numero de piece est suffixe par `A` (ex : `#1234A`).

### 1.2 Ecritures de commission PSP (Journal AC)

Generees pour chaque transaction de reglement PSP. Le schema depend de la methode de paiement.

#### 1.2.1 Card et PayPal (avec compte intermediaire 46710001)

Ces methodes utilisent un compte intermediaire car les fonds transitent par un compte de regroupement avant le reversement.

**Paire 1 — Reglement (Journal RG) :**

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| RG | 46710001 | Compte intermediaire PSP | TTC | | Ref payout |
| RG | 411SHOPIFY | Client Shopify | | TTC | Ref commande |

**Paire 2 — Commission (Journal AC) :**

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| AC | 62700002 (card) ou 62700001 (paypal) | Commission PSP | Commission | | |
| AC | 46710001 | Compte intermediaire PSP | | Commission | Ref payout |

**Notes :**
- Le TTC de la paire 1 correspond au montant net + commission.
- La paire 1 est omise si le TTC est nul ; la paire 2 est omise si la commission est nulle.
- Pour un remboursement, les sens sont inverses.

#### 1.2.2 Klarna (sans compte intermediaire)

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| RG | 51150011 | Compte bancaire Klarna | Net | | Ref payout |
| AC | 62700003 | Commission Klarna | Commission | | |
| RG | 411SHOPIFY | Client Shopify (net) | | Net | Ref commande |
| AC | 411SHOPIFY | Client Shopify (commission) | | Commission | Ref commande |

**Note :** Le compte client est splitte entre les journaux RG et AC pour maintenir l'equilibre de chaque journal.

### 1.3 Ecritures de paiement direct (Journal RG)

Pour les methodes de paiement sans PSP (Klarna direct, Bank Deposit).

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| RG | 46740000 (Klarna) ou 58010000 (Bank Deposit) | Compte paiement direct | TTC | | |
| RG | 411SHOPIFY | Client Shopify | | TTC | Ref commande |

### 1.4 Ecritures de reversement PSP (Journal RG)

Generees a partir des versements agreges (PayoutSummary).

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| RG | 58000000 | Compte de transit | Montant | | |
| RG | 46710001 (card/paypal) ou 51150011 (klarna) | Compte PSP | | Montant | Ref payout |

**Notes :**
- Pour card et paypal, le compte de reversement est le compte intermediaire `46710001`.
- Pour klarna, c'est le compte bancaire `51150011`.
- En cas de versement multi-PSP, une paire d'ecritures est generee par moyen de paiement.

---

## 2. ManoMano

### 2.1 Ecritures de vente (Journal MM)

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| MM | 46720000 | Client ManoMano | TTC | | Ref payout (*) |
| MM | 70702xxxx | Vente produit HT (par pays) | | HT | |
| MM | 708502xxxx | Port HT (par zone geo) | | Port HT | |
| MM | 4457xxxx | TVA collectee (par pays) | | TVA | |

(*) **Lettrage :** Le compte client est lettre par `payout_reference` (reference du cycle de versement) pour permettre le rapprochement avec le reversement. Les commandes non encore reversees ont un lettrage vide.

**Notes :**
- Le code canal ManoMano est `02`.
- Pour un avoir, les sens sont inverses.

### 2.2 Ecritures de commission marketplace (Journal AC)

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| AC | 62220300 | Commission ManoMano HT | Commission HT | | |
| AC | 44566001 | TVA deductible | TVA deductible | | |
| AC | 46720000 | Client ManoMano | | Commission TTC | Ref payout |

**Notes :**
- ManoMano fournit le detail HT/TVA des commissions, ce qui permet l'eclatement en 3 lignes.
- Pour un remboursement de commission (retour), les sens sont inverses.
- Le compte client est lettre par `payout_reference`.

### 2.3 Ecritures de reversement marketplace (Journal RG)

#### 2.3.1 Reversement standard

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| RG | 51200000 | Banque | Montant | | Ref versement |
| RG | FMANO | Fournisseur ManoMano | | Montant | Ref versement |

#### 2.3.2 Lignes speciales — Eco-contribution (Journal AC)

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| AC | 62802000 | Eco-contribution | Montant HT | | |
| AC | 44566001 | TVA deductible | TVA | | |
| AC | 46720000 | Client ManoMano | | Montant TTC | Ref payout |

#### 2.3.3 Lignes speciales — Penalite remboursement (Journal AC)

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| AC | 62220300 | Penalite | Montant | | |
| AC | 46720000 | Client ManoMano | | Montant | Ref payout |

### 2.4 Reversement agrege marketplace (Journal RG)

Genere a partir du PayoutSummary pour les lignes de type "Paiement".

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| RG | 58000000 | Compte de transit | Montant | | |
| RG | 46720000 | Client ManoMano | | Montant | Ref payout |

---

## 3. Decathlon

### 3.1 Ecritures de vente (Journal DEC)

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| DEC | 46730000 | Client Decathlon | TTC | | Ref payout |
| DEC | 70703xxxx | Vente produit HT (par pays) | | HT | |
| DEC | 708503xxxx | Port HT (par zone geo) | | Port HT | |
| DEC | 4457xxxx | TVA collectee (par pays) | | TVA | |

**Notes :**
- Le code canal Decathlon est `03`.
- Les montants du CSV Decathlon sont en TTC ; le moteur extrait le HT via le taux TVA.
- Le lettrage client utilise la `payout_reference`.

### 3.2 Ecritures de commission marketplace (Journal AC)

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| AC | 62220800 | Commission Decathlon | Commission TTC | | |
| AC | 46730000 | Client Decathlon | | Commission TTC | Ref payout |

**Notes :**
- Decathlon n'a pas de TVA deductible sur les commissions (`commission_vat_rate: 0.0`), donc l'ecriture est en 2 lignes seulement (pas d'eclatement HT/TVA).
- Le compte de charge `62220800` est debite directement (pas de compte fournisseur `FDECATHLON` en contrepartie).

### 3.3 Ecritures de reversement marketplace (Journal RG)

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| RG | 51200000 | Banque | Montant | | Ref versement |
| RG | FDECATHLON | Fournisseur Decathlon | | Montant | Ref versement |

### 3.4 Abonnement Decathlon (Journal AC)

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| AC | 61311112 | Abonnement Decathlon | Montant | | |
| AC | 46730000 | Client Decathlon | | Montant | Ref payout |

**Note :** Pas de TVA deductible configuree pour Decathlon, donc l'abonnement est comptabilise TTC.

### 3.5 Reversement agrege marketplace (Journal RG)

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| RG | 58000000 | Compte de transit | Montant | | |
| RG | 46730000 | Client Decathlon | | Montant | Ref payout |

---

## 4. Leroy Merlin

### 4.1 Ecritures de vente (Journal LM)

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| LM | 46740000 | Client Leroy Merlin | TTC | | Ref payout |
| LM | 70704xxxx | Vente produit HT (par pays) | | HT | |
| LM | 708504xxxx | Port HT (par zone geo) | | Port HT | |
| LM | 4457xxxx | TVA collectee (par pays) | | TVA | |

**Notes :**
- Le code canal Leroy Merlin est `04`.
- Le lettrage client utilise la `payout_reference`.

### 4.2 Ecritures de commission marketplace (Journal AC)

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| AC | 62220900 | Commission Leroy Merlin HT | Commission HT | | |
| AC | 44566001 | TVA deductible | TVA deductible | | |
| AC | 46740000 | Client Leroy Merlin | | Commission TTC | Ref payout |

**Notes :**
- Leroy Merlin a un taux de TVA sur commission de 20% (`commission_vat_rate: 20.0`), ce qui permet l'eclatement en 3 lignes (HT + TVA deductible + TTC).

### 4.3 Ecritures de reversement marketplace (Journal RG)

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| RG | 51200000 | Banque | Montant | | Ref versement |
| RG | FADEO | Fournisseur Leroy Merlin (Adeo) | | Montant | Ref versement |

### 4.4 Abonnement Leroy Merlin (Journal AC)

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| AC | 61311113 | Abonnement Leroy Merlin HT | Montant HT | | |
| AC | 44566001 | TVA deductible | TVA | | |
| AC | 46740000 | Client Leroy Merlin | | Montant TTC | Ref payout |

**Note :** L'abonnement Leroy Merlin beneficie de la TVA deductible (taux 20%), ce qui genere 3 lignes.

### 4.5 Reversement agrege marketplace (Journal RG)

| Journal | Compte | Description | Debit | Credit | Lettrage |
|---------|--------|-------------|-------|--------|----------|
| RG | 58000000 | Compte de transit | Montant | | |
| RG | 46740000 | Client Leroy Merlin | | Montant | Ref payout |

---

## 5. Annexe : Plan comptable par defaut

### Comptes clients

| Canal | Compte |
|-------|--------|
| Shopify | 411SHOPIFY |
| ManoMano | 46720000 |
| Decathlon | 46730000 |
| Leroy Merlin | 46740000 |

### Comptes fournisseurs

| Canal | Compte |
|-------|--------|
| ManoMano | FMANO |
| Decathlon | FDECATHLON |
| Leroy Merlin | FADEO |

### Comptes PSP

| Methode | Compte bancaire | Commission | Compte intermediaire |
|---------|-----------------|------------|----------------------|
| Card | 51150012 | 62700002 | 46710001 |
| PayPal | 51150012 | 62700001 | 46710001 |
| Klarna | 51150011 | 62700003 | -- |

### Comptes de charges marketplace

| Canal | Commission | TVA deductible | Abonnement | Penalite | Eco-contribution |
|-------|------------|----------------|------------|----------|------------------|
| ManoMano | 62220300 | 44566001 | -- | 62220300 | 62802000 |
| Decathlon | 62220800 | -- | 61311112 | -- | -- |
| Leroy Merlin | 62220900 | 44566001 | 61311113 | -- | -- |

### Comptes speciaux

| Type | Compte |
|------|--------|
| Transit | 58000000 |
| Banque | 51200000 |
| Ajustement | 51150002 |

### Journaux

| Code | Description |
|------|-------------|
| VE | Ventes Shopify |
| MM | Ventes ManoMano |
| DEC | Ventes Decathlon |
| LM | Ventes Leroy Merlin |
| AC | Achats (commissions, abonnements, frais) |
| RG | Reglements et reversements |
