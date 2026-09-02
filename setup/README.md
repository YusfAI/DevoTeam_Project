# Installation assistée

Pour installer l'application sur un poste neuf sans rien connaître du projet.

## Utilisation

Double-cliquez sur **`INSTALLER.bat`**.

C'est tout. L'assistant s'occupe du reste et ne vous demande que ce qu'il ne peut
pas deviner.

## Ce qu'il vous demande

| Ce qu'il demande | Où le trouver |
|---|---|
| La clé Gemini | [aistudio.google.com](https://aistudio.google.com) → *Get API key* |
| Le lien de la feuille Google | Copiez l'URL entière depuis votre navigateur — il en extrait l'identifiant tout seul |
| Le nom de l'onglet | Celui qui contient les données (`opportunities` par défaut) |
| Le fichier JSON du compte de service | Une fenêtre de sélection s'ouvre — le fichier est copié et renommé correctement |
| Les alertes email | Facultatif, on peut passer |

## Ce qu'il fait sans rien demander

- Vérifie Python et Node, et dit précisément quoi installer s'ils manquent
- **Installe le moteur de tableaux de bord** (bruin + dac) via Git Bash
- Crée l'environnement Python isolé et installe les dépendances aux versions épinglées
- Compile l'interface
- Écrit le `.env` en conservant ses commentaires
- Copie et renomme le fichier d'identifiants
- **Affiche l'adresse à qui partager la feuille, puis attend** que ce soit fait —
  en revérifiant à chaque fois que vous le lui dites
- Crée les raccourcis du Bureau
- Lance le diagnostic complet et affiche le verdict

## Trois choses qu'il fait bien

**Il attend le partage au lieu d'échouer dessus.** Partager la feuille est un geste
qui se fait ailleurs, dans l'interface de Google. L'assistant affiche l'adresse
exacte, vous laisse le temps, et revérifie — jusqu'à dix fois. Il teste la lecture
**et l'écriture** : un partage en Lecteur laisse tout fonctionner jusqu'au premier
enregistrement, puis échoue sans rien expliquer.

**Aucun secret ne s'affiche.** La clé et le mot de passe se saisissent en aveugle et
ne sont écrits que dans `.env`, exclu du dépôt Git. Les espaces des mots de passe
d'application Gmail — que Google affiche en quatre groupes de quatre — sont retirés
automatiquement : collés tels quels, ils font échouer l'authentification.

**Il est rejouable.** Relancez-le après avoir corrigé quelque chose : les valeurs
déjà saisies sont proposées par défaut, l'environnement existant est réutilisé, et
rien n'est défait.

## Si quelque chose bloque

L'assistant nomme le point bloquant et le geste à faire. Après correction,
relancez `INSTALLER.bat`.

Pour vérifier seul, sans rien modifier :

```
.venv\Scripts\python.exe scripts\verifier_installation.py
```

## Après l'installation

Lancez l'application par le raccourci **« DevoTeam Dashboard (Production) »**, puis,
une fois la page ouverte :

```
.venv\Scripts\python.exe scripts\test_fonctionnel.py
```

Ce dernier répond à une question différente du diagnostic : non pas « tout est-il
branché ? », mais **« les chiffres sont-ils justes sur ces données ? »**. Il calcule
la réponse attendue depuis la feuille et la compare à ce que l'application annonce.

Tant qu'il n'affiche pas **« TOUT EST JUSTE »**, ne présentez pas l'application.

---

## Contenu du dossier

| Fichier | Rôle |
|---|---|
| `INSTALLER.bat` | Le fichier à double-cliquer |
| `assistant.ps1` | L'assistant lui-même |
| `sonde_feuille.py` | Teste l'accès à la feuille en lecture **et** en écriture |

L'assistant ne réimplémente rien : il enchaîne `scripts\install.bat` et
`scripts\verifier_installation.py`. Deux chemins d'installation qui feraient la même
chose de deux façons finiraient par diverger.

La procédure détaillée, à suivre à la main si vous préférez, est dans
[`../Documentation/INSTALLATION.md`](../Documentation/INSTALLATION.md).
