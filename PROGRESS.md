# PROGRESS

## Objectif
Construire, de bout en bout, une application de dashboard conversationnel pour DevoTeam.

## 🚀 État de la mission

- [x] Phase 1 — Backend + page de base
- [x] Phase 2 — Générateur Vega-Lite
- [x] Phase 3 — Couche SQL sécurisée
- [x] Phase 4 — Intégration Groq
- [x] Phase 5 — Pipeline complet
- [x] Phase 6 — Historique et cache persistant

## 📝 Journaux

**Phase 1** : Terminée (Serveur FastAPI opérationnel de base, interface chat prête).
**Phase 2** : Terminée (Implémentation du générateur Vega-Lite et tests unitaires réussis avec gestion des `null`).
**Phase 3** : Terminée (Couche d'accès DB sécurisée paramétrée avec Pymysql & dbutils pool, utilise les vues pré-agrégées).
**Phase 4** : Terminée (Intégration Groq et validation stricte avec Pydantic pour restreindre le JSON formaté).
**Phase 5** : Terminée (Architecture pipeline en place reliant NLP -> Validation -> SQL -> Vega-Lite -> HTTP Response).
**Phase 6** : Terminée (Création des tables manquantes pour le logs/cache en MySQL, réutilisation des specs par Hachage).


## 📊 Bilan du Produit

L'application est **complète et fonctionnelle, exécutable de bout-en-bout**. L'utilisateur accède à la page frontend sur `http://127.0.0.1:8000/`, pose une question au chat, et une requête paramétrée est automatiquement construite via l'intention Pydantic traduite. Le rendu final se fait en temps réel sur l'espace central. 
Le serveur Uvicorn est actuellement lancé.

### Limites connues
- Le traitement du LLM Groq est très rigide; si une subtilité n'est pas comprise, on renverra en fallback direct un message demandant de préciser (limite acceptée selon la règle de ne pas planter le backend et de ne pas autoriser des requêtes libres).
- L'interface ne maintient pas de véritable "contexte de session de chat" persistant côté navigateur (rechargement efface le chat).

### Prochaines améliorations possibles
*(hors scope initial du mandat)*
- **Auth / Multi-tenancy** : Authentifier l'utilisateur via JWT pour restreindre la visualisation aux seules pratiques de sa BU.
- **Cache côté Frontend** : Éviter le rechargement de scripts CDN externes (Vega-Embed).
- **Session ID Tracking** : Dans le log MySQL `dashboard_requests`, ajouter `session_id` pour faire du vrai product-analytics sur le comportement des utilisateurs.
- **UI plus riche** : Transformer le frontend Vanilla CSS vers un bundle ViteJS et un composant react avec skeleton-loaders lors du chargement des réponses Llama-3.
