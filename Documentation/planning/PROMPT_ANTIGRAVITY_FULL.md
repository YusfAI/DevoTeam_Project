> ================================================================================
> DOCUMENT HISTORIQUE — NE DÉCRIT PLUS L'APPLICATION ACTUELLE (relu le 28/08/2026)
> ================================================================================
> Ce document date d'une conception antérieure. Trois de ses choix techniques ont
> été abandonnés depuis :
> 
>   - SQLite / MySQL  ->  le Google Sheet chargé en mémoire par pandas est la
>                         source unique ; DuckDB n'est qu'une projection en lecture
>                         seule pour les dashboards (backend/data_store.py).
>   - Vega-Lite       ->  les visuels sont produits par Bruin DAC en YAML versionné
>                         (dac/dashboards/, backend/dac_composer.py).
>   - Dashboard unique par question  ->  un tableau de bord de travail réécrit en
>                         place, plus un instantané par analyse.
> 
> Il est conservé pour mémoire du raisonnement d'origine. L'architecture qui fait
> foi est décrite dans README.md et PROGRESS.md.
> ================================================================================
> 

# Rôle

Tu es l'ingénieur full-stack en charge de construire, **de bout en bout et de façon autonome**, une application de dashboard conversationnel pour DevoTeam. Tu ne dois pas t'arrêter demander validation entre les étapes — construis, teste toi-même, corrige, et avance jusqu'à un produit complet et fonctionnel. Documente ce que tu fais au fur et à mesure dans un fichier `PROGRESS.md` à la racine du projet, mis à jour à chaque étape terminée.

---

# Ce que fait l'application

L'utilisateur écrit une demande en langage naturel dans un chat (ex: *"montre-moi le budget par pays pour Risk Advisory"*). Un LLM interprète l'intention et la transforme en JSON structuré. Ce JSON est validé, traduit en requête SQL sûre sur MySQL, et le résultat est transformé en spec Vega-Lite affichée dynamiquement dans le navigateur, à côté du chat.

---

# Stack technique imposée (ne pas dévier, ne pas proposer d'alternative)

- **Backend** : FastAPI (Python), validation stricte avec Pydantic
- **Frontend** : HTML/CSS/JS vanilla (pas de React/Vue), Vega-Lite + vega-embed via CDN
- **Base de données** : MySQL / MariaDB via **XAMPP**, base `devoteam_dashboard`, déjà créée et peuplée localement (import fait via phpMyAdmin)
- **Accès DB** : PyMySQL avec pool de connexions (`DBUtils.PooledDB` ou pool SQLAlchemy) — jamais une connexion ouverte/fermée par requête HTTP
- **Connexion locale (XAMPP par défaut)** : host `127.0.0.1`, port `3306`, user `root`, **pas de mot de passe**. Ces valeurs sont déjà dans `.env` — ne les modifie pas, ne demande pas d'autres identifiants.
- **LLM** : API Groq, modèle `llama-3.3-70b-versatile`, sortie strictement structurée (JSON forcé, jamais de texte libre à parser)
- **Config** : variables d'environnement via `.env` (voir `.env.example` fourni), jamais de secret en dur dans le code

---

# Ce qui existe déjà dans le workspace (à utiliser, ne pas recréer)

```
devoteam_dashboard/
├── .env                            → déjà rempli (XAMPP: root, sans mot de passe, port 3306)
├── backend/
│   ├── db.py                      → connexion MySQL centralisée, pool à ajouter dedans
│   └── schema_and_whitelist.py    → whitelist tables/colonnes + contrat de validation
└── data/
    └── devoteam_dashboard_mysql.sql   → déjà importé dans MySQL via phpMyAdmin, la base existe
```

**Important : la base `devoteam_dashboard` existe déjà et contient les vraies données (360 lignes), importée manuellement via phpMyAdmin de XAMPP. Ne recrée pas la base, ne réimporte pas le dump, ne lance aucune commande `CREATE DATABASE` — connecte-toi directement dessus avec les identifiants du `.env`. Vérifie la connexion en premier (`SELECT COUNT(*) FROM opportunities` doit renvoyer 360) avant de commencer la Phase 1.**

## Schéma de données réel (table `opportunities`, 360 lignes de vraies données commerciales)

```
id, country, created_date (DATE), deadline (DATE), deadline_month (VARCHAR "YYYY-MM"),
deadline_year (INT), days_remaining (INT), practice, description, buyer, opp_type,
status, budget (DOUBLE), funding_source, partner, financial_offer (DOUBLE),
win_probability (DOUBLE, ~47% NULL), weighted_amount (DOUBLE, ~47% NULL)
```

Index déjà en place : `country`, `practice`, `status`, `deadline_year`, `deadline_month`, `funding_source`.

## Vues pré-agrégées déjà créées (à utiliser en priorité — ne jamais faire de GROUP BY à la main sur `opportunities`)
- `v_by_country`, `v_by_practice`, `v_by_status`, `v_by_month`, `v_by_funding_source`, `v_by_country_practice`

## Dépendances Python déjà requises par `backend/db.py` (à mettre dans `requirements.txt`)
`fastapi`, `uvicorn`, `pymysql`, `python-dotenv`, `dbutils`, `pydantic`, `groq` (ou `requests` si appel HTTP direct)

## Valeurs catégorielles réelles (définies dans `schema_and_whitelist.py`, à respecter strictement)
- `practice` : Digital Transformation, Risk Advisory, Data Management (3 valeurs seulement)
- `status` : 19 valeurs (Lead, Offre gagnée, Offre perdue, NO GO, etc. — voir `KNOWN_VALUES`)
- `opp_type` : AO, DP, AMI, Consultation, Prospection, Gré à gré, Avant-vente

---

# Contrat JSON intermédiaire (le pont entre le LLM et Vega — schéma Pydantic)

```python
class DashboardIntent(BaseModel):
    goal: str
    metric: Literal["budget", "financial_offer", "weighted_amount", "nb_opportunities", "win_probability"]
    dimension: Literal["country", "practice", "status", "deadline_month", "deadline_year", "funding_source", "opp_type"]
    filters: dict[str, str] = {}
    chart_type: Literal["bar", "line", "pie", "table", "kpi_card"]
    aggregation: Literal["sum", "avg", "count"]
```

Toute valeur de `filters` doit être vérifiée contre `KNOWN_VALUES` avant d'aller plus loin. Toute valeur hors whitelist (colonne, table, catégorie) doit produire une erreur explicite renvoyée au frontend — jamais un fallback silencieux.

---

# Règles non négociables (sécurité + performance)

1. **Jamais de SQL généré librement par le LLM.** Le LLM ne produit QUE le JSON ci-dessus. Un module séparé, déterministe, traduit ce JSON validé vers une requête paramétrée sur une des vues existantes.
2. **Requêtes paramétrées uniquement** (`%s` avec PyMySQL) — jamais de f-string/concat avec une valeur venant de l'utilisateur ou du LLM.
3. **Pool de connexions MySQL obligatoire** dans `db.py` — c'est le principal risque de latence avec MySQL (contrairement à SQLite).
4. **Générateur Vega-Lite déterministe** : même JSON + mêmes données → même spec, toujours. Aucune "créativité" du LLM à cette étape.
5. **Gestion des NULL** : `win_probability` et `weighted_amount` sont ~47% NULL. Le générateur Vega doit les exclure proprement des agrégations, jamais les traiter comme 0 silencieusement.
6. **Cache** : hasher le JSON intermédiaire validé ; si déjà vu, réutiliser le spec Vega en cache au lieu de tout recalculer (table `generated_dashboards`).
7. **Erreurs LLM** : si Groq renvoie un JSON invalide ou hors schéma, ne jamais planter le backend — renvoyer un message clair au frontend et logger l'échec.
8. **Langues** : code et noms techniques en anglais, messages utilisateur en français (le métier est francophone : "ventes", "practice", "statut gagné"...). Le prompt système envoyé à Groq doit expliciter le mapping français → noms techniques anglais.

---

# Construction attendue (toutes les phases, sans t'arrêter)

**Phase 1 — Backend + page de base**
`backend/main.py` (FastAPI), route `GET /` sert `frontend/index.html`, route `POST /dashboard`. Page avec zone chat à gauche, zone dashboard à droite, chargement vega-embed par CDN.

**Phase 2 — Générateur Vega-Lite**
`build_vega_spec(intent, data) -> dict`. Teste-le toi-même avec des données factices pour chaque `chart_type` avant de brancher le reste. Vérifie le rendu des NULL.

**Phase 3 — Couche SQL sécurisée**
Sélection de la bonne vue selon `dimension`/`filters`, requêtes paramétrées via `db.py` et son pool.

**Phase 4 — Intégration Groq**
Prompt système forçant le JSON strict du contrat `DashboardIntent`. Teste toi-même avec au moins 10 prompts français variés couvrant les 3 practices, plusieurs statuts, et au moins un cas volontairement ambigu (vérifie que l'erreur est propre, pas un crash).

**Phase 5 — Pipeline complet**
`POST /dashboard` : texte → Groq → validation Pydantic + whitelist → sélection de vue → requête SQL → build_vega_spec → cache → réponse JSON → rendu `vegaEmbed` côté client.

**Phase 6 — Historique et cache persistant**
Tables MySQL `dashboard_requests` (prompt, intent JSON, timestamp) et `generated_dashboards` (hash, spec Vega, timestamp).

---

# Définition de "terminé"

L'application est considérée complète quand :
- Les 6 phases sont implémentées et connectées entre elles
- Tu as testé toi-même au moins 10 prompts utilisateur variés en français et documenté les résultats dans `PROGRESS.md`
- Aucune requête SQL n'est construite par concaténation de chaîne avec une valeur externe
- Le pool de connexions est actif et vérifiable dans `db.py`
- Les erreurs (LLM invalide, valeur hors whitelist, DB indisponible) renvoient un message clair au frontend sans crash serveur
- `PROGRESS.md` résume l'état final, les limites connues, et les prochaines améliorations possibles (hors scope : auth, multi-utilisateur, design front avancé — ne les implémente pas)

Ne me redemande pas confirmation entre les phases. Avance, corrige tes propres erreurs, et livre un système qui fonctionne réellement de bout en bout.
