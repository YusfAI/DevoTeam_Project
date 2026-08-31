"""Build user-facing messages strictly from query results (no LLM hallucination)."""

import re
import unicodedata

from .labels import (
    DEVISE, METRIC_LABELS, DIMENSION_LABELS, FILTER_LABELS,
    metric_label as libelle_metrique, distinct_label,
)
from .business_rules import (
    FUNNEL_STAGE_ORDER, HOT_DEAL_MIN_PROBABILITY, HOT_DEAL_STATUSES, LOST_STATUSES,
    cap_heatmap_rows, heatmap_secondary_dimension,
)


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

    # Le périmètre « affaires chaudes » ne passe plus par un filtre ordinaire : c'est
    # une réunion (remise OU ≥ 80 %), que les filtres — combinés par ET — ne savent
    # pas porter. Sans cette ligne, la phrase ne dirait plus rien de la restriction
    # appliquée, alors qu'elle l'annonçait quand la règle tenait dans une borne.
    if intent.get("hot_deals"):
        parts.append("affaires chaudes (%s, ou probabilité ≥ %g %%)"
                     % (", ".join(HOT_DEAL_STATUSES), HOT_DEAL_MIN_PROBABILITY * 100))
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
    # Les statuts EXCLUS font partie du périmètre au même titre que les statuts
    # retenus. Ne pas les dire laissait « budget des offres non gagnées » se lire
    # comme un total sans restriction : le chiffre était juste, la phrase muette sur
    # ce qu'il recouvrait. Seules les exclusions DEMANDÉES sont annoncées — celle des
    # affaires perdues est le comportement par défaut de l'application, décrit une
    # fois pour toutes, et l'énoncer à chaque réponse n'apprendrait rien.
    for statut in intent.get("exclude_statuses") or []:
        if statut not in LOST_STATUSES:
            parts.append(f"hors {FILTER_LABELS['status']} = {statut}")

    # Les exclusions sur les autres colonnes, pour la même raison : « budget par pays
    # hors Tunisie » affichait 69 370 001 DT sans que rien dans la phrase ne dise que
    # la Tunisie avait été retirée. Le chiffre était juste, la phrase incomplète — et
    # c'est justement sur ce périmètre-là que la question portait.
    for cle, valeur in (intent.get("exclude_filters") or {}).items():
        libelle = FILTER_LABELS.get(cle, cle)
        valeurs = valeur if isinstance(valeur, (list, tuple)) else [valeur]
        parts.append(f"hors {libelle} = {', '.join(str(v) for v in valeurs)}")

    if not parts:
        return ""
    return " — filtres : " + ", ".join(parts)


def _norm_titre(texte: str) -> str:
    """Forme comparable d'un intitulé : sans casse, sans accents, sans ponctuation.

    Sert uniquement à repérer qu'un titre répète la phrase qui le suit. La casse et
    les accents diffèrent souvent entre la question tapée et le libellé reconstruit,
    sans que le sens change.
    """
    sans_accents = unicodedata.normalize("NFD", (texte or "").lower())
    sans_accents = "".join(c for c in sans_accents if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", sans_accents).strip()


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


def _synthese(rows_with_values: list, metric: str, dim_label: str, moyenne: bool) -> str:
    """La phrase de synthèse qui suit le titre : « Total : … » sur des sommes,
    l'étendue des valeurs sur des moyennes.

    Additionner des moyennes ne produit rien d'interprétable — ni un total, ni une
    moyenne d'ensemble. Plutôt que d'afficher ce chiffre sans signification sous
    l'étiquette « Total », on dit ce que les données permettent réellement d'affirmer :
    entre quelles bornes se situent les moyennes comparées.
    """
    valeurs = [v for _, v in rows_with_values]
    if not moyenne:
        total = sum(valeurs)
        return f"Total : {format_metric_value(total, metric)} sur {len(valeurs)} {dim_label}(s). "
    return (f"{len(valeurs)} {dim_label}(s) comparé(s), de "
            f"{format_metric_value(min(valeurs), metric)} à "
            f"{format_metric_value(max(valeurs), metric)}. ")


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
    # Le libellé porte l'agrégation : « budget moyen par pays » et « budget par
    # pays » ne doivent pas se lire pareil, sans quoi rien ne distingue un total
    # d'une moyenne dans la phrase de réponse.
    metric_label = libelle_metrique(metric, intent.get("aggregation", ""))
    # Un comptage de valeurs distinctes n'est pas un nombre d'opportunités : dire
    # « Nombre d'opportunités par practice : 3 » là où on compte des practices
    # distinctes est faux deux fois — sur ce qui est compté, et sur la forme.
    compte = intent.get("count_distinct")
    if compte:
        metric_label = distinct_label(compte)
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
        # les étapes du pipeline que le graphique affiche réellement (voir sql_builder.py
        # ::funnel_sql) — sans ce filtre, le texte inclurait des statuts de sortie
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
        # ne garde que les plus fortes (voir sql_builder.py::MAX_CATEGORIES) — le
        # même plafond est appliqué ici pour que le texte décrive ce qui est réellement
        # affiché, jamais une donnée plus large que le graphique.
        dim_label = DIMENSION_LABELS.get(dimension, dimension)
        # Le second axe était écrit « practice » en dur : quand l'axe demandé ÉTAIT
        # la practice, le message annonçait « practice × practice » pendant que le
        # graphique croisait, lui, avec les pays.
        secondaire = heatmap_secondary_dimension(dimension)
        sec_label = DIMENSION_LABELS.get(secondaire, secondaire)
        capped, _ = cap_heatmap_rows(data, dimension, metric)
        totals: dict = {}
        for row in capped:
            key = row.get(dimension)
            val = extract_metric_value(row, metric)
            if val is not None:
                totals[key] = (totals.get(key) or 0) + val
        if not totals:
            return f"Aucune valeur de {metric_label} disponible{filter_desc}."

        # Le mot « Total » désignait la somme des seules cases AFFICHÉES : sur
        # « budget par pays et practice », il annonçait 103 340 001 DT là où le
        # portefeuille en pèse 103 900 001 — 560 000 DT et quatre pays écartés sous
        # une étiquette qui promettait l'exhaustivité. Le total redevient le vrai
        # total, et ce que la carte laisse de côté est dit plutôt que soustrait en
        # silence. Une ligne « Autres » n'aurait pas convenu ici : sur une matrice,
        # elle mélangerait des pays sans rapport dans une bande unique.
        affiche = sum(totals.values())
        reel = sum(v for v in (extract_metric_value(r, metric) for r in data) if v is not None)
        tous_les_pays = len({r.get(dimension) for r in data})

        phrase = (f"{metric_label.capitalize()} croisé(e) {dim_label} × {sec_label}{filter_desc}. "
                  f"Total : {format_metric_value(reel, metric)} sur {tous_les_pays} {dim_label}(s).")
        if len(totals) < tous_les_pays:
            ecartes = tous_les_pays - len(totals)
            phrase += (f" La carte montre les {len(totals)} premiers "
                       f"({format_metric_value(affiche, metric)}, {len(capped)} combinaisons) ; "
                       f"{ecartes} {dim_label}(s) de plus petit total n'y figurent pas.")
        else:
            phrase += f" {len(capped)} combinaisons affichées."
        return phrase

    if use_raw or chart_type == "table":
        budgets = [extract_metric_value(r, "budget") for r in data]
        budgets = [b for b in budgets if b is not None]
        total_budget = sum(budgets) if budgets else 0
        suffix = f" Budget total : {format_metric_value(total_budget, 'budget')}." if budgets else ""
        return f"{len(data)} opportunité(s){filter_desc}.{suffix}"

    if chart_type == "kpi_card" or (not dimension and len(data) == 1):
        val = extract_metric_value(data[0], metric)
        label = goal or metric_label.capitalize()
        # Un chiffre unique introuvable s'affichait « Budget : N/A. », sans dire ce
        # qui avait vidé le périmètre — alors que les autres formes annoncent, elles,
        # « Aucune donnée trouvée — filtres : … ». Un « N/A » nu se lit comme une
        # panne ; nommer le filtre en fait un résultat.
        if val is None:
            return (f"Aucune donnée trouvée{filter_desc}. Essayez d'élargir vos critères."
                    if filter_desc else
                    f"{label} : aucune valeur disponible dans les données.")
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

        # Ni une moyenne ni un comptage distinct ne s'ADDITIONNENT à travers les
        # catégories : un client servi par deux practices y figure deux fois, si bien
        # que « Total : 134 » s'affichait là où le portefeuille compte 84 clients.
        moyenne = intent.get("aggregation") == "avg" or bool(intent.get("count_distinct"))
        total = sum(v for _, v in rows_with_values)
        top_line = _top_entries(rows_with_values, metric, 3)
        # L'intitulé ne précède la phrase que s'il APPORTE quelque chose. Quand il
        # décrit déjà la même analyse — ce qui est le cas dès que le titre est
        # reconstruit depuis l'intention — la réponse se lisait « Budget par pays —
        # Budget par pays. Total : … », le même énoncé deux fois de suite.
        entete = f"{metric_label.capitalize()} par {dim_label}"
        prefix = f"{goal} — " if goal and _norm_titre(goal) != _norm_titre(entete) else ""
        limit_note = f" (top {limit})" if limit > 0 else ""
        # La note de concentration exprime une part du total : elle n'a de sens que
        # sur des sommes. Sur des moyennes, « les 3 premiers pèsent 60 % » ne veut
        # rien dire — on n'ajoute donc rien.
        note = "" if moyenne else _concentration_note(rows_with_values, total, dim_label)
        return (
            f"{prefix}{metric_label.capitalize()} par {dim_label}{filter_desc}{limit_note}. "
            f"{_synthese(rows_with_values, metric, dim_label, moyenne)}"
            f"Classement : {top_line}.{note}"
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


_AGREGATION_LABELS = {"sum": "total", "avg": "moyenne", "count": "comptage"}


def _borne_summary(range_filters: dict) -> str:
    """« probabilité de gain >= 0.8 » — les bornes en clair, pour le récit du
    changement. Le même vocabulaire que `_describe_filters`, en plus court."""
    morceaux = []
    for cle, regle in range_filters.items():
        libelle = FILTER_LABELS.get(cle, cle)
        valeur = regle.get("value", "")
        if regle.get("op") == "between" and isinstance(valeur, (list, tuple)) and len(valeur) == 2:
            morceaux.append("%s entre %s et %s" % (libelle, valeur[0], valeur[1]))
        else:
            morceaux.append("%s %s %s" % (libelle, regle.get("op", ""), valeur))
    return ", ".join(morceaux)


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

    # Trois champs manquaient à cette comparaison, et une retouche qui ne touchait
    # qu'eux s'annonçait donc « rien n'a changé » alors que les chiffres à l'écran
    # venaient de bouger. « en somme » après « budget moyen par pays » en était le cas
    # le plus net : la somme remplaçait la moyenne, et le message disait le contraire.
    avant, apres = previous.get("aggregation") or "sum", current.get("aggregation") or "sum"
    if avant != apres:
        changements.append("calcul : %s → %s" % (_AGREGATION_LABELS.get(avant, avant),
                                                 _AGREGATION_LABELS.get(apres, apres)))

    avant, apres = previous.get("range_filters") or {}, current.get("range_filters") or {}
    if avant != apres:
        changements.append("bornes retirées" if not apres
                           else "bornes : %s" % _borne_summary(apres))

    avant = set(previous.get("exclude_statuses") or [])
    apres = set(current.get("exclude_statuses") or [])
    if avant != apres:
        ajoutes = sorted(apres - avant)
        changements.append("exclusions : %s" % ", ".join(ajoutes) if ajoutes
                           else "exclusions levées")

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
