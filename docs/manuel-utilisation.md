# Manuel d'utilisation MAPP E-COMMERCE

Guide utilisateur complet pour l'outil de comptabilite e-commerce MAPP E-COMMERCE.

---

## Sommaire

1. [Prerequis](#1-prerequis)
2. [Telecharger les fichiers sources](#2-telecharger-les-fichiers-sources)
3. [Charger les fichiers dans MAPP](#3-charger-les-fichiers-dans-mapp)
4. [Verifier le parametrage comptable](#4-verifier-le-parametrage-comptable)
5. [Generer les ecritures](#5-generer-les-ecritures)
6. [Verifier les anomalies](#6-verifier-les-anomalies)
7. [Exporter les ecritures](#7-exporter-les-ecritures)
8. [Flash e-commerce](#8-flash-e-commerce)

---

## 1. Prerequis

### Navigateur web

MAPP E-COMMERCE fonctionne dans un navigateur web moderne. Les navigateurs recommandes sont :

- **Google Chrome** (version 90 ou superieure) -- recommande
- **Mozilla Firefox** (version 90 ou superieure)
- **Microsoft Edge** (version 90 ou superieure)
- **Safari** (version 15 ou superieure)

L'application prend en charge les themes clair, sombre et systeme, accessibles depuis le selecteur en bas de la barre laterale.

### Acces a l'outil

Ouvrez l'adresse de l'application MAPP E-COMMERCE dans votre navigateur. Aucune installation n'est necessaire. L'outil fonctionne integralement dans le navigateur ; vos fichiers ne quittent pas votre poste (le traitement est effectue localement via le serveur de l'application).

---

## 2. Telecharger les fichiers sources

Avant d'utiliser MAPP, vous devez exporter les fichiers CSV depuis chaque marketplace. Voici les fichiers attendus pour chaque canal et leur nommage.

**Important :** L'outil identifie automatiquement chaque fichier par son nom. Il est essentiel de conserver les noms d'origine ou de respecter les conventions de nommage ci-dessous (le caractere `*` represente une partie variable du nom, par exemple la date ou la periode).

### 2.1 Shopify

Exportez les fichiers suivants depuis l'administration Shopify :

| Fichier | Nommage attendu | Obligatoire | Source dans Shopify |
|---------|-----------------|-------------|---------------------|
| Ventes | `Ventes Shopify*.csv` | Oui | Rapports > Ventes |
| Transactions | `Transactions Shopify*.csv` | Oui | Rapports > Finances > Transactions |
| Details des versements | `Details versements*.csv` ou `Details versements*.csv` | Oui | Paiements > Versements |
| Retours | `Total des retours*.csv` | Non (optionnel) | Rapports > Ventes > Retours |

**Notes :**
- Les trois premiers fichiers forment un groupe obligatoire : ils doivent tous etre presents pour que le canal Shopify soit traite.
- Le fichier des retours est optionnel mais ameliore la precision des ecritures d'avoir.
- Les fichiers `Detail transactions par versements*.csv` sont egalement acceptes (optionnels, plusieurs fichiers possibles).

### 2.2 ManoMano

Exportez les fichiers suivants depuis le back-office ManoMano :

| Fichier | Nommage attendu | Obligatoire | Source dans ManoMano |
|---------|-----------------|-------------|----------------------|
| Chiffre d'affaires | `CA Manomano*.csv` | Oui | Rapports de ventes |
| Detail versement | `Detail versement Manomano*.csv` | Oui | Rapports de paiements |
| Detail commandes | `Detail commandes manomano*.csv` | Oui | Rapports de commandes |

**Note :** Le separateur utilise dans les CSV ManoMano est le point-virgule (`;`). L'outil le detecte automatiquement.

### 2.3 Decathlon

| Fichier | Nommage attendu | Obligatoire | Source |
|---------|-----------------|-------------|--------|
| Donnees Decathlon | `Decathlon*.csv` | Oui | Export Mirakl (portail vendeur Decathlon) |

**Note :** Decathlon utilise la plateforme Mirakl. Un seul fichier CSV contient toutes les donnees (ventes, commissions, reversements).

### 2.4 Leroy Merlin

| Fichier | Nommage attendu | Obligatoire | Source |
|---------|-----------------|-------------|--------|
| Donnees Leroy Merlin | `Leroy Merlin*.csv` | Oui | Export Mirakl (portail vendeur Leroy Merlin) |

**Note :** Comme Decathlon, Leroy Merlin utilise la plateforme Mirakl. Un seul fichier CSV suffit.

### Remarques generales sur les fichiers

- **Separateur CSV :** L'outil detecte automatiquement le separateur (virgule `,` ou point-virgule `;`). Si vous avez ouvert et re-enregistre un fichier avec Excel, le separateur peut avoir change -- cela est gere automatiquement.
- **Encodage :** Les fichiers doivent etre en UTF-8 (encodage par defaut des exports marketplace).
- **Taille maximale :** 50 Mo par fichier.

---

## 3. Charger les fichiers dans MAPP

### 3.1 Acceder a la vue d'import

Au lancement de l'application, vous arrivez automatiquement sur la vue **Import fichiers** (premiere icone dans la barre laterale gauche).

### 3.2 Deposer les fichiers

La zone d'import se presente sous la forme d'un encadre en pointilles avec l'icone de telechargement. Deux methodes sont disponibles :

- **Glisser-deposer :** Selectionnez les fichiers CSV dans votre explorateur de fichiers et faites-les glisser directement dans la zone de depot.
- **Parcourir :** Cliquez sur la zone ou sur le lien "ou parcourez vos fichiers" pour ouvrir le selecteur de fichiers de votre systeme.

Vous pouvez deposer les fichiers de tous les canaux en une seule operation. L'outil les trie automatiquement.

### 3.3 Verification de la detection

Apres le depot, l'application affiche un tableau de bord des canaux detectes :

- Chaque canal (Shopify, ManoMano, Decathlon, Leroy Merlin) est represente par une carte.
- Les fichiers reconnus sont affiches sous chaque canal avec une coche verte.
- Les fichiers manquants sont signales.
- Un compteur en haut indique le nombre de canaux complets (ex : "2/4 complets").

**Fichiers non reconnus :** Si un fichier ne correspond a aucun pattern connu, il est signale en orange avec la mention "non reconnu". Verifiez que le nom du fichier respecte les conventions de nommage decrites dans la section precedente.

### 3.4 Supprimer un fichier

Pour retirer un fichier depose par erreur, cliquez sur le bouton de suppression (icone X) a cote du nom du fichier dans la carte du canal concerne.

---

## 4. Verifier le parametrage comptable

### 4.1 Acceder aux parametres

Cliquez sur **Parametres** dans la section "Configuration" de la barre laterale gauche. Vous pouvez egalement cliquer sur le bouton "Parametres" dans la barre de validation en bas de la vue d'import.

### 4.2 Structure du parametrage

Le parametrage est organise en quatre sections :

#### Comptes de tiers

- **Clients :** Comptes clients par canal (ex : `411SHOPIFY`, `46720000`).
- **Fournisseurs :** Comptes fournisseurs marketplace (ex : `FMANO`, `FDECATHLON`, `FADEO`).

#### Comptes de charges

- **Commissions :** Comptes de charges pour les commissions marketplace (Decathlon, Leroy Merlin).
- **Commissions PSP :** Comptes de charges pour les commissions des prestataires de paiement (Card, PayPal, Klarna).
- **Abonnements :** Comptes de charges pour les abonnements marketplace (Decathlon, Leroy Merlin).

#### TVA et Journaux

- **TVA deductible :** Compte de TVA deductible utilise pour les commissions avec TVA recuperable.
- **Codes journaux :** Codes des journaux comptables par canal (VE, MM, DEC, LM pour les ventes ; AC pour les achats ; RG pour les reglements).

#### Parametres de controle

- **Seuil de tolerance :** Ecart maximum tolere (en euros) pour le rapprochement entre ventes et encaissements. Valeur par defaut : 0.01 EUR. Plage autorisee : 0.001 a 1.00 EUR.

### 4.3 Modifier une valeur

Cliquez dans le champ de saisie de la valeur a modifier et tapez la nouvelle valeur. Les modifications sont signalees visuellement :
- Le champ modifie est entoure en couleur.
- La valeur par defaut est affichee en petit sous le champ.
- Un bouton de reinitialisation apparait pour revenir a la valeur par defaut.

### 4.4 Reinitialiser

- **Un champ :** Cliquez sur l'icone de reinitialisation a droite du champ.
- **Tous les champs :** Cliquez sur le bouton "Reinitialiser" en bas de la page, puis confirmez.

**Important :** Les modifications du plan comptable sont temporaires et ne sont pas sauvegardees entre les sessions. Elles s'appliquent uniquement au traitement en cours.

---

## 5. Generer les ecritures

### 5.1 Lancer le traitement

En bas de la vue d'import, une barre de validation indique l'etat de preparation :

- Le nombre de canaux prets est affiche (ex : "2 canaux prets").
- Le bouton **Generer les ecritures** est actif des qu'au moins un canal est complet.

Cliquez sur **Generer les ecritures** pour lancer le traitement. Un indicateur de chargement s'affiche pendant la generation.

**Note :** Les canaux incomplets (fichiers manquants) sont automatiquement ignores. Seuls les canaux dont tous les fichiers obligatoires sont presents sont traites.

### 5.2 Resultat du traitement

Apres le traitement, l'application bascule automatiquement vers la vue de resultats. Plusieurs onglets deviennent accessibles dans la barre laterale :

- **Ecritures** : Tableau detaille de toutes les ecritures generees.
- **Anomalies** : Liste des points de controle a verifier.
- **Resume** : Vue synthetique des indicateurs cles.
- **Flash e-commerce** : Tableau de bord visuel.

### 5.3 Vue Resume

La vue Resume presente les indicateurs cles par canal :

- **Taux de rapprochement :** Pourcentage des ventes rapprochees avec un encaissement. Un taux de 100% signifie que chaque vente a ete retrouvee dans les fichiers de transactions/versements.
- **CA HT :** Chiffre d'affaires hors taxes total.
- **Nombre d'ecritures :** Total des lignes d'ecritures generees.
- **Ventilation par type :** Repartition entre ventes, commissions, reglements, reversements et frais.
- **Decompte des anomalies par severite.**

Les indicateurs sont egalement detailles par canal avec un code couleur (vert = OK, orange = a verifier, rouge = erreur).

---

## 6. Verifier les anomalies

### 6.1 Acceder aux anomalies

Cliquez sur **Anomalies** dans la barre laterale. Un badge rouge sur l'icone indique le nombre total d'anomalies detectees.

### 6.2 Les trois niveaux de severite

Les anomalies sont classees par severite, de la plus critique a la moins critique :

| Severite | Couleur | Signification |
|----------|---------|---------------|
| **Erreur** | Rouge | Probleme bloquant qui necessite une correction avant import en comptabilite. Exemple : ecart de TVA significatif, incoherence TTC. |
| **Avertissement** | Orange | Point d'attention qui peut necessiter une verification manuelle. Exemple : vente sans encaissement correspondant, versement multi-PSP. |
| **Info** | Bleu | Information contextuelle, generalement sans action requise. Exemple : versement d'une periode anterieure, resume de paiement. |

### 6.3 Types d'anomalies courants

#### Coherence TVA
- **Ecart de taux TVA** : Le taux TVA calcule differe du taux attendu pour le pays.
- **Ecart de montant TVA** : Le montant TVA recalcule ne correspond pas au montant du fichier source.
- **Incoherence TTC** : Le total TTC ne correspond pas a HT + TVA.

#### Rapprochement ventes/encaissements
- **Vente sans encaissement** : Une commande n'a pas ete retrouvee dans les fichiers de transactions.
- **Encaissement orphelin** : Un reglement ne correspond a aucune vente connue.
- **Ecart de montant** : L'ecart entre le montant de la vente et l'encaissement depasse le seuil de tolerance.

#### Versements
- **Versement multi-PSP** : Un versement contient des transactions de plusieurs moyens de paiement differents.
- **Versement sans correspondance** : Un versement n'a aucune transaction dans la periode exportee.

#### Remboursements
- **Remboursement de periode anterieure** : Un remboursement concerne une commande d'une periode precedente.

### 6.4 Filtrer les anomalies

Utilisez les filtres en haut du panneau pour affiner l'affichage :
- **Par severite** : Afficher uniquement les erreurs, avertissements ou infos.
- **Par canal** : Afficher les anomalies d'un canal specifique.

Les anomalies sont regroupees par categorie et presentees sous forme de cartes depliables. Chaque carte indique le nombre d'occurrences et le detail de chaque anomalie.

### 6.5 Exporter le rapport d'anomalies en PDF

Cliquez sur le bouton **Exporter PDF anomalies** pour telecharger un rapport PDF. Ce rapport contient la liste complete des anomalies avec leur severite, canal, reference et detail. Il peut etre conserve comme piece justificative ou transmis a un collaborateur pour verification.

---

## 7. Exporter les ecritures

### 7.1 Acceder a l'export

Les boutons d'export sont disponibles dans la vue **Ecritures**.

### 7.2 Export Excel (.xlsx)

Cliquez sur **Telecharger Excel (.xlsx)** pour obtenir un fichier Excel directement importable dans votre logiciel comptable. Le fichier contient les colonnes suivantes :

- Date
- Journal
- Compte
- Libelle
- Debit
- Credit
- Numero de piece
- Lettrage
- Canal
- Type d'ecriture

Le fichier est nomme `ecritures-AAAA-MM-JJ.xlsx` (avec la date du jour).

### 7.3 Export CSV

Si le serveur n'est pas disponible ou si vous preferez le format CSV, cliquez sur **Telecharger CSV (2 fichiers)**. Deux fichiers sont generes :

1. `ecritures-AAAA-MM-JJ.csv` : Les ecritures comptables.
2. `anomalies-AAAA-MM-JJ.csv` : La liste des anomalies.

Les fichiers CSV utilisent le separateur point-virgule (`;`) et l'encodage UTF-8 avec BOM pour une ouverture correcte dans Excel.

### 7.4 Filtrage des ecritures

Avant l'export, vous pouvez filtrer les ecritures affichees dans le tableau :
- Par **journal** (VE, MM, DEC, LM, AC, RG).
- Par **canal** (Shopify, ManoMano, Decathlon, Leroy Merlin).
- Par **type** (vente, commission, reglement, reversement, frais).
- Par **periode** a l'aide du filtre de dates.

**Note :** L'export Excel genere les ecritures a partir des fichiers sources, independamment des filtres d'affichage. Les filtres d'affichage sont uniquement visuels.

---

## 8. Flash e-commerce

### 8.1 Acceder au Flash

Cliquez sur **Flash e-commerce** dans la barre laterale (icone graphique). Ce tableau de bord n'est disponible qu'apres avoir genere les ecritures.

### 8.2 Tableau de bord visuel

Le Flash e-commerce presente une synthese visuelle de votre activite e-commerce sur la periode traitee. Il est organise autour de plusieurs indicateurs :

#### KPIs principaux

- **CA HT total** : Chiffre d'affaires hors taxes, tous canaux confondus.
- **Nombre de commandes** : Total des commandes traitees.
- **Taux de rapprochement** : Pourcentage global de rapprochement ventes/encaissements.
- **Taux d'anomalies** : Part des transactions presentant une anomalie.

#### Graphiques

- **Repartition du CA par canal** : Camembert montrant la part de chaque marketplace dans le chiffre d'affaires.
- **CA HT par canal** : Histogramme comparatif.
- **Repartition geographique** : CA HT par pays.
- **Taux de remboursement par canal** : Evolution des retours.
- **Commissions par canal** : Montant et taux de commission marketplace.
- **Ventilation TVA** : Repartition de la TVA par pays et par taux.
- **Anomalies par categorie** : Repartition visuelle des anomalies.
- **Rentabilite par canal** : Net vendeur apres commissions et frais.

### 8.3 Filtre par periode

Un selecteur de periode en haut de la page permet de restreindre l'affichage a une plage de dates. Le filtre s'applique a l'ensemble des graphiques et KPIs du Flash.

### 8.4 Export PDF du Flash

Cliquez sur le bouton **Exporter PDF** pour generer un document PDF du Flash e-commerce. Ce PDF contient :

- L'en-tete avec le nom de l'entreprise et la periode.
- Les KPIs principaux.
- Les graphiques reproduits en format vectoriel pour une impression de qualite.
- Les tableaux de donnees associes (TVA par pays, commissions, etc.).

Le PDF est directement imprimable et peut etre joint comme piece complementaire au dossier comptable de la periode.

**Note :** Vous pouvez choisir d'exporter le Flash pour un canal unique via une case a cocher dans les options d'export.

---

## Glossaire

| Terme | Definition |
|-------|-----------|
| **Canal** | Marketplace ou plateforme de vente (Shopify, ManoMano, Decathlon, Leroy Merlin). |
| **PSP** | Prestataire de Services de Paiement (ex : Shopify Payments, PayPal, Klarna). |
| **Rapprochement** | Processus de verification de la correspondance entre une vente et son encaissement. |
| **Lettrage** | Code permettant de rapprocher les ecritures comptables entre elles (debit et credit de la meme operation). |
| **Reversement (Payout)** | Virement de la marketplace vers le compte bancaire du vendeur. |
| **Commission** | Frais preleves par la marketplace ou le PSP sur chaque transaction. |
| **Anomalie** | Point de controle detecte automatiquement par l'outil, necessitant ou non une action corrective. |
| **Flash e-commerce** | Tableau de bord synthetique de l'activite e-commerce sur une periode donnee. |
| **Seuil de tolerance** | Ecart maximum (en euros) accepte lors du rapprochement entre un montant de vente et son encaissement. |
