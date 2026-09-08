# Obtenir les accès — à faire avant le jour de l'installation

Une fiche à garder de côté. Elle liste tout ce qu'il faut récupérer **avant**
d'arriver sur le poste de destination — rien de tout cela ne se fait sur place,
et le manque de l'un d'eux est la cause la plus fréquente d'une installation
interrompue à mi-chemin.

---

## ☐ 1. La clé Gemini (obligatoire)

**Où** : [aistudio.google.com](https://aistudio.google.com) → bouton **« Get API key »**

1. Connectez-vous avec un compte Google.
2. Cliquez **Get API key** → **Create API key**.
3. Copiez la clé affichée (elle commence par `AIza...`).

C'est elle qui va dans `GOOGLE_API_KEY=` du fichier `.env`. L'offre gratuite suffit
largement à l'usage de cette application.

---

## ☐ 2. Le compte de service Google + son fichier JSON (obligatoire)

C'est l'étape la plus longue, mais elle ne se fait **qu'une seule fois** — le même
fichier JSON peut resservir pour d'autres installations si besoin.

**Où** : [console.cloud.google.com](https://console.cloud.google.com)

1. Créez un projet (ou réutilisez-en un existant) — bouton en haut de la page.
2. Menu ☰ → **IAM et administration** → **Comptes de service**.
3. **Créer un compte de service** → donnez-lui un nom (ex. `devoteam-dashboard`) →
   **Créer et continuer** → **Terminer** (les rôles proposés ne sont pas
   nécessaires ici).
4. Cliquez sur le compte de service créé → onglet **Clés** → **Ajouter une clé**
   → **Créer une clé** → format **JSON** → **Créer**.
5. Un fichier `.json` se télécharge automatiquement (dans *Téléchargements*
   généralement) — **c'est lui** qu'il faudra déposer dans `credentials\` lors de
   l'installation.
6. Toujours sur cette page, **activez l'API Google Sheets** si ce n'est pas déjà
   fait : menu ☰ → **API et services** → **Bibliothèque** → chercher
   *Google Sheets API* → **Activer**.

Ouvrez le fichier JSON dans un éditeur de texte et repérez la ligne
`"client_email"` — c'est l'adresse qu'il faudra partager avec la feuille
(étape 4).

---

## ☐ 3. Le lien de la feuille Google (obligatoire)

Ouvrez la feuille dans le navigateur et copiez l'URL complète telle qu'elle
apparaît — l'identifiant s'en extrait automatiquement à l'installation, inutile
de le découper vous-même :

```
https://docs.google.com/spreadsheets/d/IDENTIFIANT_DE_LA_FEUILLE/edit
```

Notez aussi le **nom de l'onglet** qui contient les données (visible en bas de
la feuille).

---

## ☐ 4. Partager la feuille avec le compte de service (obligatoire)

Dans Google Sheets : **Partager** → collez l'adresse `client_email` du fichier
JSON (étape 2) → rôle **Éditeur** (pas Lecteur) → **Envoyer**.

> Le rôle Éditeur n'est pas une précaution excessive : l'application **écrit**
> dans la feuille (elle attribue un identifiant aux lignes qui n'en ont pas). Un
> partage en Lecteur laisse tout fonctionner jusqu'au premier enregistrement,
> puis échoue sans rien expliquer.

---

## ☐ 5. Mot de passe d'application Gmail (facultatif)

Uniquement si vous voulez le rappel quotidien par email des échéances à 7 jours.
Sans lui, l'application fonctionne intégralement, seul ce rappel ne part pas.

**Où** : [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)

Nécessite que la validation en 2 étapes soit activée sur ce compte Gmail —
sinon la page n'existe pas. Donnez un nom au mot de passe (ex.
*DevoTeam Dashboard*), copiez les 16 caractères affichés **sans les espaces**.

---

## Récapitulatif — ce que vous devez avoir en main avant de partir

| # | Élément | Où il va |
|---|---|---|
| 1 | Clé Gemini | `.env` → `GOOGLE_API_KEY` |
| 2 | Fichier `.json` du compte de service | `credentials\google_service_account.json` |
| 3 | Lien de la feuille + nom de l'onglet | `.env` → `GOOGLE_SHEET_ID` / `GOOGLE_SHEET_TAB` |
| 4 | La feuille déjà partagée en Éditeur | *(rien à coller — juste à avoir fait)* |
| 5 *(optionnel)* | Mot de passe d'application Gmail | `.env` → `GMAIL_APP_PASSWORD` |

Une fois sur place, `setup\INSTALLER.bat` (ou la procédure Docker) vous
redemandera ces mêmes valeurs, dans le même ordre — vous n'aurez plus qu'à les
coller.
