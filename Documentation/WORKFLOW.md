# Du prompt au dashboard — ce qui se passe à l'intérieur

Traçage concret d'une question posée dans le chat, du texte brut jusqu'au dashboard
affiché. Exemple utilisé : **« budget par pays pour Risk Advisory »**.

## Vue d'ensemble

```
                    ┌─ Google Sheet (source de vérité)
                    │        ↓  toutes les 15 min
                    │   backend/data_store.py  →  DataFrame pandas (en mémoire)
                    │     une cellule illisible → « Non renseigné », la ligne est
                    │     conservée ; chaque remplacement est tracé (data_quality.py)
                    │        ↓                          ↓
                    │   duckdb_export.py            chat & alertes
                    │        ↓  (projection lecture seule)
                    │   dac/data/devoteam.db
                    └────────────────────────────────────┐
                                                         │
Chat (frontend)                                          │
  → POST /dashboard { query, previous_intent }           │
  → backend/llm.py :: parse_user_query()                 │
      → RETOUCHE reconnue ? (« en camembert », « top 5 »)│
        → appliquée sur l'intention précédente, sans LLM │
      → sinon : chemin rapide (mots-clés) OU appel Gemini│
      → validation Pydantic + liste blanche              │
      → résolution des filtres contre les vraies valeurs │
  → backend/intent_refiner.py :: refine_intent()         │
      → dates relatives, garde-fous déterministes        │
      → choose_chart_type() : la forme demandée est      │
        confrontée à la cardinalité réelle des données   │
  → backend/db_layer.py (pandas)  →  message texte       │
  → backend/dac_composer.py                              │
      → compose 5-7 widgets (règles déterministes)       │
      → backend/sql_builder.py génère le SQL de chacun ──┘
      → réécrit dac/dashboards/_principal.yml (travail)
      → écrit dac/dashboards/_analyse_<hash>.yml (instantané)
      → describe_change() : ce qui a changé par rapport au tour précédent
  → réponse { ai_message, dac_dashboard, dashboard_snapshot, intent }
  → Frontend :: iframe → Bruin DAC (port 8321)
      → DAC exécute le SQL de chaque widget sur DuckDB
      → affiche le dashboard multi-widgets
```

## Deux fichiers, deux rôles

`_principal.yml` porte TOUJOURS le même nom de dashboard (« Tableau de bord »), donc
toujours la même URL : chaque question le réécrit, et l'utilisateur voit son tableau
de bord se transformer au lieu d'en voir apparaître un de plus. `_analyse_<hash>.yml`
fige le résultat de cette question précise, ce qui permet à la liste déroulante du chat
de rouvrir une analyse passée telle qu'elle était — sans repasser par le modèle.

Les deux sont des artefacts d'exécution, hors suivi git (voir `.gitignore`). Sont
versionnés en revanche les dashboards du tableau de bord principal — `accueil.yml`,
`section_chaudes.yml`, `section_sante.yml`, `section_pipeline.yml`,
`section_urgences.yml` — tous produits par `scripts/generate_accueil.py`, ainsi que
`qualite.yml`.

## Le raccourci : quand aucun fichier n'est écrit

Avant de composer quoi que ce soit, `backend/overview_match.py` regarde si une
section porte DÉJÀ la réponse. Si oui, le backend renvoie simplement son nom et les
filtres à lui appliquer : la page s'ouvre filtrée, rien n'est écrit sur le disque, et
les chiffres viennent de widgets relus en revue plutôt que d'une composition faite à
la volée.

La table de correspondance ne se fie pas à l'apparence. Une page peut porter la même
métrique sur le même axe et répondre à une AUTRE question, parce que son périmètre
diffère : le KPI « Offres remises » compte les statuts déposés dont l'échéance est
passée (147), là où le chat compte le portefeuille actif (229). Les deux chiffres
sont justes ; y renvoyer afficherait un nombre différent de celui qu'on vient
d'annoncer. `tests/test_reutilisation_fidele.py` exécute donc les deux moteurs sur
les mêmes lignes et refuse toute entrée dont le total ou le nombre de lignes diffère.

## Étape par étape, avec l'exemple

**1. Le chat.** L'utilisateur tape la question et clique Envoyer :
```json
POST /dashboard
{ "query": "budget par pays pour Risk Advisory", "previous_intent": null }
```

**2. Compréhension** (`backend/llm.py`). Pas de contexte précédent : le chemin rapide
par mots-clés (`intent_refiner.py::try_rule_based_parse`) peut suffire — sinon Gemini
reçoit un prompt système contenant les vraies valeurs des données (practices, pays,
statuts connus, date du jour) et renvoie un JSON structuré :
```json
{"metric": "budget", "dimension": "country",
 "filters": {"practice": "Risk Advisory"},
 "chart_type": "bar", "aggregation": "sum"}
```
Ce JSON est chargé dans un modèle Pydantic (`DashboardIntent`) qui rejette toute clé
de filtre hors liste blanche. La valeur « Risk Advisory » passe par `_fuzzy_match()`
contre les valeurs réellement présentes dans la colonne `practice` — trouvée, acceptée.
Si elle ne l'était pas, le pipeline s'arrêterait ici avec une demande de clarification.

**3. Affinage déterministe** (`intent_refiner.py::refine_intent`). Aucune date relative
ici, rien à corriger. (C'est à cette étape que « ce mois-ci », « urgentes < 7 jours »
ou la règle métier « offre pondérée » seraient calculés en Python pur — jamais devinés
par le LLM.)

**4. Les données pour le message** (`db_layer.py`). L'intention est traduite en
opérations pandas sur le DataFrame en mémoire — filtres en masques booléens,
`GROUP BY` en `.groupby().agg()` :
```python
df[df["practice"] == "Risk Advisory"].groupby("country")["budget"].sum()
```
→ `[{"country": "Tunisie", "budget": 26000000}, ...]`

**5. Le message texte** (`response_builder.py`) est calculé directement depuis ces
données, jamais rédigé par le LLM :
> « Budget par pays — filtres : practice = Risk Advisory. Total : 72 680 000 € sur
> 16 pays. Classement : Tunisie (26 000 000 €, 36 %) | … »

**6. La composition du dashboard** (`dac_composer.py`). L'intention donne l'angle
principal ; des **règles déterministes** l'entourent de widgets complémentaires qui
partagent tous ses filtres :

| Widget | Rôle |
|---|---|
| Budget / Opportunités / Montant pondéré | les totaux du périmètre interrogé |
| Budget par pays | le graphique qui répond à la question |
| Budget par statut | le même chiffre sous un autre angle |
| Pipeline commercial | où en sont ces opportunités |
| Détail des opportunités | la vérification ligne par ligne |

La dimension complémentaire évite toute dimension déjà figée par un filtre — grouper
par practice alors que la question filtre sur une seule practice donnerait un
graphique à une seule barre.

**7. La génération du SQL** (`sql_builder.py`). **Le LLM n'écrit jamais ce SQL.**
Chaque widget est traduit depuis son intention validée :
```sql
SELECT country, SUM(budget) AS budget
FROM opportunities
WHERE practice = 'Risk Advisory'
  AND status NOT IN ('Offre perdue', 'Infructueux', 'NO GO', 'Hors scope', 'Non shortlisté')
GROUP BY country
ORDER BY budget DESC
```
Les noms de colonnes viennent de la liste blanche, et les valeurs sont échappées
(`'Côte d''Ivoire'`) — les vraies données contiennent des apostrophes.

La clause `status NOT IN (...)` est ajoutée automatiquement : les affaires
définitivement perdues sont exclues de tous les chiffres par défaut, parce qu'un
« budget total » qui additionne 66 M€ d'affaires mortes n'aide personne à décider.
L'exclusion est levée dès que la question porte elle-même sur un statut — « liste des
offres perdues » doit répondre, pas renvoyer un tableau vide.

**8. L'écriture du dashboard.** Le tout est écrit deux fois en YAML — dans
`dac/dashboards/_principal.yml` (le tableau de bord de travail, réécrit sur place) et
dans `dac/dashboards/_analyse_<hash>.yml` (l'instantané de cette question) — en bloc
littéral pour rester relisible :
```yaml
name: Budget par pays pour risk advisory
connection: devoteam_duckdb
rows:
  - widgets:
      - name: Budget
        type: metric
        col: 4
        sql: |-
          SELECT SUM(budget) AS value
          FROM opportunities
          WHERE practice = 'Risk Advisory'
```

**8 bis. Ce qui a changé.** Si la question suit une précédente, les deux intentions
sont comparées et la différence est annoncée en tête de réponse (« Tableau de bord
mis à jour — axe : pays → practice ; filtres retirés »). Si la demande n'a rien
changé, ou si une forme demandée a été refusée, la réponse le dit également : une
demande comprise ne doit jamais rester sans réponse visible.

**9. La réponse.** FastAPI renvoie :
```json
{
  "ai_message": "...",
  "dac_dashboard": "Tableau de bord",
  "dashboard_snapshot": "Budget par pays — Risk Advisory",
  "intent": {...}
}
```

**10. L'affichage.** Le frontend pointe son iframe sur
`http://localhost:8321/d/<nom encodé>`, en reportant les filtres dans la chaîne de
requête. DAC lit le YAML, exécute le SQL de chaque widget sur le fichier DuckDB, et
rend le dashboard. Si le nom est celui d'une section, la barre d'onglets s'affiche
au-dessus ; sinon, seul le bouton de retour au tableau de bord principal subsiste. `intent` devient le
`previous_intent` du tour suivant (contexte multi-tour), et tout est sauvegardé dans
`localStorage` pour survivre à un rechargement de page.

## Les deux principes qui protègent tout ça

**Le LLM ne touche jamais les données.** Il ne produit qu'un JSON intermédiaire,
entièrement validé (schéma + liste blanche + valeurs réelles) avant qu'une seule
requête ne soit construite. Ni SQL, ni pandas, ni chiffre ne sortent de lui. Si
quelque chose ne colle pas — métrique inconnue, pays introuvable, date ambiguë — le
pipeline s'arrête à l'étape 2 ou 3 et renvoie une demande de clarification plutôt
qu'un résultat inventé.

**Une seule source de vérité.** Le DataFrame pandas alimente le chat et les alertes ;
le fichier DuckDB qu'interroge DAC n'en est qu'une projection réécrite à chaque
rafraîchissement. Les deux moteurs affichent donc toujours les mêmes chiffres — c'est
vérifiable, et c'est vérifié : le nombre d'opportunités urgentes est identique dans
le chat, dans le dashboard généré et dans la section qui l'affiche, et le raccourci
décrit plus haut n'accepte une section que si elle redonne le chiffre exact.

*(Pour le détail complet module par module, voir
`Documentation/reports/Guide_Technique_DevoTeam_Dashboard.docx`.)*
