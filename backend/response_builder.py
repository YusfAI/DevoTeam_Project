"""Build user-facing messages strictly from query results (no LLM hallucination)."""

from .labels import DEVISE, METRIC_LABELS, DIMENSION_LABELS, FILTER_LABELS
from .business_rules import FUNNEL_STAGE_ORDER, cap_heatmap_rows


def get_help_message() -> str:
    return (
        "Je peux analyser uniquement les données d'opportunités commerciales disponibles.\n\n"
        "Exemples :\n"
        "• « budget par pays pour Risk Advisory »\n"
        "• « combien d'offres gagnées ? »\n"
        "• « top 5 pays par budget »\n"
        "• « évolution du budget par mois pour Data Management »\n"
        "• « liste des opportunités urgentes (< 7 jours) »"
    )


def format_metric_value(value, metric: str) -> str:
    if value is None:
        return "N/A"
    if metric == "win_probability":
        # Stocké en base comme fraction 0-1 (0.74 = 74%).
        return f"{float(value) * 100:.1f} %"
    if metric == "nb_opportunities":
        return f"{int(value):,}".replace(",", " ")
    return f"{float(value):,.0f} {DEVISE}".replace(",", " ")


def extract_metric_value(row: dict, metric: str):
    val = row.get(metric)
    if val is None and metric == "budget":
        val = row.get("total_budget")
    if val is None and metric == "financial_offer":
        val = row.get("total_offer")
    if val is None and metric == "weighted_amount":
        val = row.get("total_weighted")
    return val


def _describe_filters(intent: dict) -> str:
    parts = []
    for key, value in intent.get("filters", {}).items():
        label = FILTER_LABELS.get(key, key)
        if isinstance(value, (list, tuple)):
            parts.append(f"{label} = {', '.join(str(v) for v in value)}")
        else:
            parts.append(f"{label} = {value}")
    for key, rule in intent.get("range_filters", {}).items():
        label = FILTER_LABELS.get(key, key)
        op = rule.get("op", "")
        value = rule.get("value", "")
        if op == "between" and isinstance(value, (list, tuple)) and len(value) == 2:
            parts.append(f"{label} entre {value[0]} et {value[1]}")
        else:
            parts.append(f"{label} {op} {value}")
    if not parts:
        return ""
    return " — filtres : " + ", ".join(parts)


def _top_entries(rows_with_values: list, metric: str, n: int = 3) -> str:
    sorted_rows = sorted(rows_with_values, key=lambda x: x[1], reverse=True)[:n]
    total = sum(v for _, v in rows_with_values)
    parts = []
    for dim, val in sorted_rows:
        pct = (val / total * 100) if total else 0
        parts.append(f"{dim} ({format_metric_value(val, metric)}, {pct:.0f} %)")
    return " | ".join(parts)


def _concentration_note(rows_with_values: list, total: float, dim_label: str) -> str:
    """Signale une concentration forte du total sur quelques valeurs.

    Le classement seul énumère des chiffres ; il ne dit pas si le portefeuille est
    réparti ou tenu par une poignée de lignes — or c'est cette information-là qui
    change une décision commerciale.

    Le seuil se compare à ce que donnerait une répartition UNIFORME (3/n), et non à
    une valeur fixe : sur cinq catégories, un partage parfaitement égal produit déjà
    60 % pour le top 3 : annoncer une « concentration » dans ce cas serait faux. On
    n'alerte donc qu'au-delà d'un tiers de plus que l'uniforme, et jamais sous 60 %.
    """
    n = len(rows_with_values)
    if total <= 0 or n < 5:
        return ""
    top3 = sum(v for _, v in sorted(rows_with_values, key=lambda x: x[1], reverse=True)[:3])
    part = top3 / total
    seuil = max(0.6, (3 / n) * 1.3)
    if part < seuil:
        return ""
    # « pays » est déjà pluriel : y ajouter un « s » donnait « payss ». Même cas pour
    # tout label finissant par s, x ou z, invariables au pluriel en français.
    pluriel = dim_label if dim_label[-1:].lower() in ("s", "x", "z") else f"{dim_label}s"
    return (f" À noter : les 3 premiers {pluriel} concentrent "
            f"{part * 100:.0f} % du total.")


def build_data_response(intent: dict, data: list) -> str:
    metric = intent.get("metric", "budget")
    dimension = intent.get("dimension", "")
    chart_type = intent.get("chart_type", "bar")
    goal = intent.get("goal", "")
    # Même règle que db_layer et sql_builder, et pour la même raison : la présence
    # d'un range_filter ne signifie PAS que l'utilisateur veut une liste. Elle le
    # faisait ici, et « combien d'affaires chaudes ? » répondait « 1 opportunité » —
    # le nombre de LIGNES du résultat agrégé, au lieu des 14 qu'il contenait. Le
    # souhait d'une liste s'exprime par use_raw_table ou chart_type == "table".
    use_raw = bool(intent.get("use_raw_table")) or chart_type == "table"
    filter_desc = _describe_filters(intent)
    metric_label = METRIC_LABELS.get(metric, metric)
    limit = int(intent.get("limit") or 0)

    if not data:
        return f"Aucune donnée trouvée{filter_desc}. Essayez d'élargir vos critères."

    if chart_type == "scatter":
        # data = lignes brutes par opportunité (budget, win_probability, weighted_amount) —
        # ni un chiffre unique ni une répartition par dimension, donc pas les branches ci-dessous.
        plotted = [r for r in data if r.get("budget") is not None and r.get("win_probability") is not None]
        if not plotted:
            return f"Aucune opportunité avec budget et probabilité de gain renseignés{filter_desc}."
        return (
            f"{len(plotted)} opportunité(s) avec budget et probabilité de gain renseignés{filter_desc} "
            "— survolez les points pour le détail (client, pays, statut)."
        )

    if chart_type == "funnel" and dimension:
        # data = toutes les valeurs du dimension demandé (ex: 19 statuts), pas seulement
        # les étapes du pipeline que le graphique affiche réellement (voir vega_generator.py
        # ::_build_funnel_rows) — sans ce filtre, le texte inclurait des statuts de sortie
        # ("Offre perdue"...) que l'entonnoir ne montre pas, et divergerait du graphique.
        stage_set = set(FUNNEL_STAGE_ORDER)
        rows_with_values = []
        for row in data:
            if row.get(dimension) not in stage_set:
                continue
            val = extract_metric_value(row, metric)
            if val is not None:
                rows_with_values.append((row.get(dimension), float(val)))
        if not rows_with_values:
            return f"Aucune étape du pipeline trouvée dans ces données{filter_desc}."
        total = sum(v for _, v in rows_with_values)
        top_line = _top_entries(rows_with_values, metric, 3)
        return (
            f"Entonnoir de vente — {metric_label}{filter_desc}. "
            f"Total : {format_metric_value(total, metric)} sur {len(rows_with_values)} étape(s) du pipeline. "
            f"Principales étapes : {top_line}."
        )

    if chart_type == "heatmap" and dimension:
        # data = toutes les valeurs de la dimension (ex: 21 pays), alors que le graphique
        # ne garde que les plus fortes (voir vega_generator.py::_cap_heatmap_rows) — le
        # même plafond est appliqué ici pour que le texte décrive ce qui est réellement
        # affiché, jamais une donnée plus large que le graphique.
        dim_label = DIMENSION_LABELS.get(dimension, dimension)
        capped, _ = cap_heatmap_rows(data, dimension, metric)
        totals: dict = {}
        for row in capped:
            key = row.get(dimension)
            val = extract_metric_value(row, metric)
            if val is not None:
                totals[key] = (totals.get(key) or 0) + val
        if not totals:
            return f"Aucune valeur de {metric_label} disponible{filter_desc}."
        grand_total = sum(totals.values())
        return (
            f"{metric_label.capitalize()} croisé(e) {dim_label} × practice{filter_desc}. "
            f"Total : {format_metric_value(grand_total, metric)} sur {len(totals)} {dim_label}(s) "
            f"et {len(capped)} combinaisons affichées."
        )

    if use_raw or chart_type == "table":
        budgets = [extract_metric_value(r, "budget") for r in data]
        budgets = [b for b in budgets if b is not None]
        total_budget = sum(budgets) if budgets else 0
        suffix = f" Budget total : {format_metric_value(total_budget, 'budget')}." if budgets else ""
        return f"{len(data)} opportunité(s){filter_desc}.{suffix}"

    if chart_type == "kpi_card" or (not dimension and len(data) == 1):
        val = extract_metric_value(data[0], metric)
        label = goal or metric_label.capitalize()
        return f"{label} : {format_metric_value(val, metric)}."

    if dimension:
        dim_label = DIMENSION_LABELS.get(dimension, dimension)
        rows_with_values = []
        for row in data:
            val = extract_metric_value(row, metric)
            if val is not None:
                rows_with_values.append((row.get(dimension, "?"), float(val)))

        if not rows_with_values:
            return f"Aucune valeur de {metric_label} disponible{filter_desc}."

        total = sum(v for _, v in rows_with_values)
        top_line = _top_entries(rows_with_values, metric, 3)
        prefix = f"{goal} — " if goal else ""
        limit_note = f" (top {limit})" if limit > 0 else ""
        return (
            f"{prefix}{metric_label.capitalize()} par {dim_label}{filter_desc}{limit_note}. "
            f"Total : {format_metric_value(total, metric)} sur {len(rows_with_values)} {dim_label}(s). "
            f"Classement : {top_line}.{_concentration_note(rows_with_values, total, dim_label)}"
        )

    val = extract_metric_value(data[0], metric)
    return f"Résultat{filter_desc} : {format_metric_value(val, metric)}."


# ---------------------------------------------------------------------------
# Ce qui a changé dans le tableau de bord
#
# Une demande de suite MODIFIE le tableau de bord affiché — elle n'en ouvre pas un
# autre. Sans le dire, l'utilisateur voit l'iframe se recharger et ne sait pas si sa
# demande a été prise en compte, ni ce qu'elle a touché. La phrase est construite par
# comparaison des deux intentions, jamais par le modèle : elle décrit donc ce qui a
# réellement changé dans les requêtes, pas ce qu'on croit avoir compris.
# ---------------------------------------------------------------------------

CHART_LABELS = {
    "bar": "barres", "line": "courbe", "area": "aire", "pie": "camembert",
    "table": "tableau", "kpi_card": "chiffre clé", "scatter": "nuage de points",
    "heatmap": "carte de chaleur", "funnel": "entonnoir",
}

# Au-delà, ce n'est plus une retouche mais une analyse différente : énumérer cinq
# changements serait plus long à lire que la réponse elle-même, et le mot
# « modifié » deviendrait trompeur.
_MAX_CHANGES_DESCRIBED = 3


def _filter_summary(filters: dict) -> str:
    parts = []
    for key, value in (filters or {}).items():
        label = FILTER_LABELS.get(key, key)
        if isinstance(value, (list, tuple)):
            value = " et ".join(str(v) for v in value)
        parts.append(f"{label} = {value}")
    return ", ".join(parts)


def list_changes(previous: dict, current: dict) -> list:
    """Différences entre deux intentions, en clair. Une liste vide signifie que la
    demande n'a rien changé — information à part entière, à ne pas confondre avec
    « trop de changements pour parler de modification » (voir describe_change)."""
    if not previous or not current:
        return []

    changements = []

    avant, apres = previous.get("metric"), current.get("metric")
    if avant != apres:
        changements.append(
            f"mesure : {METRIC_LABELS.get(avant, avant)} → {METRIC_LABELS.get(apres, apres)}")

    avant, apres = previous.get("dimension") or "", current.get("dimension") or ""
    if avant != apres:
        libelle = lambda d: DIMENSION_LABELS.get(d, d) if d else "aucun"
        changements.append(f"axe : {libelle(avant)} → {libelle(apres)}")

    avant, apres = previous.get("chart_type"), current.get("chart_type")
    if avant != apres:
        changements.append(
            f"affichage : {CHART_LABELS.get(avant, avant)} → {CHART_LABELS.get(apres, apres)}")

    avant, apres = previous.get("filters") or {}, current.get("filters") or {}
    if avant != apres:
        if not apres:
            changements.append("filtres retirés")
        elif not avant:
            changements.append(f"filtre ajouté : {_filter_summary(apres)}")
        else:
            changements.append(f"filtres : {_filter_summary(apres)}")

    avant, apres = int(previous.get("limit") or 0), int(current.get("limit") or 0)
    if avant != apres:
        changements.append(f"top {apres}" if apres else "classement complet rétabli")

    return changements


def describe_change(previous: dict, current: dict) -> str:
    """Phrase décrivant la modification du tableau de bord. Vide s'il n'y a rien à
    dire, ou si les deux analyses n'ont plus assez en commun pour qu'on parle encore
    de modification plutôt que d'analyse nouvelle."""
    changements = list_changes(previous, current)
    if not changements or len(changements) > _MAX_CHANGES_DESCRIBED:
        return ""
    return "Tableau de bord mis à jour — " + " ; ".join(changements) + "."
