# Obtenir les accès — à faire avant le jour de l'installation

Une fiche à garder de côté. Elle liste tout ce qu'il faut récupérer **avant**
d'arriver sur le poste de destination — rien de tout cela ne se fait sur place,
et le manque de l'un d'eux est la cause la plus fréquente d'une installation
interrompue à mi-chemin.

Aucune de ces étapes ne demande de partager une clé avec un tiers ni de
télécharger un fichier d'identifiants : la clé API Sheets est en **lecture
seule**, et le modèle de chat tourne **en local** (Ollama), sans clé du tout.

---

## ☐ 1. Une clé API Google Sheets, en lecture seule (obligatoire)

**Où** : [console.cloud.google.com](https://console.cloud.google.com)

1. Créez un projet (ou réutilisez-en un existant) — bouton en haut de la page.
2. Menu ☰ → **API et services** → **Bibliothèque** → cherchez *Google Sheets
   API* → **Activer**.
3. Menu ☰ → **API et services** → **Identifiants** → **Créer des identifiants**
   → **Clé API**.
4. Copiez la clé affichée (elle commence par `AIza...`).
5. *(Recommandé)* Cliquez sur la clé fraîchement créée → **Restrictions de
   l'API** → limitez-la à *Google Sheets API* uniquement. Une clé restreinte ne
   sert à rien d'autre même si elle fuite.

C'est elle qui va dans `GOOGLE_SHEETS_API_KEY=` du fichier `.env`. Pas de
compte de service, pas de fichier JSON à télécharger ni à déposer quelque
part : une clé API suffit, parce que la lecture du Sheet est la seule chose
dont l'application a besoin — elle n'y écrit jamais.

---

## ☐ 2. Le lien de la feuille Google (obligatoire)

Ouvrez la feuille dans le navigateur et copiez l'URL complète telle qu'elle
apparaît — l'identifiant s'en extrait automatiquement à l'installation, inutile
de le découper vous-même :

```
https://docs.google.com/spreadsheets/d/IDENTIFIANT_DE_LA_FEUILLE/edit
```

Notez aussi le **nom de l'onglet** qui contient les données (visible en bas de
la feuille).

---

## ☐ 3. Partager la feuille en lecture (obligatoire)

Dans Google Sheets : **Partager** → sous « Accès général », choisissez
**« Toute personne disposant du lien »**, rôle **Lecteur** → **Terminé**.

> Une clé API n'a pas d'identité Google propre — elle ne peut lire que ce qui
> est déjà accessible par lien, quel que soit son propriétaire. C'est
> pourquoi il n'y a personne de précis à qui « partager » cette fois : pas de
> compte de service, pas d'adresse `@...iam.gserviceaccount.com` à copier. Et
> comme la clé est en lecture seule, il n'y a rien à réparer si le partage
> est fait en Lecteur plutôt qu'en Éditeur — contrairement à l'ancien compte
> de service, aucun rôle plus large n'est jamais nécessaire.
>
> **À peser côté entreprise** : « toute personne disposant du lien » est un
> partage plus large qu'un compte de service ciblé — quiconque obtient le
> lien peut lire les données, sans qu'un accès Google individuel soit
> nécessaire. Si ce n'est pas acceptable pour la feuille en question, il
> faut soit y placer des données moins sensibles, soit revenir à une
> authentification par compte de service (non couverte par cette fiche).

---

## ☐ 4. Le modèle de chat — Ollama (aucune clé, installation automatique)

Rien à récupérer ici : `scripts\install.bat` et l'assistant d'installation
détectent Ollama, l'installent s'il manque
([ollama.com/download](https://ollama.com/download)), et téléchargent
automatiquement le modèle (`qwen2.5:7b-instruct-q4_K_M`, ~4,7 Go) au premier
lancement. Ça peut prendre plusieurs minutes selon la connexion — c'est
normal, laissez-le terminer.

Aucune clé API, aucun compte, aucun quota : le modèle tourne entièrement sur
la machine.

---

## ☐ 5. Mot de passe d'application Gmail (facultatif)

Uniquement si vous voulez le rappel quotidien par email des échéances à 7 jours.
Sans lui, l'application fonctionne intégralement, seul ce rappel ne part pas.

**Où** : [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)

Nécessite que la validation en 2 étapes soit activée sur ce compte Gmail —
sinon la page n'existe pas. Donnez un nom au mot de passe (ex.
*DevoTeam Dashboard*), copiez les 16 caractères affichés **sans les espaces**.

Le rappel peut être envoyé à **plusieurs personnes** : séparez les adresses par
une virgule dans `ALERT_RECIPIENT_EMAIL` (ex.
`direction@exemple.com,suivi@exemple.com`).

---

## Récapitulatif — ce que vous devez avoir en main avant de partir

| # | Élément | Où il va |
|---|---|---|
| 1 | Clé API Google Sheets (lecture seule) | `.env` → `GOOGLE_SHEETS_API_KEY` |
| 2 | Lien de la feuille + nom de l'onglet | `.env` → `GOOGLE_SHEET_ID` / `GOOGLE_SHEET_TAB` |
| 3 | La feuille partagée en Lecteur, « toute personne disposant du lien » | *(rien à coller — juste à avoir fait)* |
| 4 | Ollama + le modèle | *(rien à faire — installé automatiquement)* |
| 5 *(optionnel)* | Mot de passe d'application Gmail | `.env` → `GMAIL_APP_PASSWORD` |

Une fois sur place, `INSTALLER.bat` (à la racine — recommandé, via Docker) ou
`setup\INSTALLER_NATIF.bat` (alternative sans Docker) vous demandera ces mêmes
valeurs — vous n'aurez plus qu'à les coller.
