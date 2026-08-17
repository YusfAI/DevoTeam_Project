# Du prompt au résultat — ce qui se passe à l'intérieur

Traçage concret d'une question posée dans le chat, du texte brut jusqu'au graphique
affiché. Exemple utilisé : **« budget total par pays pour Risk Advisory »**.

## Vue d'ensemble

```
Chat (frontend)
  → POST /dashboard { query, previous_intent }
  → backend/llm.py :: parse_user_query()
      → chemin rapide (mots-clés) OU appel Gemini + validation Pydantic
      → résolution des filtres contre les vraies valeurs de la base
  → backend/intent_refiner.py :: refine_intent()
      → dates relatives, garde-fous déterministes (days_remaining, funnel...)
  → backend/db_layer.py :: build_and_execute_query()
      → requête SQL paramétrée sur une liste blanche de tables/colonnes
  → backend/vega_generator.py + response_builder.py
      → spec Vega-Lite (ou KPI/table) + message texte calculé depuis les données
  → Frontend :: DashboardPanel + vega-embed
      → affichage, mise en cache, contexte gardé pour le tour suivant
```

## Étape par étape, avec l'exemple

**1. Le chat.** L'utilisateur tape la question et clique Envoyer. Le frontend envoie :
```json
POST /dashboard
{ "query": "budget total par pays pour Risk Advisory", "previous_intent": null }
```

**2. Compréhension** (`backend/llm.py`). Pas de contexte précédent, une seule practice
citée : le chemin rapide par mots-clés (`intent_refiner.py::try_rule_based_parse`)
peut suffire ; sinon Gemini reçoit un prompt système avec les vraies valeurs de la base
(practices/pays/statuts connus, date du jour) et renvoie un JSON structuré :
```json
{"metric": "budget", "dimension": "country",
 "filters": {"practice": "Risk Advisory"},
 "chart_type": "bar", "aggregation": "sum"}
```
Ce JSON est chargé dans un modèle Pydantic (`DashboardIntent`) qui rejette toute clé
de filtre hors liste blanche. La valeur "Risk Advisory" passe par `_fuzzy_match()`
contre les vraies valeurs de `practice` en base — trouvée telle quelle, acceptée.

**3. Affinage déterministe** (`intent_refiner.py::refine_intent`). Aucune date
relative ici, rien à corriger : l'intent traverse inchangé. (C'est à cette étape que
« ce mois-ci », « opportunités urgentes < 7 jours », ou une dimension forcée sur
`status` pour un entonnoir seraient calculés en Python pur — jamais devinés par le LLM.)

**4. Requête SQL** (`db_layer.py::build_and_execute_query`). La dimension `country` a
une vue pré-agrégée dédiée (`v_by_country`) :
```sql
SELECT country, SUM(total_budget) AS value FROM v_by_country
WHERE ... practice = %s ... GROUP BY country ORDER BY value DESC
```
→ retourne `[{"country": "Maroc", "value": 1250000}, ...]`.

**5. Génération du résultat.** `vega_generator.py` construit la spec Vega-Lite
(barres, palette validée, plafond de catégories) ; `response_builder.py` calcule en
parallèle le message texte affiché (« Le budget total pour Risk Advisory est de X €
sur Y pays... ») — directement depuis les mêmes données, jamais rédigé par le LLM.

**6. Cache + journal.** Le hash de l'intent sert de clé dans `generated_dashboards`
(évite de régénérer une spec identique) ; la requête est aussi journalisée dans
`dashboard_requests` (historique/audit).

**7. Réponse.** FastAPI renvoie :
```json
{ "ai_message": "...", "vega_spec": {...}, "intent": {...} }
```

**8. Affichage** (frontend). `DashboardPanel` rend le graphique via `vega-embed` ;
`intent` devient le `previous_intent` du tour suivant (contexte multi-tour), et tout
est sauvegardé dans `localStorage` pour survivre à un rechargement de page.

## Le principe qui protège tout ça

Le LLM ne produit jamais de SQL et ne touche jamais la base — seulement un JSON
intermédiaire, entièrement validé (schéma + liste blanche + valeurs réelles) avant
qu'une seule requête ne soit construite. Si quelque chose ne colle pas (métrique
inconnue, pays introuvable, date ambiguë), le pipeline s'arrête à l'étape 2 ou 3 et
renvoie une demande de clarification plutôt qu'un résultat inventé.

*(Pour le détail complet module par module, voir `Documentation/reports/Guide_Technique_DevoTeam_Dashboard.docx`.)*
