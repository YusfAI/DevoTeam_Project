# -*- coding: utf-8 -*-
"""Réécrit dac/dashboards/accueil.yml. À lancer depuis la racine du projet.

La vue d'ensemble répond d'abord aux trois questions posées par le métier :
combien d'offres remises depuis novembre 2025, comment elles se répartissent par
practice, et ce qu'elles sont devenues (gagnées / perdues / en attente). Le reste
— santé du portefeuille, pipeline, urgences — vient ensuite.

Les 12 étapes du pipeline et les listes de statuts sont dérivées de
business_rules.py plutôt que recopiées : une divergence entre deux widgets
fausserait les taux sans qu'aucun test ne le voie.
"""
import pathlib
import sys

sys.path.insert(0, ".")
from backend.business_rules import (
    FUNNEL_STAGE_ORDER, HOT_DEAL_MIN_PROBABILITY, HOT_DEAL_STATUSES, LOST_STATUSES,
    PENDING_SUBMISSION, SUBMITTED_STATUSES, WON_STATUSES,
)


def q(v):
    return "'" + v.replace("'", "''") + "'"


def liste(valeurs):
    return ", ".join(q(v) for v in valeurs)


PERDUS = liste(LOST_STATUSES)
CASES = "\n".join(
    "                WHEN %s THEN %d" % (q(s), i + 1) for i, s in enumerate(FUNNEL_STAGE_ORDER)
)
STAGES = ",\n".join(
    "              " + liste(FUNNEL_STAGE_ORDER[i:i + 3])
    for i in range(0, len(FUNNEL_STAGE_ORDER), 3)
)

# Les deux filtres de tête, injectés en Jinja dans CHAQUE requête.
PRACTICE = (
    "          {% if filters.practice != 'Toutes' %}\n"
    "            AND practice = '{{ filters.practice }}'\n"
    "          {% endif %}"
)
PERIODE = (
    "          {% if filters.periode == 'Depuis novembre 2025' %}\n"
    "            AND deadline >= DATE '2025-11-01'\n"
    "          {% elif filters.periode == '12 derniers mois' %}\n"
    "            AND deadline >= CURRENT_DATE - INTERVAL 12 MONTH\n"
    "          {% elif filters.periode == 'Depuis janvier 2026' %}\n"
    "            AND deadline >= DATE '2026-01-01'\n"
    "          {% endif %}"
)
FILTRES = PERIODE + "\n" + PRACTICE

# Une offre est « remise » si son statut atteste qu'elle est partie chez le client —
# y compris quand elle a été gagnée ou perdue depuis. « À date » borne à aujourd'hui :
# une échéance encore à venir signifie que l'offre n'est pas encore remise.
REMISES_CTE = """          WITH remises AS (
            SELECT *,
              CASE
                WHEN status IN (%s) THEN 'Gagnée'
                WHEN status IN (%s) THEN 'Perdue'
                ELSE 'En attente'
              END AS issue
            FROM opportunities
            WHERE status IN (%s)
              AND deadline <= CURRENT_DATE
%s
          )""" % (
    liste(WON_STATUSES),
    liste([s for s in SUBMITTED_STATUSES
           if s not in WON_STATUSES and s not in PENDING_SUBMISSION]),
    liste(SUBMITTED_STATUSES),
    FILTRES,
)

# Les trois issues sont énumérées en dur et jointes en LEFT JOIN : elles restent
# ainsi présentes même à zéro. Sans cela, une période sans aucune offre perdue
# décalerait l'ordre des séries — et Recharts attribuant ses couleurs par rang,
# « Gagnée » changerait de couleur d'un filtre à l'autre.
ISSUES = ("          issues(issue, rang) AS (\n"
          "            VALUES ('Gagnée', 1), ('Perdue', 2), ('En attente', 3)\n"
          "          )")


def kpi(name, col, corps, fmt, desc=None):
    d = "\n        description: %s" % desc if desc else ""
    return ("      - name: %s\n"
            "        type: metric\n"
            "        col: %d%s\n"
            "        sql: |\n"
            "%s\n"
            '        value: { field: value, type: number, format: "%s" }' % (name, col, d, corps, fmt))


def kpi_remises(name, col, expr, fmt, desc=None):
    return kpi(name, col, REMISES_CTE + "\n          SELECT %s AS value FROM remises" % expr, fmt, desc)


# Affaire chaude : offre déjà partie chez le client, forte probabilité de gain,
# décision pas encore tombée. Pas de borne haute sur l'échéance ici, contrairement
# aux offres remises : ces affaires sont par définition tournées vers l'avenir, les
# limiter aux échéances passées viderait le tableau de son intérêt.
CHAUDES_CTE = """          WITH chaudes AS (
            SELECT * FROM opportunities
            WHERE win_probability >= %s
              AND status IN (%s)
%s
          )""" % (HOT_DEAL_MIN_PROBABILITY, liste(HOT_DEAL_STATUSES), FILTRES)


def kpi_chaudes(name, col, expr, fmt, desc=None):
    return kpi(name, col, CHAUDES_CTE + "\n          SELECT %s AS value FROM chaudes" % expr, fmt, desc)


def actif(expr, extra=""):
    """Portefeuille actif : affaires perdues exclues (règle par défaut de l'app)."""
    return ("          SELECT %s AS value FROM opportunities\n"
            "          WHERE status NOT IN (%s)%s\n%s" % (expr, PERDUS, extra, FILTRES))


def etapes_cte():
    return ("          WITH etapes AS (\n"
            "            SELECT status, COUNT(*) AS nb,\n"
            "              CASE status\n" + CASES + "\n"
            "              END AS rang\n"
            "            FROM opportunities\n"
            "            WHERE status IN (\n" + STAGES + "\n"
            "            )\n" + FILTRES + "\n"
            "            GROUP BY status\n"
            "          )")


HEADER = """schema: https://getbruin.com/schemas/dac/dashboard/v1
name: Vue d'ensemble commerciale
description: Les offres remises depuis novembre 2025, ce qu'elles sont devenues, et l'état du portefeuille
connection: devoteam_duckdb

# ATTENTION : fichier PRODUIT par scripts/generate_accueil.py, à ne pas éditer à la
# main — toute modification directe serait perdue à la prochaine génération. Il reste
# versionné et relu en revue (c'est un dashboard « as code »), mais son générateur
# existe pour une raison précise : les 12 étapes du pipeline et la liste des statuts
# perdus sont recopiées dans plusieurs widgets, et deux copies qui divergent
# fausseraient les taux sans qu'aucun test ne le voie. Elles sont donc dérivées de
# backend/business_rules.py, source unique.
#
#   python scripts/generate_accueil.py     (depuis la racine du projet)
#
# Les données viennent du fichier DuckDB réécrit à chaque rafraîchissement du Google
# Sheet (backend/duckdb_export.py).
#
# CE QU'EST UNE « OFFRE REMISE ». Le statut décrit l'état COURANT : une offre partie
# chez le client et gagnée depuis n'est plus au statut « Offre remise ». Compter ce
# seul statut donnerait 4 offres au lieu de 57. Sont donc comptées comme remises les
# opportunités dont le statut atteste le dépôt — Offre remise, En attente du plan de
# charge, Offre gagnée, Offre signée, Offre perdue (définition arrêtée avec le métier,
# voir business_rules.SUBMITTED_STATUSES).
#
# « À DATE ». Il n'existe pas de colonne « date de remise » : l'échéance en tient
# lieu, car pour un appel d'offres la date limite de dépôt EST la date de remise. La
# borne haute est aujourd'hui — une échéance à venir signifie que l'offre n'est pas
# encore partie (20 opportunités sont dans ce cas et sortent donc du compte).
#
# EXCLUSION DES AFFAIRES PERDUES. La règle par défaut de l'application les écarte de
# tous les chiffres (66,1 M€ d'affaires mortes dans un « budget total » ne servent
# aucune décision). Elle est LEVÉE dans le bloc « offres remises », qui filtre
# lui-même sur le statut : c'est exactement l'échappatoire prévue — sans elle, la
# question « combien de perdues ? » ne pourrait pas recevoir de réponse. Le bloc
# « portefeuille » plus bas, lui, applique l'exclusion.
#
# Les 12 étapes de l'entonnoir sont la transcription exacte de
# business_rules.FUNNEL_STAGE_ORDER.
#
# COULEURS. Bruin DAC attribue les couleurs de série par rang dans le résultat, sans
# permettre de fixer « Gagnée = vert ». Les issues sont donc énumérées en dur et
# jointes en LEFT JOIN pour rester dans un ordre constant même à zéro, et ce sont les
# étiquettes — pas la couleur — qui portent le sens.
filters:
  - name: periode
    type: select
    multiple: false
    default: "Depuis novembre 2025"
    options:
      values: ["Depuis novembre 2025", "12 derniers mois", "Depuis janvier 2026", "Tout l'historique"]

  - name: practice
    type: select
    multiple: false
    default: "Toutes"
    options:
      values: ["Toutes", "Digital Transformation", "Risk Advisory", "Data Management"]

rows:
  # === Q1 et Q3 : combien d'offres remises, et ce qu'elles sont devenues ===
  - widgets:
"""

ligne1 = "\n\n".join([
    kpi_remises("Offres remises", 3, "COUNT(*)", ",.0f",
                "Offres effectivement déposées sur la période, échéance déjà passée."),
    kpi_remises("Gagnées", 3, "COUNT(*) FILTER (WHERE issue = 'Gagnée')", ",.0f",
                "Offres gagnées ou déjà signées."),
    kpi_remises("Perdues", 3, "COUNT(*) FILTER (WHERE issue = 'Perdue')", ",.0f"),
    kpi_remises("En attente", 3, "COUNT(*) FILTER (WHERE issue = 'En attente')", ",.0f",
                "Déposées, sans décision du client à ce jour."),
])

ligne2 = "\n\n".join([
    kpi_remises("Taux de réussite", 4,
                "COUNT(*) FILTER (WHERE issue = 'Gagnée') * 1.0\n"
                "                 / NULLIF(COUNT(*) FILTER (WHERE issue <> 'En attente'), 0)",
                ".1%",
                "Gagnées rapportées aux seules offres DÉCIDÉES — les offres en attente "
                "ne sont ni un succès ni un échec, les compter au dénominateur écraserait le taux."),
    kpi_remises("Budget remis", 4, "SUM(budget)", ",.0f",
                "Montant total des offres déposées sur la période."),
    kpi_remises("Budget gagné", 4, "SUM(budget) FILTER (WHERE issue = 'Gagnée')", ",.0f"),
])

BODY = """

  - widgets:
      - name: Issue des offres remises
        type: chart
        chart: pie
        col: 6
        description: Trois parts d'un même total — le pourcentage s'affiche sur chaque part.
        sql: |
__REMISES__,
__ISSUES__
          SELECT i.issue, COUNT(r.id) AS nb
          FROM issues i
          LEFT JOIN remises r ON r.issue = i.issue
          GROUP BY i.issue, i.rang
          ORDER BY i.rang
        label: issue
        value: { field: nb }

      - name: Offres remises par practice
        type: chart
        chart: pie
        col: 6
        description: Répartition des offres déposées entre les trois practices.
        sql: |
__REMISES__
          SELECT practice, COUNT(*) AS nb
          FROM remises
          GROUP BY practice
          ORDER BY nb DESC
        label: practice
        value: { field: nb }

  - widgets:
      - name: Issue par practice
        type: chart
        chart: bar
        col: 6
        stacked: true
        description: >-
          Où l'on gagne, et où l'on perd. Barres empilées plutôt que côte à côte : la
          hauteur totale reste le volume déposé par practice, lisible en même temps
          que sa composition.
        sql: |
__REMISES__,
__ISSUES__,
          practices AS (SELECT DISTINCT practice FROM remises)
          SELECT p.practice, i.issue, COUNT(r.id) AS nb
          FROM practices p
          CROSS JOIN issues i
          LEFT JOIN remises r ON r.practice = p.practice AND r.issue = i.issue
          GROUP BY p.practice, i.issue, i.rang
          ORDER BY p.practice, i.rang
        x: { field: practice, type: category, title: Practice }
        y: { field: nb, type: number, title: Offres remises, format: ",.0f" }
        color: { field: issue }

      - name: Offres remises par mois
        type: chart
        chart: bar
        col: 6
        stacked: true
        description: >-
          Rythme de dépôt et issue mois par mois. Barres empilées et non courbe : une
          courbe montrerait le volume mais pas sa composition, qui est ici l'essentiel.
        sql: |
__REMISES__,
__ISSUES__,
          mois AS (SELECT DISTINCT deadline_month AS m FROM remises WHERE deadline_month IS NOT NULL)
          SELECT mo.m AS mois, i.issue, COUNT(r.id) AS nb
          FROM mois mo
          CROSS JOIN issues i
          LEFT JOIN remises r ON r.deadline_month = mo.m AND r.issue = i.issue
          GROUP BY mo.m, i.issue, i.rang
          ORDER BY mo.m, i.rang
        x: { field: mois, type: category, title: Mois d'échéance }
        y: { field: nb, type: number, title: Offres remises, format: ",.0f" }
        color: { field: issue }

  # === Affaires chaudes : l'offre est partie, la décision approche ===
  - widgets:
__CHAUDES_KPI__

  - widgets:
      - name: Affaires chaudes par practice
        type: chart
        chart: bar
        col: 12
        description: Nombre d'affaires chaudes par practice.
        sql: |
__CHAUDES__
          SELECT practice, COUNT(*) AS nb
          FROM chaudes
          GROUP BY practice
          ORDER BY nb DESC
        x: { field: practice, type: category, title: Practice }
        y: { field: nb, type: number, title: Affaires chaudes, format: ",.0f" }
        color: { field: practice }

  - widgets:
      - name: Détail des affaires chaudes
        type: table
        col: 12
        description: >-
          Pondération SUPÉRIEURE OU ÉGALE à 80 % — 90 % ou 100 % y figureraient aussi.
          Si aucune n'apparaît à 100 %, c'est que dans ces données 100 % n'est pas une
          prévision mais un constat : les 88 opportunités à 100 % sont exactement les
          88 déjà gagnées ou signées, et une affaire dont la décision est tombée n'est
          plus en jeu. Classées par montant pondéré décroissant, les plus grosses
          espérances de gain d'abord. La pondération est convertie en pourcentage dans
          la requête plutôt que confiée au format d'affichage, dont la prise en charge
          des pourcentages dans les tableaux DAC n'est pas garantie.
        sql: |
__CHAUDES__
          SELECT description, buyer, practice, budget,
                 ROUND(win_probability * 100) AS ponderation,
                 weighted_amount, deadline
          FROM chaudes
          ORDER BY weighted_amount DESC
        columns:
          - { name: description, label: Opportunité }
          - { name: buyer, label: Client }
          - { name: practice, label: Practice }
          - { name: budget, label: Budget, number: currency }
          - { name: ponderation, label: Pondération %, number: number }
          - { name: weighted_amount, label: Montant pondéré, number: currency }
          - { name: deadline, label: Échéance }

  # === Santé du portefeuille — affaires perdues exclues ===
  - widgets:
"""

ligne3 = "\n\n".join([
    kpi("Budget actif", 3, actif("SUM(budget)"), ",.0f",
        "Budget estimé côté client, hors affaires perdues, infructueuses, NO GO, hors scope et non shortlistées."),
    kpi("Offre financière", 3, actif("SUM(financial_offer)"), ",.0f",
        "Montant réellement proposé par DevoTeam, sur le même périmètre."),
    kpi("Écart offre / budget", 3,
        actif("(SUM(financial_offer) - SUM(budget)) / NULLIF(SUM(budget), 0)"), "+.1%",
        "Négatif = nous chiffrons en dessous du budget annoncé par le client."),
    kpi("Montant pondéré", 3, actif("SUM(weighted_amount)"), ",.0f",
        "Offre financière × probabilité de gain, sur les seules opportunités où elle est "
        "renseignée — environ la moitié du portefeuille."),
])

FOOTER = """

  # === Pipeline : où en sont les affaires encore ouvertes ===
  - widgets:
      - name: Entonnoir de vente
        type: chart
        chart: funnel
        col: 6
        description: Nombre d'opportunités ayant atteint au moins chaque étape.
        # Cumul depuis la fin : une opportunité signée a nécessairement franchi les
        # étapes précédentes. Compter les statuts bruts ne décroîtrait pas et ne
        # formerait donc pas un entonnoir (voir backend/sql_builder.funnel_sql).
        sql: |
__ETAPES__
          SELECT status, SUM(nb) OVER (ORDER BY rang DESC ROWS UNBOUNDED PRECEDING) AS atteint
          FROM etapes
          ORDER BY rang
        label: status
        value: { field: atteint }

      - name: Taux de passage entre étapes
        type: chart
        chart: bar
        col: 6
        description: Part des opportunités ayant atteint une étape qui franchissent la suivante.
        sql: |
__ETAPES__,
          cumul AS (
            SELECT status, rang,
              SUM(nb) OVER (ORDER BY rang DESC ROWS UNBOUNDED PRECEDING) AS atteint
            FROM etapes
          )
          SELECT status,
            atteint * 1.0 / NULLIF(LAG(atteint) OVER (ORDER BY rang), 0) AS taux
          FROM cumul
          ORDER BY rang
        x: { field: status, type: category, title: Étape }
        y: { field: taux, type: number, title: Taux de passage, format: ".0%" }
        color: { field: status }

  - widgets:
      - name: Budget actif par pays
        type: chart
        chart: bar
        col: 12
        description: Les 10 pays au budget actif le plus élevé.
        sql: |
          SELECT country, SUM(budget) AS budget FROM opportunities
          WHERE status NOT IN (__PERDUS__)
__FILTRES__
          GROUP BY 1
          ORDER BY 2 DESC
          LIMIT 10
        x: { field: country, type: category, title: Pays }
        y: { field: budget, type: number, title: Budget, format: ",.0f" }
        color: { field: country }

  # === Ce qu'il faut traiter maintenant ===
  - widgets:
      - name: Opportunités urgentes (échéance ≤ 7 jours)
        type: table
        col: 12
        description: >-
          Opportunités encore ouvertes uniquement. Seul widget tourné vers l'avenir :
          la borne « à date » des offres remises ne s'y applique pas, sinon il serait
          toujours vide.
        sql: |
          SELECT buyer, country, practice, status, deadline, days_remaining, budget
          FROM opportunities
          WHERE days_remaining BETWEEN 0 AND 7
            AND status NOT IN (
              'Offre gagnée', 'Offre perdue', 'Offre signée', 'Infructueux',
              'NO GO', 'Hors scope', 'Non shortlisté'
            )
__FILTRES__
          ORDER BY days_remaining ASC
        columns:
          - { name: buyer, label: Client }
          - { name: country, label: Pays }
          - { name: practice, label: Practice }
          - { name: status, label: Statut }
          - { name: deadline, label: Échéance }
          - { name: days_remaining, label: Jours restants, number: number }
          - { name: budget, label: Budget, number: currency }
"""

NOUVELLE_LIGNE = """

  - widgets:
"""

chaudes_kpi = "\n\n".join([
    kpi_chaudes("Affaires chaudes", 4, "COUNT(*)", ",.0f",
                "Offres remises dont la probabilité de gain est d'au moins 80 % — 90 % et "
                "100 % compris — et dont la décision n'est pas tombée."),
    kpi_chaudes("Budget en jeu", 4, "SUM(budget)", ",.0f",
                "Budget cumulé des affaires chaudes."),
    kpi_chaudes("Montant pondéré en jeu", 4, "SUM(weighted_amount)", ",.0f",
                "Offre financière × probabilité — l'espérance de gain de ces affaires."),
])

doc = HEADER + ligne1 + NOUVELLE_LIGNE + ligne2 + BODY + ligne3 + FOOTER
doc = (doc.replace("__CHAUDES_KPI__", chaudes_kpi)
          .replace("__CHAUDES__", CHAUDES_CTE)
          .replace("__REMISES__", REMISES_CTE)
          .replace("__ISSUES__", ISSUES)
          .replace("__ETAPES__", etapes_cte())
          .replace("__PERDUS__", PERDUS)
          .replace("__FILTRES__", FILTRES))

pathlib.Path("dac/dashboards/accueil.yml").write_text(doc, encoding="utf-8")

import yaml
parsed = yaml.safe_load(doc)
print("YAML valide : %d lignes, %d widgets" % (
    len(parsed["rows"]), sum(len(r["widgets"]) for r in parsed["rows"])))
for r in parsed["rows"]:
    total = sum(w["col"] for w in r["widgets"])
    assert total == 12, "ligne incomplète : %d/12" % total

# Une ligne entière OUBLIÉE dans l'assemblage laisse la grille parfaitement remplie :
# vérifier la grille ne suffit donc pas, il faut aussi compter ce qui doit être là.
noms = [w["name"] for r in parsed["rows"] for w in r["widgets"]]
attendus = [
    "Offres remises", "Gagnées", "Perdues", "En attente",
    "Taux de réussite", "Budget remis", "Budget gagné",
    "Issue des offres remises", "Offres remises par practice",
    "Issue par practice", "Offres remises par mois",
    "Affaires chaudes", "Budget en jeu", "Montant pondéré en jeu",
    "Affaires chaudes par practice", "Détail des affaires chaudes",
    "Budget actif", "Offre financière", "Écart offre / budget", "Montant pondéré",
    "Entonnoir de vente", "Taux de passage entre étapes", "Budget actif par pays",
    "Opportunités urgentes (échéance ≤ 7 jours)",
]
manquants = [n for n in attendus if n not in noms]
assert not manquants, "widgets manquants : %s" % manquants
print("grille 12 colonnes respectée, %d widgets attendus tous présents" % len(attendus))
