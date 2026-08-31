"""Post-process and rule-based pre-parse to improve intent accuracy."""

import logging
import re
import unicodedata
from datetime import date
from typing import Optional

from .business_rules import (
    HOT_DEAL_MIN_PROBABILITY, SUBMITTED_STATUSES, choose_chart_type,
)
from .schema_and_whitelist import VALID_METRICS, VALID_DIMENSIONS, KNOWN_VALUES
from .alerts import ALERT_WINDOW_DAYS, EXCLUDED_STATUSES

logger = logging.getLogger("devoteam.intent")


def _norm(text: str) -> str:
    """Minuscules, sans accents, et TOUTE suite d'espacement ramenée à une espace.

    Les tables de phrases contiennent des espaces littéraux (« par pays »). Une
    tabulation ou un retour chariot entre les deux mots suffisait donc à les rendre
    invisibles : « budget<TAB>par<CR>pays » ne reconnaissait plus l'axe et renvoyait
    le total du portefeuille. Un copier-coller depuis un tableur produit exactement
    ce genre de texte.

    Les caractères de contrôle non imprimables sont retirés plutôt que remplacés :
    ils ne séparent pas des mots, ils les polluent.
    """
    text = unicodedata.normalize("NFD", text.lower())
    sans_accents = "".join(c for c in text if unicodedata.category(c) != "Mn")
    sans_controle = "".join(
        c for c in sans_accents
        if c.isspace() or unicodedata.category(c) not in ("Cc", "Cf", "Co", "Cs")
    )
    return re.sub(r"\s+", " ", sans_controle)


# "offre(s)"/"opportunité(s)" doit précéder "pondéré..." de près (0-2 mots entre les
# deux) — exclut "montant pondéré", qui n'a ni "offre" ni "opportunité" à proximité.
_WEIGHTED_OFFER_PATTERN = re.compile(r"\b(?:offres?|opportunit\w*)\s+(?:\w+\s+){0,2}ponder")

# « affaire chaude » est l'autre nom de la même chose : une offre déjà remise, très
# probable, dont la décision n'est pas tombée. Deux termes pour un seul concept —
# ils doivent donc résoudre vers la MÊME définition, sinon la même question donnerait
# deux chiffres selon le mot employé.
_HOT_DEAL_PATTERN = re.compile(r"\b(?:affaires?|deals?|opportunit\w*)\s+(?:[\w'-]+\s+){0,2}chaud")

# « ajoute le budget par pays » : compléter le tableau de bord affiché, pas le
# remplacer. Le verbe ne change RIEN à l'analyse demandée — même métrique, même axe,
# mêmes filtres — seulement la façon dont le résultat rejoint l'écran. D'où un
# simple drapeau porté par l'intention, plutôt qu'un chemin de composition distinct.
_APPEND_PATTERN = re.compile(r"\b(?:ajoute\w*|rajoute\w*|joins?|complete\w*)\b")

# « offres remises » est un terme MÉTIER, pas le statut du même nom. Le statut décrit
# l'état courant : une offre partie chez le client et gagnée depuis n'y figure plus.
# Sans cette règle, la question « combien d'offres a-t-on remises ? » répondait 4 —
# le nombre d'offres encore en attente de décision — quand la vue d'ensemble en
# affiche 57. Deux chiffres différents pour la même question, selon qu'on la pose au
# chat ou qu'on la lise sur le dashboard : c'est précisément ce que ce projet évite.
#
# Le pluriel n'est pas exigé (« combien d'offre remise ») mais « offre remise »
# employé au singulier avec un déterminant défini (« le statut offre remise ») reste
# rare, et la levée d'ambiguïté par le nombre serait fragile.
# Jusqu'à trois mots peuvent s'intercaler : « combien d'offres A-T-ON remises ». La
# classe intermédiaire inclut l'apostrophe et le trait d'union, sans quoi « a-t-on »
# ne compterait pas pour un mot et la tournure la plus naturelle de la question
# passerait à côté de la règle.
_SUBMITTED_OFFER_PATTERN = re.compile(
    r"\b(?:offres?|opportunit\w*|dossiers?)\s+(?:[\w'-]+\s+){0,3}(?:remis\w*|depose\w*|soumis\w*)"
)


PRACTICE_MAP = {
    "data management": "Data Management",
    "data": "Data Management",
    "risk advisory": "Risk Advisory",
    "risk": "Risk Advisory",
    "digital transformation": "Digital Transformation",
    "digital": "Digital Transformation",
}

STATUS_MAP = {
    "offre gagnee": "Offre gagnée",
    "offres gagnees": "Offre gagnée",
    "gagnee": "Offre gagnée",
    "gagnees": "Offre gagnée",
    "gagne": "Offre gagnée",
    "remportee": "Offre gagnée",
    "offre perdue": "Offre perdue",
    "offres perdues": "Offre perdue",
    "perdue": "Offre perdue",
    "perdues": "Offre perdue",
    "perdu": "Offre perdue",
    "offre signee": "Offre signée",
    "signee": "Offre signée",
    "offre remise": "Offre remise",
    "en cours": "En cours de préparation",
    "lead": "Lead",
    "no go": "NO GO",
}


def _detect_practice(q: str) -> str | None:
    for key, val in PRACTICE_MAP.items():
        if key in q:
            return val
    return None


# Mots qui RETOURNENT le sens du statut qui les suit : « offres non gagnées » ne
# demande pas les offres gagnées. C'est pourtant ce qui était renvoyé — le budget
# des offres gagnées (30 080 000 DT) présenté comme celui des non-gagnées. Une
# réponse fausse ET inversée, la pire des deux.
_NEGATIONS = ("non", "pas", "hors", "sauf", "excepte", "exceptees", "autres que",
              "sans", "different de", "differentes de")

# Fenêtre de recherche de la négation devant le statut. Trois mots suffisent à couvrir
# « offres autres que gagnées » sans aller happer une négation d'une autre proposition.
_PORTEE_NEGATION = 3


def _est_nie(q: str, position: int) -> bool:
    """Le statut trouvé à `position` est-il précédé d'une négation proche ?"""
    avant = q[:position].split()[-_PORTEE_NEGATION:]
    fenetre = " ".join(avant)
    return any(re.search(r"\b%s\b" % re.escape(n), fenetre) for n in _NEGATIONS)


def _filtres_nies(q: str, filters: dict) -> dict:
    """Les filtres dont la VALEUR est précédée d'une négation dans la question.

    La négation n'était traitée que pour le statut. « budget par pays hors Tunisie »
    posait donc `country = Tunisie` et répondait 34 530 000 DT — le budget DE la
    Tunisie — quand la question en demande le complément (69 370 001). Idem pour
    « tout sauf Risk Advisory ». Le mot de négation était lu, puis jeté.

    Renvoie ce qu'il faut RETIRER de `filters` et poser en exclusion ; l'appelant
    fait le déplacement, pour que la décision et son effet restent au même endroit.
    """
    nies: dict = {}
    for colonne, valeur in (filters or {}).items():
        if colonne == "status":
            continue  # traité par `_statuts_de_la_question`, plus fin sur les accords
        valeurs = valeur if isinstance(valeur, (list, tuple)) else [valeur]
        rejetees = []
        for v in valeurs:
            trouve = re.search(r"\b%s\b" % re.escape(_norm(str(v))), q)
            if trouve and _est_nie(q, trouve.start()):
                rejetees.append(v)
        if rejetees:
            nies[colonne] = rejetees
    return nies


def _statuts_de_la_question(q: str) -> tuple[list, list]:
    """(statuts demandés, statuts exclus) — tous ceux que la question nomme.

    Deux corrections en une. D'abord la négation, décrite ci-dessus. Ensuite la
    CONJONCTION : « offres gagnées et perdues par pays » ne retenait que le premier
    statut rencontré, et répondait donc à la moitié de la question sans le dire.
    """
    retenus, exclus = [], []
    for cle, valeur in STATUS_MAP.items():
        # Même tolérance d'accord que pour les métriques (`_ACCORDS`). Sans elle, la
        # table devait énumérer chaque forme à la main — et « signée » y était au
        # singulier seulement : « budget des offres signées » ET « budget des offres
        # NON signées » renvoyaient tous deux 103 900 001 DT, le portefeuille entier,
        # là où les vraies valeurs sont 13 080 000 et 90 820 001. Deux réponses
        # fausses, identiques, à deux questions opposées.
        trouve = re.search(r"\b%s%s\b" % (re.escape(cle), _ACCORDS), q)
        if not trouve:
            continue
        cible = exclus if _est_nie(q, trouve.start()) else retenus
        if valeur not in cible:
            cible.append(valeur)
    # Un statut à la fois nié et demandé (« les gagnées, pas les non gagnées ») est
    # trop ambigu pour être tranché ici : l'exclusion l'emporte, elle est la plus
    # restrictive et donc la moins susceptible d'affirmer quelque chose de faux.
    retenus = [s for s in retenus if s not in exclus]
    return retenus, exclus


def _detect_status(q: str) -> str | None:
    """Le statut demandé, au singulier — pour les appelants qui n'en attendent qu'un."""
    retenus, _ = _statuts_de_la_question(q)
    return retenus[0] if retenus else None


# Tables plutôt que cascades de `if` : les mêmes formulations servent à détecter la
# métrique ET à savoir quels mots de la demande ont été compris (voir
# try_followup_parse). Deux listes séparées auraient fini par diverger.
_METRIC_PHRASES = [
    (("combien", "nombre", "volume", "nb", "count"), "nb_opportunities"),
    (("proba", "probabilite", "chance"), "win_probability"),
    (("offre financiere", "financial offer"), "financial_offer"),
    (("pondere", "weighted"), "weighted_amount"),
    (("budget", "ca", "chiffre", "montant"), "budget"),
]

# « by X » autant que « par X » : l'application est francophone, mais une question
# posée en anglais recevait le total du portefeuille au lieu de la répartition
# demandée — « budget by country » répondait 103 900 001 DT sans le moindre axe.
# Reconnaître la tournure coûte une ligne ; l'ignorer coûtait une réponse fausse.
_DIMENSION_PHRASES = [
    (("par pays", "par country", "by country"), "country"),
    (("par practice", "par metier", "by practice"), "practice"),
    (("par statut", "par status", "by status"), "status"),
    (("par mois", "evolution", "mensuel", "by month"), "deadline_month"),
    (("par an", "par annee", "by year"), "deadline_year"),
    (("par type", "by type"), "opp_type"),
    (("par source", "financement", "by funding"), "funding_source"),
    # Les formes « des X » / « les X » viennent des classements : « top 5 des
    # clients par budget » désigne bien le client comme axe, et le budget comme
    # critère de tri. Sans elles, la question repartait sans dimension et le total
    # du portefeuille sortait en réponse.
    (("par client", "par acheteur", "par lead", "par compte",
      "des clients", "les clients", "des acheteurs", "by client", "by buyer"), "buyer"),
    (("par partenaire", "des partenaires", "les partenaires", "by partner"), "partner"),
    (("des pays", "les pays"), "country"),
    (("des practices", "les practices"), "practice"),
]

# Les mots par lesquels une question peut désigner un axe d'analyse. Sert au
# garde-fou de `_axe_incompris` : ce qui suit « par » sans figurer ici n'est pas
# une dimension oubliée dans la table ci-dessus, c'est un axe qui n'existe pas.
_MOTS_AXES_CONNUS = {
    "pays", "country", "practice", "practices", "metier", "metiers", "statut",
    "statuts", "status", "mois", "month", "an", "ans", "annee", "annees", "year",
    "type", "types", "source", "sources", "financement", "client", "clients",
    "acheteur", "acheteurs", "lead", "leads", "compte", "comptes", "partenaire",
    "partenaires", "buyer", "opportunite", "opportunites", "offre", "offres",
    "trimestre", "semestre",
}

# « par » n'introduit pas toujours un axe : « par exemple », « par rapport à »,
# « par contre » sont des locutions. Les exclure évite de refuser une question
# parfaitement claire.
_LOCUTIONS_PAR = {"exemple", "rapport", "contre", "ailleurs", "consequent", "defaut", "la", "ici"}

# Demande explicite d'une moyenne. « moyen »/« moyenne » attrapent aussi les accords
# (« budget moyen », « valeur moyenne ») ; « en moyenne » et « average » complètent.
# Le texte est déjà sans accent à ce stade (voir _norm).
_MOYENNE_PATTERN = re.compile(r"\b(?:moyen(?:ne)?s?|average|avg)\b")

# Une notion de TAUX que les données ne portent pas telle quelle. Le modèle la
# rabattait sur « nombre d'opportunités » : l'utilisateur demandait un pourcentage et
# recevait un comptage, sans que rien ne signale la substitution.
_TAUX_PATTERN = re.compile(
    r"\b(?:taux|pourcentage|%)\s+(?:de\s+|d')?(?:reussite|succes|conversion|transformation|gain|win)"
    r"|\bwin\s*rate\b"
)


# Terminaisons d'accord admises à la fin d'une phrase reconnue : « pondéré » doit
# attraper « pondérée » et « pondérées », sans pour autant se prolonger n'importe
# comment. C'est cette borne qui manquait.
_ACCORDS = r"(?:e|s|es|ee|ees)?"


def _phrase_pattern(phrase: str) -> str:
    """Motif ANCRÉ DES DEUX CÔTÉS, avec une tolérance d'accord à droite.

    Deux bugs de la même famille sont nés ici. « ca » (pour le chiffre d'affaires)
    se retrouvait dans « camembert » et « carte de chaleur » : demander un camembert
    basculait la métrique sur le budget. Puis « count » s'est retrouvé dans
    « country » : « budget par country » répondait un COMPTAGE — 229 — sous le
    libellé « Budget ».

    La borne de droite n'est donc pas optionnelle ; elle laisse seulement passer les
    accords français (`_ACCORDS`), qui ne peuvent pas transformer un mot en un autre.
    Les phrases très courtes n'y ont pas droit du tout : « ca » + « s » donnerait
    « cas », qui n'a aucun rapport.
    """
    escaped = re.escape(phrase.strip())
    if len(phrase.strip()) <= 3:
        return r"\b" + escaped + r"\b"
    return r"\b" + escaped + _ACCORDS + r"\b"


def _match_phrase(q: str, table: list) -> tuple[str | None, str]:
    """(valeur, texte trouvé dans la question) — le texte sert à vérifier ensuite
    que la demande a été comprise en entier."""
    for phrases, valeur in table:
        for phrase in phrases:
            found = re.search(_phrase_pattern(phrase), q)
            if found:
                return valeur, found.group(0)
    return None, ""


def _detect_metric(q: str) -> str | None:
    return _match_phrase(q, _METRIC_PHRASES)[0]


def _detect_dimension(q: str) -> str | None:
    return _match_phrase(q, _DIMENSION_PHRASES)[0]


_AXES_DISPONIBLES = ("pays, practice, statut, client, partenaire, mois, année, "
                     "source de financement, type d'opportunité")


def _axe_incompris(q: str, dimension: str) -> str | None:
    """Le mot qui suit « par » désigne-t-il un axe qui n'existe pas ?

    Ne se déclenche QUE si aucune dimension n'a été retenue : dès qu'une l'a été,
    la demande de répartition a été comprise et il n'y a rien à signaler. Sans ce
    garde-fou, « budget par client » (avant que `buyer` existe) et « budget par
    couleur de cheveux » renvoyaient tous deux le total du portefeuille — une
    réponse fausse ayant toutes les apparences d'une bonne.
    """
    if dimension:
        return None
    # Le jeton est capturé TEL QUEL, ponctuation comprise, puis nettoyé pour la
    # comparaison. Le motif ne retenait que des lettres : « budget par
    # ../../etc/passwd » ne présentait donc aucun jeton à examiner, et la question
    # repartait avec le total du portefeuille — exactement le silence qu'on traque.
    # « by » est reconnu comme « par » : une question posée en anglais mérite le même
    # garde-fou qu'une question posée en français.
    for brut in re.findall(r"\b(?:par|by)\s+(?:le |la |les |l'|the )?(\S{2,})", q):
        mot = re.sub(r"^[^\w]+|[^\w]+$", "", brut) or brut
        if mot in _LOCUTIONS_PAR or mot in _MOTS_AXES_CONNUS:
            continue
        # « par » introduit aussi un critère de TRI, pas seulement un axe : dans
        # « top 5 des clients par budget », c'est le budget qui classe et le client
        # qui répartit. Refuser ici rejetterait une question parfaitement claire.
        if _match_phrase(mot, _METRIC_PHRASES)[0]:
            continue
        return (f"Je ne sais pas répartir par « {mot} » — cet axe n'existe pas dans les "
                f"données. Axes disponibles : {_AXES_DISPONIBLES}.")
    return None


# « urgent » est un mot MÉTIER : il désigne la même fenêtre que les alertes email
# (alerts.ALERT_WINDOW_DAYS). Il n'était reconnu nulle part — « liste des
# opportunités urgentes » renvoyait les 229 opportunités actives, tout le
# portefeuille, au lieu des 6 qui tombent réellement dans la semaine.
_URGENCE_PATTERN = re.compile(r"\burgent\w*|\bpresse\w*|\bimminent\w*")

# Une année citée dans la question. Le garde-fou `_annee_hors_donnees` refusait déjà
# celles qui n'existent pas ; celles qui EXISTENT étaient tout aussi silencieusement
# ignorées — « budget par pays en 2026 » rendait les 103 900 001 DT de tous les
# exercices au lieu des 74 540 001 de 2026.
_ANNEE_PATTERN = re.compile(r"\b(?:en|pour|de|sur|annee|exercice)\s+((?:19|20|21)\d{2})\b")


# Comparaisons chiffrées. Seul « moins de N jours » était reconnu : « budget
# supérieur à 500000 », « plus de 2 millions », « entre 100000 et 500000 » et
# « probabilité supérieure à 50 % » repartaient tous avec le portefeuille entier
# (103 900 001 DT), la borne énoncée disparaissant en chemin.
_NOMBRE = r"(\d[\d\s.,]*)\s*(millions?|m|k|milliers?)?"
_PLUS_QUE = re.compile(r"\b(?:plus de|superieur\w*\s+a|au[- ]dessus de|depassant|>=?)\s*" + _NOMBRE)
_MOINS_QUE = re.compile(r"\b(?:moins de|inferieur\w*\s+a|en dessous de|<=?)\s*" + _NOMBRE)
_ENTRE = re.compile(r"\bentre\s+" + _NOMBRE + r"\s+et\s+" + _NOMBRE)

# Multiplicateurs des suffixes d'ordre de grandeur.
_ECHELLES = {"million": 1e6, "millions": 1e6, "m": 1e6, "k": 1e3,
             "millier": 1e3, "milliers": 1e3}

# Mots qui désignent la colonne bornée. Sans eux, tout serait rapporté au budget —
# « probabilité supérieure à 50 % » deviendrait un budget de 50.
_COLONNE_PROBABILITE = re.compile(r"\bproba\w*|\bchance\w*|%")
_COLONNE_JOURS = re.compile(r"\bjours?\b|\bsemaines?\b|\becheance\w*\b")


def _nombre(texte: str, echelle: str | None) -> float | None:
    """« 2 millions » -> 2000000.0. Les séparateurs de milliers sont retirés."""
    try:
        valeur = float(re.sub(r"[\s.,](?=\d{3}\b)", "", (texte or "").strip()).replace(",", "."))
    except ValueError:
        return None
    return valeur * _ECHELLES.get((echelle or "").strip().lower(), 1)


def _colonne_bornee(q: str, metric: str) -> str | None:
    """Sur quelle colonne porte une comparaison chiffrée trouvée dans la question."""
    if _COLONNE_JOURS.search(q):
        return None  # déjà couvert par la règle dédiée aux échéances
    if _COLONNE_PROBABILITE.search(q):
        return "win_probability"
    if metric in ("budget", "financial_offer", "weighted_amount"):
        return metric
    return "budget"


def _bornes_chiffrees(q: str, metric: str) -> dict:
    """Les bornes numériques énoncées par la question, prêtes pour `range_filters`."""
    colonne = _colonne_bornee(q, metric)
    if not colonne:
        return {}

    def cadre(valeur):
        # Un pourcentage s'exprime en fraction dans les données (0.8 = 80 %).
        return valeur / 100 if colonne == "win_probability" and valeur > 1 else valeur

    entre = _ENTRE.search(q)
    if entre:
        bas, haut = _nombre(entre.group(1), entre.group(2)), _nombre(entre.group(3), entre.group(4))
        if bas is not None and haut is not None:
            return {colonne: {"op": "between", "value": [cadre(min(bas, haut)), cadre(max(bas, haut))]}}

    plus = _PLUS_QUE.search(q)
    if plus:
        valeur = _nombre(plus.group(1), plus.group(2))
        if valeur is not None:
            return {colonne: {"op": ">=" if ">=" in plus.group(0) else ">", "value": cadre(valeur)}}

    moins = _MOINS_QUE.search(q)
    if moins:
        valeur = _nombre(moins.group(1), moins.group(2))
        if valeur is not None:
            return {colonne: {"op": "<=" if "<=" in moins.group(0) else "<", "value": cadre(valeur)}}

    return {}


# « combien de clients différents ? » demande une CARDINALITÉ, pas un volume. La
# question renvoyait 229 — le nombre d'opportunités — là où la réponse est 84. Le
# nom au pluriel suffit à désigner l'axe ; « différents » n'est qu'une insistance.
_NOMS_VERS_AXE = {
    "pays": "country", "clients": "buyer", "client": "buyer",
    "acheteurs": "buyer", "comptes": "buyer", "leads": "buyer",
    "practices": "practice", "practice": "practice", "metiers": "practice",
    "partenaires": "partner", "partenaire": "partner",
    "statuts": "status", "types": "opp_type",
    "sources": "funding_source", "sources de financement": "funding_source",
}
_COMPTAGE_DISTINCT = re.compile(
    r"\b(?:combien de|nombre de|nb de)\s+(?:differents?\s+)?([a-z][a-z ']{1,24}?)"
    r"(?:\s+(?:differents?|distincts?|uniques?))?\b"
)


def _axe_a_denombrer(q: str) -> str | None:
    """L'axe dont la question demande le nombre de valeurs distinctes, s'il y en a un."""
    for trouve in _COMPTAGE_DISTINCT.finditer(q):
        nom = trouve.group(1).strip()
        # Du plus long au plus court : « sources de financement » avant « sources ».
        for candidat in (nom, nom.rsplit(" ", 1)[0], nom.split(" ")[0]):
            if candidat in _NOMS_VERS_AXE:
                return _NOMS_VERS_AXE[candidat]
    return None


def _annee_demandee(q: str) -> str | None:
    """L'année sur laquelle la question porte, si elle en nomme une seule.

    Plusieurs années citées (« compare 2025 et 2026 ») relèvent d'une comparaison :
    c'est au modèle de poser la liste de valeurs, ce code-ci ne tranche pas.
    """
    trouvees = {m for m in _ANNEE_PATTERN.findall(q)}
    return trouvees.pop() if len(trouvees) == 1 else None


def _annee_hors_donnees(q: str) -> str | None:
    """Une année citée dans la question mais absente des données.

    Le contrôle porte sur le TEXTE et non sur les filtres : « budget par pays en
    2030 » ne produisait aucun filtre d'année du tout — la contrainte disparaissait
    avant d'arriver au moteur, et la réponse portait sur tous les exercices en ayant
    l'air de répondre à la question posée.
    """
    # Deux façons de reconnaître une année. La plage 1800-2199 attrape « en 2030 »
    # sans confondre avec un montant ; et un nombre à quatre chiffres ANNONCÉ comme
    # une année (« l'année 3000 », « exercice 3000 ») en est une quoi qu'il vaille —
    # sans quoi une année absurde passait entre les mailles et la question repartait
    # sur le portefeuille entier.
    citees = {int(a) for a in re.findall(r"\b(1[89]\d{2}|20\d{2}|21\d{2})\b", q)}
    citees |= {int(a) for a in re.findall(r"\b(?:annee|an|exercice)\s+(\d{4})\b", q)}
    if not citees:
        return None
    try:
        from .data_store import get_dataframe
        df = get_dataframe()
        if df is None or df.empty:
            return None
        connues = {int(a) for a in df["deadline_year"].dropna().unique().tolist()}
    except Exception:
        # Sans données de référence, ce garde-fou se tait plutôt que de refuser à tort.
        logger.warning("Années de référence indisponibles.", exc_info=True)
        return None
    if not connues:
        return None

    hors = sorted(citees - connues)
    # Une seule des années citées suffit à rendre la question traitable : « compare
    # 2025 et 2030 » garde son sens sur 2025, on ne bloque donc que si AUCUNE ne
    # tombe dans les données.
    if not hors or citees & connues:
        return None
    couverture = ("%d" % min(connues) if len(connues) == 1
                  else "%d à %d" % (min(connues), max(connues)))
    return ("Aucune donnée pour %s. Les échéances connues vont de %s."
            % (", ".join(str(a) for a in hors), couverture))


def _mesure_indisponible(q: str) -> str | None:
    """Une mesure que les données ne portent pas, nommée explicitement.

    Le taux de réussite se rabattait en silence sur un simple comptage. Plutôt que
    de répondre à côté, on le dit et on propose ce qui s'en approche le plus.
    """
    if _TAUX_PATTERN.search(q):
        return ("Le taux de réussite n'est pas une mesure que je peux croiser librement — "
                "il est affiché en KPI sur la vue d'ensemble. Je peux en revanche vous "
                "montrer la probabilité de gain moyenne par practice, ou la répartition "
                "des offres remises entre gagnées, perdues et en attente.")
    return None


def _clarification(message: str) -> dict:
    """Intention « je n'ai pas compris » — même forme que llm._unclear_intent, pour
    que `main.py` la présente exactement de la même façon."""
    return {
        "goal": "", "metric": "", "dimension": "", "filters": {}, "range_filters": {},
        "chart_type": "bar", "aggregation": "sum", "use_raw_table": False,
        "is_conversation": True, "limit": 0, "clarification": message,
    }


def _detect_chart_type(q: str, dimension: str) -> str | None:
    if any(w in q for w in ("liste", "lister", "detail", "tableau")):
        return "table"
    if any(w in q for w in ("entonnoir", "funnel", "pipeline de vente", "pipeline commercial")):
        return "funnel"
    if any(w in q for w in ("nuage de points", "scatter", "bulles", "correlation", "correle",
                             "lien entre", "rapport entre", "en fonction de")):
        return "scatter"
    if any(w in q for w in ("carte de chaleur", "heatmap", "heat map")):
        return "heatmap"
    # \b requis : "aire" en simple sous-chaîne matcherait "faire"/"affaire"/"nécessaire".
    if re.search(r"\baire\b", q) or "area chart" in q:
        return "area"
    if any(w in q for w in ("camembert", "repartition", "part de", "pourcentage", "proportion")):
        return "pie"
    if any(w in q for w in ("evolution", "tendance", "courbe")):
        # "évolution"/"tendance" n'implique une courbe que sur un axe temporel — sur une
        # dimension non temporelle (ex: "évolution par pays", très inhabituel), une courbe
        # n'a pas de sens (rien à ordonner sur l'axe X) ; on laisse retomber sur "bar".
        if not dimension or dimension in ("deadline_month", "deadline_year"):
            return "line"
    if any(w in q for w in ("kpi", "combien", "total", "quel est")) and not dimension:
        return "kpi_card"
    if dimension == "deadline_month":
        return "line"
    if dimension:
        return "bar"
    return None


def try_rule_based_parse(query: str) -> dict | None:
    """High-confidence parse without LLM for common French patterns."""
    q = _norm(query)
    if not q.strip():
        return None

    if q.strip() in ("bonjour", "salut", "hello", "coucou", "aide", "help"):
        return {"goal": "", "metric": "", "dimension": "", "filters": {}, "range_filters": {},
                "chart_type": "bar", "aggregation": "sum", "use_raw_table": False,
                "is_conversation": True, "limit": 0}

    metric = _detect_metric(q)
    dimension = _detect_dimension(q)
    practice = _detect_practice(q)
    statuts, statuts_exclus = _statuts_de_la_question(q)
    status = statuts[0] if statuts else None
    chart_type = _detect_chart_type(q, dimension or "")

    use_raw = chart_type == "table" or "liste" in q
    is_data_query = bool(metric or dimension or practice or status or statuts_exclus
                         or use_raw or "top" in q)

    if not is_data_query:
        return None

    filters = {}
    if practice:
        filters["practice"] = practice
    # Une LISTE dès que la question en nomme plusieurs : « offres gagnées et perdues »
    # portait auparavant sur les seules gagnées, en silence.
    if statuts:
        filters["status"] = statuts[0] if len(statuts) == 1 else statuts

    range_filters = {}
    m_days = re.search(r"(?:moins de|<=|<|inferieur(?:e)? a)\s*(\d+)\s*jours?", q)
    if m_days:
        # "moins de N jours" signifie une échéance encore À VENIR (urgente), jamais déjà
        # passée — days_remaining < N inclurait aussi les valeurs négatives (deadlines
        # dépassées depuis longtemps), donc bornée explicitement à [0, N].
        range_filters["days_remaining"] = {"op": "between", "value": [0, int(m_days.group(1))]}
        use_raw = True
        chart_type = "table"

    limit = 0
    m_top = re.search(r"top\s*(\d+)|(\d+)\s*premier", q)
    if m_top:
        limit = int(m_top.group(1) or m_top.group(2))

    if not metric:
        metric = "nb_opportunities" if dimension else "budget"
    if not chart_type:
        chart_type = "kpi_card" if not dimension else "bar"

    goal = query.strip().capitalize()
    if goal and not goal[0].isupper():
        goal = goal[0].upper() + goal[1:]

    resultat = {
        "goal": goal,
        "metric": metric,
        "dimension": dimension or "",
        "filters": filters,
        "range_filters": range_filters,
        "chart_type": chart_type,
        "aggregation": "count" if metric == "nb_opportunities" else "sum",
        "use_raw_table": use_raw,
        "is_conversation": False,
        "limit": limit,
    }
    # « offres NON gagnées » s'exprime par une EXCLUSION, jamais par un filtre sur le
    # statut nié — c'est exactement l'inverse de la question.
    if statuts_exclus:
        resultat["exclude_statuses"] = statuts_exclus
    return resultat


# ---------------------------------------------------------------------------
# Ajustements sur le dashboard courant
#
# « en camembert », « top 5 », « enlève le filtre » ne sont pas des questions :
# ce sont des retouches de la question précédente. Les traiter comme des questions
# neuves faisait perdre le contexte — « par pays » repartait sur le nombre
# d'opportunités alors que la question d'avant portait sur le budget — et
# consommait un appel au modèle (quota gratuit ~16 requêtes/minute) pour un
# changement que le code sait appliquer seul, instantanément.
#
# GARDE-FOU CENTRAL : une retouche hérite en silence de tout le contexte précédent.
# Si un seul mot de la demande n'a pas été compris ici, l'hériter reviendrait à
# répondre à une autre question que celle posée — « budget par pays au Maroc pour
# Data Management » serait servie avec le filtre « Risk Advisory » de la question
# d'avant. On exige donc que CHAQUE mot porteur de sens ait été consommé par une
# règle ; au moindre reliquat, on rend la main au chemin normal (LLM + validation).
# ---------------------------------------------------------------------------

# Formes nommées explicitement par l'utilisateur. La forme demandée reste ensuite
# soumise à choose_chart_type : demander un camembert sur 19 pays donne des barres,
# avec l'explication affichée sous le graphique.
# Passer d'un total à une moyenne et retour est une RETOUCHE, pas une nouvelle
# question. « en somme » après « budget moyen par pays » n'était pas reconnu : la
# demande repartait vers le modèle, qui la lisait comme une question autonome et
# rendait un chiffre unique — l'axe « pays » disparaissait au passage.
_FOLLOWUP_AGREGATIONS = [
    (("en moyenne", "moyenne", "moyen"), "avg"),
    (("en somme", "en total", "au total", "somme", "cumule"), "sum"),
]

_FOLLOWUP_CHARTS = [
    (("camembert", "secteurs"), "pie"),
    (("histogramme", "barres", "barre"), "bar"),
    (("courbe", "lignes"), "line"),
    (("aire",), "area"),
    (("tableau", "liste"), "table"),
    (("nuage de points", "nuage"), "scatter"),
    (("entonnoir",), "funnel"),
    (("carte de chaleur", "heatmap"), "heatmap"),
]

# Retire TOUS les filtres : « remets tout », « sur l'ensemble du portefeuille ».
_RESET_FILTERS = (
    "sans filtre", "sans les filtres", "sans aucun filtre",
    "enleve les filtres", "enleve le filtre", "enleve tous les filtres",
    "retire les filtres", "retire le filtre", "annule les filtres",
    "tout le portefeuille", "ensemble du portefeuille",
    "remets tout", "sans restriction",
)

# Mots sans effet sur le sens d'une retouche : leur présence dans le reliquat ne
# doit pas faire échouer la vérification de couverture.
_FOLLOWUP_STOPWORDS = {
    "le", "la", "les", "l", "de", "du", "des", "un", "une", "d", "et", "ou",
    "en", "au", "aux", "a", "sur", "pour", "par", "avec", "dans", "ce", "cet",
    "cette", "ca", "c", "est", "moi", "me", "nous", "y", "s", "n", "je", "tu",
    "montre", "montres", "affiche", "affiches", "donne", "donnes", "mets", "met",
    "passe", "change", "changer", "fais", "fait", "refais", "plutot", "maintenant",
    "juste", "seulement", "uniquement", "aussi", "encore", "toujours", "alors",
    # Verbes d'ajout : ils pilotent la façon d'appliquer le résultat, pas son
    # contenu, et ne doivent donc pas faire échouer la vérification de couverture.
    "ajoute", "ajoutes", "ajouter", "rajoute", "rajouter", "complete", "completer",
    "puis", "ensuite", "svp", "stp", "merci", "voir", "graphique", "graphe",
    "dashboard", "tableau de bord", "practice", "plait", "il", "sous", "forme",
}

# Seconde barrière, moins fine que la couverture mot à mot mais immédiate : une
# retouche est courte par nature.
_MAX_FOLLOWUP_LENGTH = 60

_FOLLOWUP_KEYS = ("metric", "dimension", "filters", "range_filters", "chart_type",
                  "aggregation", "use_raw_table", "limit", "exclude_statuses",
                  # Sans ces deux-là, une retouche perdait le périmètre : « hors
                  # Tunisie » puis « en camembert » réaffichait la Tunisie, et
                  # « combien de clients » puis « par practice » repassait à un
                  # comptage de lignes.
                  "exclude_filters", "count_distinct", "hot_deals")


def _compose_goal(intent: dict) -> str:
    """Titre reconstruit à partir de l'intention retouchée. Reprendre la phrase de
    l'utilisateur donnerait « En camembert » comme titre de dashboard ; garder
    l'ancien titre laisserait croire que la retouche n'a pas été prise en compte."""
    from .labels import DIMENSION_LABELS, FILTER_LABELS, METRIC_LABELS, distinct_label

    # Un comptage distinct porte sur une AUTRE colonne que l'axe : le titre doit dire
    # laquelle, sinon « combien de clients par practice » s'intitulait « Nombre
    # d'opportunités par practice » — faux sur ce qui est compté.
    compte = intent.get("count_distinct")
    if compte:
        titre = distinct_label(compte).capitalize()
    else:
        titre = METRIC_LABELS.get(intent.get("metric", ""), intent.get("metric", "")).capitalize()
    dimension = intent.get("dimension")
    if dimension:
        titre += " par " + DIMENSION_LABELS.get(dimension, dimension).lower()

    valeurs = []
    for colonne, valeur in (intent.get("filters") or {}).items():
        if isinstance(valeur, (list, tuple)):
            valeurs.append(" vs ".join(str(v) for v in valeur))
        else:
            valeurs.append(str(valeur))
        FILTER_LABELS.get(colonne, colonne)  # libellés disponibles si besoin d'enrichir
    if valeurs:
        titre += " — " + ", ".join(valeurs)
    return titre or "Analyse"


def try_followup_parse(query: str, previous_intent: dict | None) -> dict | None:
    """Applique une retouche courte à l'intention précédente. Renvoie None dès que la
    demande n'est pas intégralement reconnue comme une retouche — l'appelant passe
    alors par le chemin normal (LLM + validation stricte), jamais par une supposition.
    """
    if not previous_intent or not previous_intent.get("metric"):
        return None
    if previous_intent.get("is_conversation"):
        return None

    q = _norm(query).strip()
    if not q or len(q) > _MAX_FOLLOWUP_LENGTH:
        return None

    intent = {k: previous_intent[k] for k in _FOLLOWUP_KEYS if k in previous_intent}
    intent["filters"] = dict(intent.get("filters") or {})
    intent["range_filters"] = dict(intent.get("range_filters") or {})
    intent["is_conversation"] = False

    reste = " " + q + " "
    touche = False

    def consomme(texte: str) -> None:
        nonlocal reste
        if texte:
            reste = reste.replace(texte, " ")

    for mot in _RESET_FILTERS:
        if mot in reste:
            intent["filters"] = {}
            intent["range_filters"] = {}
            consomme(mot)
            touche = True

    chart, texte = _match_phrase(reste, _FOLLOWUP_CHARTS)
    if chart:
        intent["chart_type"] = chart
        intent["use_raw_table"] = chart == "table"
        consomme(texte)
        touche = True

    # Filtres nommés : practice et statut ont des valeurs canoniques connues, donc
    # résolubles ici sans risque. Un pays ne l'est pas (liste dynamique, hors de
    # portée de ce module) — une demande qui en nomme un échouera à la vérification
    # de couverture et repartira vers le LLM, qui sait la résoudre.
    poses_ici = set()
    practice = _detect_practice(reste)
    if practice:
        intent["filters"]["practice"] = practice
        poses_ici.add("practice")
        for cle in PRACTICE_MAP:
            if cle in reste:
                consomme(cle)
                break
        touche = True

    statut = _detect_status(reste)
    if statut:
        intent["filters"]["status"] = statut
        poses_ici.add("status")
        for cle in STATUS_MAP:
            if cle in reste:
                consomme(cle)
                break
        touche = True

    dimension, texte = _match_phrase(reste, _DIMENSION_PHRASES)
    if dimension:
        intent["dimension"] = dimension
        consomme(texte)
        # Grouper PAR une colonne sur laquelle on filtre déjà ne produirait qu'une
        # seule barre : le filtre devient redondant avec l'axe et doit sauter. On
        # épargne les filtres à plusieurs valeurs — « compare France et Maroc » veut
        # précisément cet axe ET cette restriction — et ceux que la demande vient de
        # poser elle-même, qui sont voulus.
        valeur = intent["filters"].get(dimension)
        if (dimension not in poses_ici and valeur is not None
                and not isinstance(valeur, (list, tuple))):
            del intent["filters"][dimension]
        # Demander un AXE, c'est demander un regroupement. Tant que la liste brute
        # héritée du tour précédent restait active, elle court-circuitait le groupement
        # dans les deux moteurs : « affaires chaudes » puis « par practice » annonçait
        # « axe : aucun → practice » et réaffichait exactement la même liste plate.
        # Le message promettait un changement qui n'avait pas lieu.
        #
        # Sauf si la retouche demande elle-même un tableau (« par practice en
        # tableau ») — la branche des formes, plus haut, l'a alors déjà posé.
        if intent.get("use_raw_table") and chart != "table":
            intent["use_raw_table"] = False
            if intent.get("chart_type") == "table":
                intent["chart_type"] = "bar"
        touche = True

    agregation, texte = _match_phrase(reste, _FOLLOWUP_AGREGATIONS)
    if agregation:
        intent["aggregation"] = agregation
        consomme(texte)
        touche = True

    metric, texte = _match_phrase(reste, _METRIC_PHRASES)
    if metric:
        intent["metric"] = metric
        consomme(texte)
        touche = True

    m_top = re.search(r"top\s*(\d+)|(\d+)\s*premiers?", reste)
    if m_top:
        intent["limit"] = int(m_top.group(1) or m_top.group(2))
        consomme(m_top.group(0))
        touche = True

    if not touche:
        return None

    # Vérification de couverture : tout mot restant est un mot qu'on n'a PAS compris.
    for mot in re.findall(r"[a-z0-9]+", reste):
        if mot not in _FOLLOWUP_STOPWORDS:
            return None

    intent["goal"] = _compose_goal(intent)
    return intent


# ---------------------------------------------------------------------------
# Dates et périodes relatives : résolues en Python déterministe, jamais confiées
# au calcul mental du LLM (risque de dates "plausibles mais fausses").
# ---------------------------------------------------------------------------

_MONTHS_AGO_PATTERN = re.compile(r"(\d+)\s+derniers?\s+mois")


def _month_index(year: int, month: int) -> int:
    return year * 12 + (month - 1)


def _month_from_index(idx: int) -> tuple[int, int]:
    return idx // 12, idx % 12 + 1


def _format_month(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _quarter_month_range(year: int, month: int) -> tuple[int, int]:
    """Index (premier mois, dernier mois) du trimestre contenant (year, month)."""
    start_month = ((month - 1) // 3) * 3 + 1
    start_idx = _month_index(year, start_month)
    return start_idx, start_idx + 2


def _apply_relative_period(q: str, intent: dict, today: date) -> None:
    """Détecte les tournures FR de date/période relative et remplit filters/
    range_filters sur deadline_month/deadline_year. Ne fait rien si l'intention a
    déjà une valeur sur l'une de ces deux colonnes (ne jamais écraser un filtre
    explicite déjà posé, que ce soit par l'utilisateur ou par le LLM).
    """
    filters = intent.setdefault("filters", {})
    range_filters = intent.setdefault("range_filters", {})
    if "deadline_month" in filters or "deadline_year" in filters or "deadline_month" in range_filters:
        return

    today_idx = _month_index(today.year, today.month)

    m_n_months = _MONTHS_AGO_PATTERN.search(q)
    if m_n_months:
        n = int(m_n_months.group(1))
        sy, sm = _month_from_index(today_idx - n)
        range_filters["deadline_month"] = {
            "op": "between",
            "value": [_format_month(sy, sm), _format_month(today.year, today.month)],
        }
        return

    if "trimestre dernier" in q or "trimestre precedent" in q:
        cur_start_idx, _ = _quarter_month_range(today.year, today.month)
        prev_y, prev_m = _month_from_index(cur_start_idx - 3)
        start_idx, end_idx = _quarter_month_range(prev_y, prev_m)
        sy, sm = _month_from_index(start_idx)
        ey, em = _month_from_index(end_idx)
        range_filters["deadline_month"] = {"op": "between", "value": [_format_month(sy, sm), _format_month(ey, em)]}
        return

    if "ce trimestre" in q or "trimestre en cours" in q:
        start_idx, end_idx = _quarter_month_range(today.year, today.month)
        sy, sm = _month_from_index(start_idx)
        ey, em = _month_from_index(end_idx)
        range_filters["deadline_month"] = {"op": "between", "value": [_format_month(sy, sm), _format_month(ey, em)]}
        return

    if "mois dernier" in q or "mois precedent" in q:
        y, m = _month_from_index(today_idx - 1)
        filters["deadline_month"] = _format_month(y, m)
        return

    if "ce mois" in q or "du mois" in q:
        filters["deadline_month"] = _format_month(today.year, today.month)
        return

    if "annee derniere" in q or "an dernier" in q:
        filters["deadline_year"] = str(today.year - 1)
        return

    if "cette annee" in q:
        filters["deadline_year"] = str(today.year)
        return


def refine_intent(query: str, intent: dict, today: Optional[date] = None) -> dict:
    """Merge rule hints into LLM output and normalize."""
    q = _norm(query)
    hints = try_rule_based_parse(query)

    if hints and not intent.get("is_conversation") and intent.get("metric"):
        if hints.get("filters"):
            for k, v in hints["filters"].items():
                intent.setdefault("filters", {})
                if k not in intent["filters"]:
                    intent["filters"][k] = v
        if hints.get("range_filters") and not intent.get("range_filters"):
            intent["range_filters"] = hints["range_filters"]
        if hints.get("limit") and not intent.get("limit"):
            intent["limit"] = hints["limit"]
        if hints.get("use_raw_table"):
            intent["use_raw_table"] = True
            intent["chart_type"] = "table"

    # Détecté ici plutôt que dans le seul parseur de retouches : « ajoute … » doit
    # être compris qu'il passe par le modèle ou par le chemin déterministe.
    if _APPEND_PATTERN.search(q):
        intent["append"] = True

    if not intent.get("limit"):
        m_top = re.search(r"top\s*(\d+)|(\d+)\s*premier", q)
        if m_top:
            intent["limit"] = int(m_top.group(1) or m_top.group(2))

    # "offre(s)/opportunité(s) pondérée(s)" est un terme métier défini explicitement :
    # probabilité de gain >= 80 % ET statut "Offre remise" — jamais "montant pondéré"
    # (le metric weighted_amount, ex. "montant pondéré par pays"), qui ne doit pas
    # déclencher ce filtre. D'où l'exigence que "offre"/"opportunité" précède "pondéré"
    # de près : ça exclut "montant pondéré", où aucun des deux mots n'apparaît avant.
    # Ce n'est qu'un filtre — le type d'affichage (table/KPI/graphique) reste piloté
    # normalement par le reste de la question, jamais forcé ici.
    # DEUX critères, réunis par un OU : déjà remise, OU probabilité ≥ 80 %. L'un
    # suffit. La réunion ne peut pas s'écrire avec les filtres de l'intention, qui
    # sont tous combinés par ET — d'où un drapeau, que les deux moteurs traduisent
    # à partir de la même définition (business_rules.hot_deal_sql / hot_deal_mask).
    if _WEIGHTED_OFFER_PATTERN.search(q) or _HOT_DEAL_PATTERN.search(q):
        intent["hot_deals"] = True
        # Le statut que le MODÈLE a ajouté de lui-même est retiré. Il en posait un
        # systématiquement (« Offre remise »), ce qui le transformait en condition
        # SUPPLÉMENTAIRE : la réunion redevenait une intersection, et la même notion
        # répondait 7 opportunités à une formulation et 105 à une autre.
        #
        # Un statut que la QUESTION nomme est en revanche conservé : « affaires
        # chaudes gagnées » restreint légitimement le périmètre. C'est la question
        # qui fait foi, jamais l'initiative du modèle.
        if isinstance(intent.get("filters"), dict) and _detect_status(q) is None:
            intent["filters"].pop("status", None)
        # Idem pour la borne de probabilité : posée en plus du drapeau, elle
        # rétablirait le ET qu'on vient de retirer.
        if isinstance(intent.get("range_filters"), dict):
            intent["range_filters"].pop("win_probability", None)

    # « offres remises » = toutes celles effectivement déposées, y compris gagnées et
    # perdues depuis (business_rules.SUBMITTED_STATUSES). Placé APRÈS la règle des
    # offres pondérées, qui est plus spécifique et vise un tout autre périmètre.
    # Filtrer sur `status` lève au passage l'exclusion par défaut des affaires
    # perdues — ce qui est voulu : une offre perdue a bien été remise.
    elif _SUBMITTED_OFFER_PATTERN.search(q):
        intent.setdefault("filters", {})
        intent["filters"]["status"] = list(SUBMITTED_STATUSES)

    # Une NÉGATION dans la question fait autorité sur ce que le modèle a proposé.
    # « budget des offres non gagnées » lui faisait poser filters.status = « Offre
    # gagnée » : la réponse exacte à la question inverse, 30 080 000 DT annoncés là
    # où le chiffre demandé est tout autre. Le code tranche, comme partout ici.
    _, statuts_nies = _statuts_de_la_question(q)
    if statuts_nies:
        filtres = intent.get("filters") or {}
        pose = filtres.get("status")
        poses = pose if isinstance(pose, list) else ([pose] if pose else [])
        restants = [s for s in poses if s not in statuts_nies]
        if restants:
            filtres["status"] = restants[0] if len(restants) == 1 else restants
        else:
            filtres.pop("status", None)
        intent["filters"] = filtres
        exclus = list(intent.get("exclude_statuses") or [])
        intent["exclude_statuses"] = exclus + [s for s in statuts_nies if s not in exclus]

    # Ce que les MOTS de la question demandent. La forme retenue est ensuite validée
    # contre la forme réelle des données par choose_chart_type, en fin de fonction :
    # « répartition par pays » appelle bien un camembert, mais il y a 19 pays.
    dimension = intent.get("dimension", "")
    if any(w in q for w in ("camembert", "repartition", "pourcentage", "proportion")):
        if dimension:
            intent["chart_type"] = "pie"
    if any(w in q for w in ("liste", "lister", "detail")):
        intent["use_raw_table"] = True
        intent["chart_type"] = "table"

    # Un entonnoir de vente n'a de sens que sur le statut (les étapes du pipeline) —
    # imposé plutôt que de compter sur le LLM pour le deviner correctement à chaque fois.
    if intent.get("chart_type") == "funnel":
        intent["dimension"] = "status"

    # Une carte de chaleur croise toujours deux dimensions (voir db_layer.py) ; si
    # aucune n'a été précisée, "country" est un choix par défaut raisonnable — grande
    # cardinalité, le plus intéressant à croiser avec les 3 practices fixes.
    if intent.get("chart_type") == "heatmap" and not intent.get("dimension"):
        intent["dimension"] = "country"

    # Le scatter affiche toujours budget × probabilité de gain × montant pondéré —
    # fixé plutôt que piloté par "metric" (voir dac_composer.py). Sans ce verrou,
    # un metric="win_probability" ferait appliquer la mise à l'échelle ×100 (destinée
    # à un pourcentage agrégé unique) sur le champ brut utilisé comme axe Y du nuage.
    if intent.get("chart_type") == "scatter":
        intent["metric"] = "budget"

    # "days_remaining < N" (ou "<=") sous-entend toujours une échéance encore À VENIR —
    # jamais déjà passée. Sans ce garde-fou déterministe, un LLM qui produit "<" au lieu
    # de "between" (l'instruction du prompt n'est pas une garantie à 100%) laisserait
    # passer des opportunités expirées depuis des semaines dans une liste "urgente".
    days_filter = intent.get("range_filters", {}).get("days_remaining")
    if days_filter and days_filter.get("op") in ("<", "<="):
        try:
            upper = float(days_filter["value"])
        except (TypeError, ValueError):
            upper = None
        if upper is not None and upper >= 0:
            intent["range_filters"]["days_remaining"] = {"op": "between", "value": [0, days_filter["value"]]}

    # Toute requête filtrant sur days_remaining porte sur l'urgence d'une échéance —
    # une opportunité déjà close (gagnée/perdue/signée...) n'a plus rien d'urgent,
    # même si sa deadline technique tombe dans la fenêtre demandée. Même règle que
    # backend/alerts.py pour les emails de rappel : une seule liste de statuts exclus,
    # jamais deux définitions différentes de "actif" selon le canal.
    if "days_remaining" in intent.get("range_filters", {}):
        intent["exclude_statuses"] = list(EXCLUDED_STATUSES)

    # L'agrégation dépend de la métrique ET de ce que la question demande. Un
    # comptage reste un comptage et une probabilité se moyenne toujours ; mais pour
    # un montant, « budget moyen par pays » et « budget par pays » sont deux
    # questions différentes. Le mot était jusqu'ici ignoré : la somme partait sous
    # l'étiquette « moyen », soit 34 530 000 DT affichés là où la moyenne vaut
    # 466 622 DT.
    if intent.get("metric") == "nb_opportunities":
        intent["aggregation"] = "count"
    elif intent.get("metric") == "win_probability":
        intent["aggregation"] = "avg"
    elif _MOYENNE_PATTERN.search(q):
        intent["aggregation"] = "avg"
    else:
        intent.setdefault("aggregation", "sum")

    if not intent.get("is_conversation") and intent.get("metric"):
        _apply_relative_period(q, intent, today or date.today())

    intent.setdefault("limit", 0)

    # « combien de clients différents » compte des VALEURS DISTINCTES, pas des lignes.
    # Sans cette règle, la question renvoyait 229 (le nombre d'opportunités) là où la
    # réponse est 84 — un chiffre faux, et faux d'un ordre de grandeur.
    if not intent.get("is_conversation"):
        axe = _axe_a_denombrer(q)
        if axe:
            intent["metric"] = "nb_opportunities"
            # `count_distinct` porte LA COLONNE comptée, et non un simple drapeau.
            # Avec un booléen, la colonne comptée était `dimension` — si bien qu'une
            # suite comme « par practice » écrasait l'axe et changeait ce qu'on
            # comptait : « combien de clients différents » (84) suivi de « par
            # practice » répondait 3, le nombre de practices, au lieu des 23/59/52
            # clients distincts par practice qui étaient demandés.
            #
            # Séparer les deux rend la suite naturelle : `count_distinct` dit QUOI
            # compter, `dimension` dit par quoi le regrouper.
            intent["count_distinct"] = axe
            intent["dimension"] = ""
            intent["chart_type"] = "kpi_card"
            intent["use_raw_table"] = False

    # Les bornes chiffrées que la question énonce. `setdefault` par colonne : ce que
    # le modèle a déjà posé fait foi, on ne comble que ce qui manque.
    if not intent.get("is_conversation") and intent.get("metric"):
        for colonne, regle in _bornes_chiffrees(q, intent.get("metric") or "budget").items():
            intent.setdefault("range_filters", {}).setdefault(colonne, regle)

    # Une probabilité qui sert de CRITÈRE ne peut pas être aussi la MESURE.
    # « offres à plus de 80 % de probabilité » posait bien la borne, mais gardait
    # win_probability comme métrique : la réponse affichait alors 100 % — la
    # probabilité moyenne des offres retenues — au lieu de dire combien il y en a.
    # La question porte sur les offres ; la probabilité les sélectionne.
    if (intent.get("metric") == "win_probability"
            and "win_probability" in (intent.get("range_filters") or {})
            and not _MOYENNE_PATTERN.search(q)):
        intent["metric"] = "nb_opportunities"

    # Une valeur NIÉE passe des filtres aux exclusions. « budget par pays hors
    # Tunisie » posait `country = Tunisie` : l'inverse exact de la question.
    if not intent.get("is_conversation") and intent.get("metric"):
        nies = _filtres_nies(q, intent.get("filters") or {})
        for colonne, rejetees in nies.items():
            restantes = [v for v in (intent["filters"][colonne]
                                     if isinstance(intent["filters"][colonne], (list, tuple))
                                     else [intent["filters"][colonne]])
                         if v not in rejetees]
            if restantes:
                intent["filters"][colonne] = restantes[0] if len(restantes) == 1 else restantes
            else:
                del intent["filters"][colonne]
            exclusions = intent.setdefault("exclude_filters", {})
            deja = exclusions.get(colonne) or []
            deja = deja if isinstance(deja, list) else [deja]
            exclusions[colonne] = deja + [v for v in rejetees if v not in deja]

    # Une année nommée dans la question devient un filtre. Elle ne l'était sur aucun
    # chemin : ni le parseur rapide ni le modèle ne la posaient de façon fiable, si
    # bien que « budget par pays en 2026 » répondait sur tous les exercices confondus.
    # `setdefault` : si le modèle en a déjà posé un (y compris une liste, pour une
    # comparaison), c'est le sien qui vaut.
    if not intent.get("is_conversation") and intent.get("metric"):
        annee = _annee_demandee(q)
        if annee and "deadline_year" not in (intent.get("filters") or {}):
            intent.setdefault("filters", {})["deadline_year"] = annee

    # « urgent » borne l'échéance sur la même fenêtre que les alertes email : une
    # seule définition de l'urgence, quel que soit le canal.
    if (not intent.get("is_conversation") and intent.get("metric")
            and _URGENCE_PATTERN.search(q)
            and "days_remaining" not in (intent.get("range_filters") or {})):
        intent.setdefault("range_filters", {})["days_remaining"] = {
            "op": "between", "value": [0, ALERT_WINDOW_DAYS],
        }

    # Un axe que la question nomme sans ambiguïté et que le modèle a laissé vide est
    # rattrapé ici. Le parseur rapide le faisait déjà ; le chemin par le modèle, non,
    # si bien que « budget par client » pouvait encore repartir sans répartition —
    # et donc avec le total du portefeuille. La table de phrases fait autorité sur le
    # modèle, comme partout ailleurs dans ce fichier.
    if not intent.get("is_conversation") and intent.get("metric") and not intent.get("dimension"):
        detectee = _detect_dimension(q)
        if detectee:
            intent["dimension"] = detectee

    # Dernière vérification avant de répondre : la question a-t-elle été comprise
    # EN ENTIER ? Un axe ou une mesure qui n'existe pas était jusqu'ici abandonné en
    # chemin, et le total global partait comme réponse. Mieux vaut le dire et nommer
    # ce qui est disponible que de renvoyer un chiffre juste à une autre question.
    if not intent.get("is_conversation") and intent.get("metric"):
        for probleme in (_mesure_indisponible(q),
                         _annee_hors_donnees(q),
                         _axe_incompris(q, intent.get("dimension") or "")):
            if probleme:
                logger.info("Demande hors périmètre — clarification renvoyée : %s", probleme)
                return _clarification(probleme)

    # Arbitrage final de la forme, une fois métrique, dimension, filtres et limite
    # tous connus — c'est seulement à ce stade qu'on peut mesurer la cardinalité
    # réelle et savoir si la forme demandée sert encore la question.
    if not intent.get("is_conversation") and intent.get("metric"):
        chart, raison = choose_chart_type(intent)
        intent["chart_type"] = chart
        intent["chart_type_reason"] = raison

    return intent
