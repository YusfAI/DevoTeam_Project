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
    FUNNEL_STAGE_ORDER, LOST_STATUSES, PENDING_SUBMISSION,
    SUBMITTED_STATUSES, WON_STATUSES, hot_deal_sql,
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

# Les trois filtres de tête, injectés en Jinja dans CHAQUE requête — sauf le
# tableau des urgences, qui échappe aux deux dates (voir son commentaire).
PRACTICE = (
    "          {% if filters.practice != 'Toutes' %}\n"
    "            AND practice = '{{ filters.practice }}'\n"
    "          {% endif %}"
)
# Chaque borne sous sa propre condition : vider un champ de date doit lever CETTE
# borne-là et garder l'autre, ce qu'un BETWEEN ne permettrait pas.
PERIODE = (
    "          {% if filters.Date_de_debut %}\n"
    "            AND deadline >= DATE '{{ filters.Date_de_debut }}'\n"
    "          {% endif %}\n"
    "          {% if filters.Date_de_fin %}\n"
    "            AND deadline <= DATE '{{ filters.Date_de_fin }}'\n"
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


def _bloc(texte, indent="          "):
    """Description en bloc plié (`>-`) plutôt qu'en scalaire nu.

    Un scalaire nu contenant « : » suivi d'un espace est lu par YAML comme une
    association clé/valeur, et le fichier devient invalide — panne rencontrée sur la
    première description qui a eu le tort d'être bien ponctuée. Le bloc plié accepte
    n'importe quelle ponctuation.
    """
    mots, lignes, courante = texte.split(), [], ""
    for mot in mots:
        if courante and len(courante) + 1 + len(mot) > 78:
            lignes.append(courante)
            courante = mot
        else:
            courante = "%s %s" % (courante, mot) if courante else mot
    if courante:
        lignes.append(courante)
    return ">-\n" + "\n".join(indent + ligne for ligne in lignes)


# Ferme la rangée en cours et en ouvre une nouvelle, au milieu d'un bloc de widgets.
# Six KPI ne tiennent pas sur les 12 colonnes d'une rangée ; les couper permet de
# garder chaque valeur COLLÉE à sa part — c'est ce voisinage qui les rend lisibles,
# et le renvoyer à une rangée séparée l'aurait perdu.
_RUPTURE_DE_LIGNE = "\n\n  - widgets:\n"


def kpi(name, col, corps, fmt, desc=None):
    d = "\n        description: %s" % _bloc(desc) if desc else ""
    return ("      - name: %s\n"
            "        type: metric\n"
            "        col: %d%s\n"
            "        sql: |\n"
            "%s\n"
            '        value: { field: value, type: number, format: "%s" }' % (name, col, d, corps, fmt))


def kpi_remises(name, col, expr, fmt, desc=None):
    return kpi(name, col, REMISES_CTE + "\n          SELECT %s AS value FROM remises" % expr, fmt, desc)


# Affaire chaude : probablement gagnée, PAS ENCORE gagnée — déjà remise, OU
# probabilité dans [80 %, 100 %[. Une réunion, pas une intersection : l'un des deux
# critères suffit. La borne haute est exclue parce que 100 % n'est pas une prévision
# ici mais un constat : les 88 lignes à 1,0 sont toutes déjà gagnées ou signées.
# Les offres perdues sortent d'elles-mêmes : ni leur statut ni leur probabilité
# (vide) ne les retiennent.
#
# La condition vient de business_rules.hot_deal_sql, la même que celle qu'appliquent
# le chat et les tableaux de bord générés. La recopier ici l'aurait fait diverger au
# premier changement de définition — et elle a déjà changé deux fois.
#
# Pas de borne haute sur l'échéance, contrairement aux offres remises : la question
# porte sur la confiance, pas sur une fenêtre de dépôt.
CHAUDES_CTE = """          WITH chaudes AS (
            SELECT * FROM opportunities
            WHERE %s
%s
          )""" % (hot_deal_sql(), FILTRES)


def table_chaudes():
    """LE détail des affaires chaudes : une seule table, pleine largeur.

    Elle a longtemps été découpée — trois colonnes, puis deux — parce que la
    définition d'alors en retenait plus d'une centaine et que le tableau de DAC ne
    défile pas verticalement : la page devenait interminable. La borne haute sur la
    probabilité a ramené le périmètre à ce qu'il désigne vraiment, une poignée
    d'affaires encore à gagner. Le découpage n'a plus d'objet, et la pleine largeur
    laisse enfin la place aux huit colonnes.

    Le rang reste affiché : il dit d'un coup d'œil où l'on en est dans le classement
    par espérance de gain, qui est l'ordre de lecture utile.
    """
    return (
        "      - name: Détail des affaires chaudes\n"
        "        type: table\n"
        "        col: 12\n"
        "        description: >-\n"
        "          Toutes les affaires encore à gagner, par espérance de gain\n"
        "          décroissante.\n"
        "        sql: |\n"
        "%s\n"
        "          SELECT ROW_NUMBER() OVER (ORDER BY weighted_amount DESC) AS rang,\n"
        "                 description, buyer, practice, status, budget, win_probability,\n"
        "                 weighted_amount\n"
        "          FROM chaudes\n"
        "          ORDER BY weighted_amount DESC\n"
        "        columns:\n"
        "          - { name: rang, label: \"N°\", number: number }\n"
        "          - { name: description, label: Opportunité }\n"
        "          - { name: buyer, label: Client }\n"
        "          - { name: practice, label: Practice }\n"
        "          - { name: status, label: Statut }\n"
        "          - { name: budget, label: Budget (DT), number: number }\n"
        "          - { name: win_probability, label: Probabilité, number: percent }\n"
        "          - { name: weighted_amount, label: Montant pondéré (DT), number: number }"
        % CHAUDES_CTE
    )


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
# tous les chiffres (66,1 MDT d'affaires mortes dans un « budget total » ne servent
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
  # Deux champs de date plutôt qu'un sélecteur de plage : les bornes sont nommées et
  # se lisent d'un coup d'œil. Chacune ouvre le calendrier natif du navigateur.
  #
  # Le libellé affiché EST le nom du filtre, tirets bas convertis en espaces — le
  # schéma n'a pas de champ `label`. D'où ces noms, choisis pour ce qu'ils affichent
  # (« Date de debut », « Date de fin ») et sans accent, puisqu'ils servent aussi
  # d'identifiants dans les gabarits Jinja.
  #
  # La borne de fin par défaut dépasse volontairement la dernière échéance des données
  # (2026-12-29) : plusieurs widgets regardent vers l'AVENIR — budget actif, entonnoir,
  # pipeline — et une borne fixée à aujourd'hui les amputerait de tout le portefeuille
  # en cours. À étendre le jour où des échéances iront au-delà.
  - name: Date_de_debut
    type: date
    default: "2025-11-01"

  - name: Date_de_fin
    type: date
    default: "2026-12-31"

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
                "Offres déposées sur la période, échéance déjà passée."),
    kpi_remises("Gagnées", 3, "COUNT(*) FILTER (WHERE issue = 'Gagnée')", ",.0f",
                "Gagnées ou déjà signées."),
    kpi_remises("Perdues", 3, "COUNT(*) FILTER (WHERE issue = 'Perdue')", ",.0f",
                "Décision défavorable du client."),
    kpi_remises("En attente", 3, "COUNT(*) FILTER (WHERE issue = 'En attente')", ",.0f",
                "Déposées, sans décision du client à ce jour."),
])

ligne2 = "\n\n".join([
    kpi_remises("Taux de réussite", 4,
                "COUNT(*) FILTER (WHERE issue = 'Gagnée') * 1.0\n"
                "                 / NULLIF(COUNT(*) FILTER (WHERE issue <> 'En attente'), 0)",
                ".1%",
                "Gagnées ÷ offres décidées. Les offres en attente ne comptent pas au dénominateur."),
    kpi_remises("Budget remis (DT)", 4, "SUM(budget)", ",.0f",
                "Budget cumulé des offres déposées."),
    kpi_remises("Budget gagné (DT)", 4, "SUM(budget) FILTER (WHERE issue = 'Gagnée')", ",.0f",
                "Part du budget remis effectivement remportée."),
])

BODY = """

  - widgets:
      - name: Issue des offres remises
        type: chart
        chart: pie
        col: 6
        description: Part des offres gagnées, perdues et en attente.
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
        description: Répartition des dépôts entre les trois practices.
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
        # Barres empilées plutôt que côte à côte : la hauteur totale reste le volume
        # déposé par practice, lisible en même temps que sa composition.
        description: Où l'on gagne et où l'on perd, practice par practice.
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
        # Barres empilées et non courbe : une courbe montrerait le volume mais pas sa
        # composition, qui est ici l'essentiel.
        description: Rythme de dépôt et issue, mois par mois.
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

  # === Affaires chaudes : les opportunités à 80 % de probabilité ou plus ===
  - widgets:
__CHAUDES_KPI__

  - widgets:
      - name: Affaires chaudes par practice
        type: chart
        chart: bar
        col: 6
        description: Combien chaque practice en compte, en valeur absolue.
        sql: |
__CHAUDES__
          SELECT practice, COUNT(*) AS nb
          FROM chaudes
          GROUP BY practice
          ORDER BY nb DESC
        x: { field: practice, type: category, title: Practice }
        y: { field: nb, type: number, title: Affaires chaudes, format: ",.0f" }
        color: { field: practice }

      # Le camembert PORTE les pourcentages : DAC écrit « nom NN % » sur chaque part,
      # sans qu'il faille les calculer. Les barres à côté donnent les valeurs
      # absolues ; les deux répondent à des questions différentes — « combien » et
      # « quelle proportion » — et trois practices restent sous le plafond de six
      # parts au-delà duquel deux angles voisins ne se comparent plus à l'œil.
      - name: Poids de chaque practice
        type: chart
        chart: pie
        col: 6
        description: La même répartition en pourcentages du total des affaires chaudes.
        sql: |
__CHAUDES__
          SELECT practice, COUNT(*) AS nb
          FROM chaudes
          GROUP BY practice
          ORDER BY nb DESC
        label: practice
        value: { field: nb }


  # Le détail des affaires chaudes, réparti sur TROIS colonnes côte à côte.
  #
  # Le tableau de Bruin DAC ne défile pas verticalement : son élément externe porte
  # `overflow-x-auto`, sans hauteur ni `overflow-y`, dans un cadre `overflow-hidden`.
  # Borner la hauteur de la ligne clipperait donc les affaires suivantes. Le nombre de
  # lignes étant ce qui fait la hauteur, la répartir en trois la divise par trois —
  # sans en retirer une seule, ce qui était la contrainte.
  #
  # NTILE(3) plutôt qu'un découpage à rang fixe : le nombre d'affaires change avec le
  # filtre de période (105 sur tout l'historique, 55 par défaut), et un seuil en dur
  # laisserait une colonne vide dès que le total baisse.
  #
  # La lecture va de gauche à droite : la colonne 1 porte les plus fortes espérances
  # de gain, d'où le rang affiché — sans lui, trois listes triées côte à côte ne
  # diraient pas laquelle vient en premier.
  - widgets:
__CHAUDES_COLONNES__

  # === Santé du portefeuille — affaires perdues exclues ===
  - widgets:
"""

ligne3 = "\n\n".join([
    kpi("Budget actif (DT)", 3, actif("SUM(budget)"), ",.0f",
        "Budget annoncé par le client, hors affaires perdues."),
    kpi("Offre financière (DT)", 3, actif("SUM(financial_offer)"), ",.0f",
        "Montant proposé par DevoTeam, sur le même périmètre."),
    kpi("Écart offre / budget", 3,
        actif("(SUM(financial_offer) - SUM(budget)) / NULLIF(SUM(budget), 0)"), "+.1%",
        "Négatif = nous chiffrons sous le budget du client."),
    kpi("Montant pondéré (DT)", 3, actif("SUM(weighted_amount)"), ",.0f",
        "Offre × probabilité, sur les seules lignes où la probabilité est renseignée."),
])

FOOTER = """

  # === Pipeline : où en sont les affaires encore ouvertes ===
  - widgets:
      - name: Entonnoir de vente
        type: chart
        chart: funnel
        col: 6
        description: Opportunités ayant atteint au moins chaque étape.
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
        description: Part qui franchit l'étape suivante.
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
      - name: Budget actif par pays (DT)
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
        y: { field: budget, type: number, title: Budget (DT), format: ",.0f" }
        color: { field: country }

  # === Ce qu'il faut traiter maintenant ===
  - widgets:
      - name: Opportunités urgentes (échéance ≤ 7 jours)
        type: table
        col: 12
        # Seul widget tourné vers l'avenir : la borne « à date » des offres remises ne
        # s'y applique pas, sinon il serait toujours vide.
        # Volontairement HORS des deux dates : sa fenêtre est « les 7 prochains
        # jours », elle se définit toute seule. Une date de fin posée à aujourd'hui le
        # viderait entièrement, ce qui est exactement le contraire de son propos.
        # Le filtre de practice, lui, s'applique normalement.
        description: Affaires encore ouvertes dont l'échéance tombe dans les 7 jours.
        sql: |
          SELECT buyer, country, practice, status, deadline, days_remaining, budget
          FROM opportunities
          WHERE days_remaining BETWEEN 0 AND 7
            AND status NOT IN (
              'Offre gagnée', 'Offre perdue', 'Offre signée', 'Infructueux',
              'NO GO', 'Hors scope', 'Non shortlisté'
            )
__PRACTICE_SEULE__
          ORDER BY days_remaining ASC
        columns:
          - { name: buyer, label: Client }
          - { name: country, label: Pays }
          - { name: practice, label: Practice }
          - { name: status, label: Statut }
          - { name: deadline, label: Échéance }
          - { name: days_remaining, label: Jours restants, number: number }
          - { name: budget, label: Budget (DT), number: number }
"""

NOUVELLE_LIGNE = """

  - widgets:
"""

# Chaque valeur est suivie de SA PART du portefeuille. Un nombre seul ne dit pas
# s'il est gros : « 105 affaires chaudes » prend un tout autre sens selon qu'il
# représente 5 % ou 46 % de ce qui est en jeu.
#
# Le dénominateur est le portefeuille ACTIF, affaires perdues exclues — le même que
# celui des KPI de santé plus bas. Le rapporter au portefeuille entier gonflerait le
# dénominateur avec des affaires mortes et écraserait la part sans raison.
def part_chaudes(nom, col, expression, desc):
    corps = ("          SELECT (SELECT %s FROM opportunities\n"
             "                  WHERE %s\n%s)\n"
             "                 / NULLIF((SELECT %s FROM opportunities\n"
             "                           WHERE status NOT IN (%s)\n%s), 0) AS value"
             % (expression, hot_deal_sql(), FILTRES, expression, PERDUS, FILTRES))
    return kpi(nom, col, corps, ".1%", desc)


chaudes_kpi = "\n\n".join([
    kpi_chaudes("Affaires chaudes", 3, "COUNT(*)", ",.0f",
                "Probablement gagnées, pas encore gagnées : remises, ou de 80 à 99 % de probabilité."),
    part_chaudes("Part des opportunités", 3, "COUNT(*) * 1.0",
                 "Ce que les affaires chaudes pèsent dans le portefeuille actif, en nombre."),
    kpi_chaudes("Budget à forte confiance (DT)", 3, "SUM(budget)", ",.0f",
                "Budget cumulé des affaires chaudes."),
    part_chaudes("Part du budget", 3, "SUM(budget)",
                 "La même chose en montant : la part du budget actif qui est chaude."),
]) + _RUPTURE_DE_LIGNE + "\n\n".join([
    kpi_chaudes("Montant pondéré associé (DT)", 6, "SUM(weighted_amount)", ",.0f",
                "Offre financière × probabilité, sur ce même périmètre."),
    # Sur quelle part du portefeuille ce bloc peut-il se prononcer ? Près d'une ligne
    # sur deux n'a pas de probabilité renseignée : elle ne peut alors être ni retenue
    # ni écartée comme affaire chaude. Sans ce chiffre, les trois KPI ci-dessus se
    # lisent comme portant sur l'ensemble du portefeuille, ce qui est faux — et rien
    # dans l'interface ne le disait.
    # « WHERE 1 = 1 » parce que les filtres de tête sont écrits en « AND … » : ils
    # se greffent sur une clause existante et ne peuvent pas en ouvrir une.
    kpi("Probabilité renseignée", 6,
        "          SELECT COUNT(win_probability) * 1.0 / NULLIF(COUNT(*), 0) AS value\n"
        "          FROM opportunities\n          WHERE 1 = 1\n" + FILTRES,
        ".0%",
        # Sous les 100 caractères que s'impose le tableau de bord : une description
        # se lit d'un coup d'œil sous son titre, le raisonnement vit ici.
        "Sur cette part seulement, une affaire peut être dite chaude ou non."),
])

doc = HEADER + ligne1 + NOUVELLE_LIGNE + ligne2 + BODY + ligne3 + FOOTER
chaudes_colonnes = table_chaudes()

doc = (doc.replace("__CHAUDES_COLONNES__", chaudes_colonnes)
          .replace("__CHAUDES_KPI__", chaudes_kpi)
          .replace("__CHAUDES__", CHAUDES_CTE)
          .replace("__REMISES__", REMISES_CTE)
          .replace("__ISSUES__", ISSUES)
          .replace("__ETAPES__", etapes_cte())
          .replace("__PERDUS__", PERDUS)
          .replace("__PRACTICE_SEULE__", PRACTICE)
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
    "Taux de réussite", "Budget remis (DT)", "Budget gagné (DT)",
    "Issue des offres remises", "Offres remises par practice",
    "Issue par practice", "Offres remises par mois",
    "Affaires chaudes", "Budget à forte confiance (DT)", "Montant pondéré associé (DT)",
    "Part des opportunités", "Part du budget", "Probabilité renseignée",
    "Affaires chaudes par practice", "Poids de chaque practice",
    "Détail des affaires chaudes",
    "Budget actif (DT)", "Offre financière (DT)", "Écart offre / budget", "Montant pondéré (DT)",
    "Entonnoir de vente", "Taux de passage entre étapes", "Budget actif par pays (DT)",
    "Opportunités urgentes (échéance ≤ 7 jours)",
]
manquants = [n for n in attendus if n not in noms]
assert not manquants, "widgets manquants : %s" % manquants
print("grille 12 colonnes respectée, %d widgets attendus tous présents" % len(attendus))
