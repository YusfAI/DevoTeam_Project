# Documentation — DevoTeam Dashboard

Quel document lire, selon ce que vous avez à faire.

## Installer l'application

| Document | Pour qui | Contenu |
|---|---|---|
| [`Installing DevoTeam Dashboard.pdf`](../Installing%20DevoTeam%20Dashboard.pdf) | La personne qui installe, sans connaissance technique | Guide pas à pas en anglais, de l'installation de Git au « TOUT EST JUSTE » final, avec le dépannage |
| [`OBTENIR_LES_ACCES.md`](OBTENIR_LES_ACCES.md) | Qui prépare l'installation | Ce qu'il faut réunir **avant** le jour J : partage de la feuille, lien et onglet, conditions du poste |
| [`INSTALLATION_DOCKER.md`](INSTALLATION_DOCKER.md) | Qui installe ou dépanne | La méthode recommandée (`INSTALLER.bat`), étape par étape, et ce que fait chaque étape |
| [`INSTALLATION.md`](INSTALLATION.md) | Qui ne peut pas utiliser Docker | L'installation native (Python, Node, moteur de tableaux de bord), assistée par [`setup/`](../setup/README.md) |

## Comprendre l'application

| Document | Pour qui | Contenu |
|---|---|---|
| [`reports/Rapport_Professionnel_DevoTeam_Dashboard.docx`](reports/Rapport_Professionnel_DevoTeam_Dashboard.docx) | Direction, lecteurs non techniques | Besoin métier, solution, fonctionnalités, déploiement, feuille de route |
| [`reports/Guide_Technique_DevoTeam_Dashboard.docx`](reports/Guide_Technique_DevoTeam_Dashboard.docx) | Développeurs, revue technique | Architecture, code module par module, tests, limites connues, déploiement |
| [`WORKFLOW.md`](WORKFLOW.md) | Développeurs | Le trajet concret d'une question, du chat jusqu'au tableau de bord affiché |
| [`PROGRESS.md`](PROGRESS.md) | Développeurs | Journal de développement : chaque phase livrée, ses choix et ses vérifications |

## Régénérer les documents Word et le PDF

Les trois `.docx` de `reports/` et le PDF d'installation à la racine sont produits
par un script, à partir du contenu réel du projet — ne pas les modifier à la main :

```
pip install -r requirements-dev.txt
python Documentation/reports/generate_docs.py
```

L'export PDF passe par Microsoft Word ; sans Word, les `.docx` sont produits et le
PDF est à exporter à la main.
