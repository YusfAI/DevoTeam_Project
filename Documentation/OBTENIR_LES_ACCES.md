# Obtenir les accès — à faire avant le jour de l'installation

Une fiche à garder de côté. Elle liste tout ce qu'il faut préparer **avant**
d'arriver sur le poste de destination — rien de tout cela ne se fait sur place,
et le manque de l'un d'eux est la cause la plus fréquente d'une installation
interrompue à mi-chemin.

Aucune de ces étapes ne demande de créer une clé ni de télécharger un fichier
d'identifiants : la lecture du Sheet se fait par son lien d'export public (le
même mécanisme que « Fichier → Télécharger → CSV »), et le modèle de chat
tourne **en local** (Ollama), sans clé du tout.

---

## ☐ 1. Partager la feuille Google en lecture (obligatoire)

Dans Google Sheets : **Partager** → sous « Accès général », choisissez
**« Toute personne disposant du lien »**, rôle **Lecteur** → **Terminé**.

> Sans ce partage, l'application ne peut rien lire : Google sert une page de
> connexion à la place des données. Il n'y a personne de précis à qui
> « partager » ici — pas de compte de service, pas d'adresse
> `@...iam.gserviceaccount.com` à copier. Le lien lui-même est l'autorisation.
>
> **À peser côté entreprise** : « toute personne disposant du lien » rend la
> feuille lisible par quiconque obtient ce lien, sans qu'un accès Google
> individuel soit vérifié. Si ce n'est pas acceptable pour la feuille en
> question, il faut soit y placer des données moins sensibles, soit revenir à
> une authentification par compte de service (non couverte par cette fiche).

---

## ☐ 2. Le lien de la feuille Google et son onglet (obligatoire)

Ouvrez la feuille dans le navigateur et copiez l'URL complète telle qu'elle
apparaît — l'identifiant s'en extrait automatiquement à l'installation, inutile
de le découper vous-même :

```
https://docs.google.com/spreadsheets/d/IDENTIFIANT_DE_LA_FEUILLE/edit
```

Notez aussi le **nom exact de l'onglet** qui contient les données, visible en
bas de la feuille.

> **Piège à connaître** : un nom d'onglet qui ne correspond à AUCUN onglet réel
> ne produit aucune erreur au moment de l'installation — Google charge
> silencieusement le premier onglet de la feuille à la place, et rien ne le
> signale. Mieux vaut copier-coller ce nom directement depuis l'onglet dans le
> navigateur que de le retaper de mémoire.

---

## ☐ 3. Le modèle de chat — Ollama (aucune clé, installation automatique)

Rien à récupérer ici : `scripts\install.bat` et l'assistant d'installation
détectent Ollama, l'installent s'il manque
([ollama.com/download](https://ollama.com/download)), et téléchargent
automatiquement le modèle (`qwen2.5:7b-instruct-q4_K_M`, ~4,7 Go) au premier
lancement. Ça peut prendre plusieurs minutes selon la connexion — c'est
normal, laissez-le terminer.

Aucune clé API, aucun compte, aucun quota : le modèle tourne entièrement sur
la machine.

---

## ☐ 4. Mot de passe d'application Gmail (facultatif)

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
| 1 | La feuille partagée en Lecteur, « toute personne disposant du lien » | *(rien à coller — juste à avoir fait)* |
| 2 | Lien de la feuille + nom exact de l'onglet | `.env` → `GOOGLE_SHEET_ID` / `GOOGLE_SHEET_TAB` |
| 3 | Ollama + le modèle | *(rien à faire — installé automatiquement)* |
| 4 *(optionnel)* | Mot de passe d'application Gmail | `.env` → `GMAIL_APP_PASSWORD` |

Une fois sur place, `INSTALLER.bat` (à la racine — recommandé, via Docker) ou
`setup\INSTALLER_NATIF.bat` (alternative sans Docker) vous demandera ces mêmes
valeurs — vous n'aurez plus qu'à les coller.
