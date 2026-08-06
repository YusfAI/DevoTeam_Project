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
- [x] Phase 7 — Vendoring local des librairies Vega (cache navigateur) *(remplacée par la Phase 8)*
- [x] Phase 8 — Passage professionnel : anti-hallucination backend, qualité des graphiques, migration Vite/React
- [x] Phase 9 — Compréhension du prompt : contexte multi-tour, dates relatives, comparaisons
- [x] Phase 10 — Migration du LLM : Groq (Llama 3.3) → Claude (Anthropic) *(annulée en Phase 11)*
- [x] Phase 11 — Retour à Groq (Llama 3.3)

## 📝 Journaux

**Phase 1** : Terminée (Serveur FastAPI opérationnel de base, interface chat prête).
**Phase 2** : Terminée (Implémentation du générateur Vega-Lite et tests unitaires réussis avec gestion des `null`).
**Phase 3** : Terminée (Couche d'accès DB sécurisée paramétrée avec Pymysql & dbutils pool, utilise les vues pré-agrégées).
**Phase 4** : Terminée (Intégration Groq et validation stricte avec Pydantic pour restreindre le JSON formaté).
**Phase 5** : Terminée (Architecture pipeline en place reliant NLP -> Validation -> SQL -> Vega-Lite -> HTTP Response).
**Phase 6** : Terminée (Création des tables manquantes pour le logs/cache en MySQL, réutilisation des specs par Hachage).
**Phase 7** : Terminée puis **remplacée par la Phase 8** (le vendoring manuel CDN dans `frontend/vendor/` n'a plus de raison d'être une fois le frontend migré vers Vite : Vega/Vega-Lite/Vega-Embed sont redevenus de vraies dépendances npm, bundlées et hashées automatiquement — cache navigateur correct nativement, sans classe `StaticFiles` custom).

**Phase 8** : Terminée. Trois chantiers menés en parallèle :
- *Anti-hallucination backend* (`backend/llm.py`) : suppression des défauts silencieux (un `metric`/`dimension` non reconnu déclenchait auparavant un fallback vers `"budget"` ou `""` sans le dire — remplacé par une demande de clarification explicite) ; validation étendue des filtres `country`/`funding_source`/`partner` (auparavant non whitelistés du tout) via correspondance exacte → alias → `difflib` ; rejet Pydantic explicite des clés de filtre hors whitelist ; logging propre (`logging` au lieu de `print`, corrige au passage un bug d'encodage mojibake) ; résilience réseau sur l'appel Groq.
- *Cohérence requêtes/graphiques* (`backend/db_layer.py`, `backend/vega_generator.py`) : mapping vue-par-dimension explicite (fini le `"v_by_" + dimension` fantôme) ; le cas "métrique indisponible sur la vue" bascule maintenant sur le calcul groupé au lieu de lever une erreur incohérente avec le cas symétrique ; correction du bug NULL→0 sur les KPI (`win_probability`/`weighted_amount` ~47% NULL) en calculant la valeur KPI côté Python (`None` reste `None`) plutôt que via un hack de texte Vega ; garde-fou de cardinalité (pie > 6 segments → bascule en barre horizontale, bar/pie > seuil → regroupement "Autres" pour les agrégations sum/count) ; palette catégorielle validée CVD.
- *Frontend* : migration complète Vanilla JS → **Vite + React**, cartes KPI natives (StatTile), tableau jumeau pour chaque graphique, thème clair/sombre.
- *Fiabilité* : pool MySQL rendu paresseux (`backend/db.py`) pour que l'import des modules ne nécessite plus une DB déjà démarrée ; suite `pytest` (`tests/`) remplaçant les scripts `print`-and-eyeball, avec mocks Groq/DB (aucune dépendance réseau/DB réelle) — inclut un test de non-régression sur le bug de filtre silencieusement perdu observé historiquement.
- *Sécurité* : `.env` (contenait la vraie clé Groq) retiré du suivi git + `.gitignore` ajouté + `.env.example` créé. **Action restant à faire par l'utilisateur : régénérer la clé Groq sur console.groq.com**, puisqu'elle est restée exposée dans l'historique git jusqu'ici.

**Phase 9** : Terminée. Mode JSON Schema strict Groq testé empiriquement et abandonné : `llama-3.3-70b-versatile` rejette `response_format: json_schema` avec une 400 explicite (modèle non supporté), et le modèle est imposé par le mandat du projet. Le filet de sécurité existant (Pydantic + whitelist + `IntentUnclear`) reste le mécanisme d'application des règles. Trois capacités ajoutées :
- *Dates et périodes relatives* (`backend/intent_refiner.py`) : "ce mois-ci", "le mois dernier", "cette année", "l'année dernière", "ce/le trimestre (dernier)", "les N derniers mois" — résolues en **Python déterministe** (arithmétique de date pure, gère les passages d'année), jamais confiées au calcul du LLM (risque de dates plausibles-mais-fausses). Fonctionne même sans appel Groq quand le reste de la requête passe par le parseur rapide. Nouveau support `BETWEEN` dans `range_filters`/`db_layer.py` pour les intervalles.
- *Requêtes de comparaison* : les filtres peuvent désormais être une liste de valeurs (`filters:{"country":["France","Maroc"]}`) plutôt qu'une seule — traduit en `WHERE ... IN (...)` côté SQL, chaque valeur validée individuellement (une comparaison avec un pays inconnu déclenche une clarification nommant la valeur fautive, pas un abandon silencieux). Le parseur rapide détecte les mots de comparaison ("compare", "vs"...) et les cas à plusieurs pays cités pour ne jamais y répondre seul.
- *Contexte multi-tour* : le frontend renvoie le dernier intent résolu avec chaque nouvelle question (`previous_intent`, pas de session serveur) ; dès qu'un contexte est présent, le chemin rapide sans LLM est systématiquement sauté et Groq reçoit le contexte dans le prompt pour interpréter les questions de suivi ("et pour Data Management ?"). Vérifié en conditions réelles : le second tour hérite correctement du type de graphique/dimension et ne change que le filtre demandé.

Vérifié en conditions réelles (MySQL + Groq) pour les trois : date relative résolue sans appel LLM, comparaison à deux pays produisant un graphique à deux barres, et un suivi conversationnel réel.

**Phase 10** : Terminée côté code (vérifiée par la suite `pytest` avec mocks — le compte Anthropic utilisé pour le build n'avait pas de crédit au moment de la migration, vérification en conditions réelles jamais faite). `backend/llm.py` appelait l'API Claude (`claude-haiku-4-5`) au lieu de Groq, avec des sorties structurées strictes (`client.messages.parse(..., output_format=<Pydantic>)`) rendant `metric`/`dimension`/`chart_type`/`aggregation`/clés de filtres impossibles à halluciner par construction — ce qui avait permis de supprimer la réparation heuristique par mots-clés (`_resolve_metric`/`_resolve_dimension`). **Annulée en Phase 11** à la demande de l'utilisateur (retour à Groq).

**Phase 11** : Terminée. Retour complet à Groq (`llama-3.3-70b-versatile`) — `backend/llm.py` et `tests/test_llm_validation.py` restaurés à l'état de fin de Phase 9 (JSON libre + validation Pydantic + réparation heuristique `_resolve_metric`/`_resolve_dimension`, toutes les capacités de la Phase 9 — dates relatives, comparaisons, contexte multi-tour — inchangées et déjà compatibles avec ce chemin). `requirements.txt`, `.env`, `.env.example`, `README.md` repointés vers `GROQ_API_KEY`. Suite `pytest` (53 tests) revérifiée après restauration.


## 📊 Bilan du Produit

L'application est **complète et fonctionnelle, exécutable de bout-en-bout**, hébergée localement. En développement : `uvicorn backend.main:app --reload` (API) + `npm run dev` dans `frontend/` (UI, proxy vers l'API). En local "prod" : `npm run build` puis `uvicorn backend.main:app` sert l'UI et l'API sur `http://127.0.0.1:8000/` en un seul processus. Voir `README.md` pour le détail.

### Limites connues
- Le LLM reste volontairement rigide sur les demandes ambiguës : une métrique/dimension/valeur de filtre non reconnue déclenche désormais systématiquement une demande de clarification explicite plutôt qu'un résultat deviné — c'est un choix délibéré (anti-hallucination), pas un bug, mais ça veut dire que certaines formulations très informelles échoueront là où un système plus permissif aurait deviné (parfois correctement, parfois non).
- L'interface ne maintient pas de véritable "contexte de session de chat" persistant côté navigateur (rechargement efface le chat).
- Le bundle frontend (Vega/Vega-Lite/Vega-Embed) dépasse le seuil d'avertissement Vite (~1 Mo minifié) — sans impact réel en usage local, mais un code-splitting (import dynamique de vega-embed) serait la prochaine étape si l'app devait un jour être servie sur un réseau plus lent.

### Prochaines améliorations possibles
*(hors scope initial du mandat)*
- **Auth / Multi-tenancy** : Authentifier l'utilisateur via JWT pour restreindre la visualisation aux seules pratiques de sa BU.
- **Session ID Tracking** : Dans le log MySQL `dashboard_requests`, ajouter `session_id` pour faire du vrai product-analytics sur le comportement des utilisateurs.
- **Contexte de chat persistant** : conserver l'historique de conversation côté navigateur (localStorage) entre les rechargements (le contexte multi-tour de la Phase 9 vit déjà en mémoire React, mais disparaît au rechargement comme le reste du chat).
- **Mode JSON Schema strict** : non supporté par Groq/`llama-3.3-70b-versatile` (testé en Phase 9, confirmé 400 explicite). Fonctionne nativement avec Claude (validé en Phase 10) si l'app devait un jour migrer à nouveau — le filet de sécurité actuel (Pydantic + whitelist + `IntentUnclear`) reste suffisant en attendant.
