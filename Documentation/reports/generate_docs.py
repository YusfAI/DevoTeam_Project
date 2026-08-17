"""Génère les deux documents .docx (rapport professionnel + guide technique) au
branding Devoteam, à partir du contenu réel du projet (code, tests, PROGRESS.md).

Script one-shot, à relancer si le contenu doit être régénéré après une évolution
du projet. Nécessite python-docx (voir requirements-dev.txt) — pas une dépendance
runtime de l'application.

Usage : python Documentation/reports/generate_docs.py
"""
import os

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # Documentation/reports/
ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DOC_DIR = SCRIPT_DIR
LOGO = os.path.join(ROOT, "Dev_logo_rgb.png")
EMAIL_PROOF = os.path.join(SCRIPT_DIR, "assets", "email_proof.png")

CORAL = RGBColor(0xF2, 0x40, 0x5A)
CORAL_HEX = "F2405A"
CORAL_STRONG = RGBColor(0xD4, 0x2A, 0x45)
CORAL_STRONG_HEX = "D42A45"
CORAL_TINT_HEX = "FCE9EC"
CHARCOAL = RGBColor(0x24, 0x24, 0x22)
MUTED = RGBColor(0x52, 0x51, 0x4E)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

FONT = "Calibri"


# ---------- helpers de style ----------

def new_document():
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)

    style = doc.styles["Normal"]
    style.font.name = FONT
    style.font.size = Pt(10.5)
    style.font.color.rgb = CHARCOAL
    style.paragraph_format.space_after = Pt(6)
    style.paragraph_format.line_spacing = 1.18
    return doc


def _bottom_border(paragraph, hex_color, size="18"):
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), hex_color)
    pBdr.append(bottom)
    pPr.append(pBdr)


def shade_cell(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def add_cover(doc, doc_label, title, subtitle):
    doc.add_picture(LOGO, width=Inches(2.3))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for _ in range(3):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(doc_label.upper())
    run.font.size = Pt(12)
    run.font.bold = True
    run.font.color.rgb = CORAL
    run.font.name = FONT

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = p2.add_run(title)
    run2.font.size = Pt(27)
    run2.font.bold = True
    run2.font.color.rgb = CHARCOAL

    p3 = doc.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run3 = p3.add_run(subtitle)
    run3.font.size = Pt(13)
    run3.font.color.rgb = MUTED

    for _ in range(6):
        doc.add_paragraph()

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    mrun = meta.add_run("DevoTeam Dashboard — Projet interne  |  Août 2026  |  Youssef Hmidi")
    mrun.font.size = Pt(10)
    mrun.font.color.rgb = MUTED
    doc.add_page_break()


def add_sommaire(doc, entries):
    add_h1(doc, "Sommaire")
    for entry in entries:
        p = doc.add_paragraph(style="List Bullet")
        r = p.add_run(entry)
        r.font.color.rgb = CHARCOAL
    doc.add_page_break()


def add_h1(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(20)
    p.paragraph_format.space_after = Pt(10)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.size = Pt(18)
    run.font.bold = True
    run.font.color.rgb = CORAL
    _bottom_border(p, CORAL_STRONG_HEX)
    return p


def add_h2(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.size = Pt(13.5)
    run.font.bold = True
    run.font.color.rgb = CHARCOAL
    return p


def add_h3(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.size = Pt(11.5)
    run.font.bold = True
    run.font.color.rgb = CORAL_STRONG
    return p


def add_body(doc, text, bold=False, italic=False):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    return p


def add_cue(doc, text):
    """Didascalie pour un script oral (ex: [Montrer le chat à l'écran]) — italique,
    ton discret, jamais confondue avec le texte à prononcer."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    run = p.add_run(text)
    run.italic = True
    run.font.size = Pt(9.5)
    run.font.color.rgb = MUTED
    return p


def add_bullet(doc, text, lead=None):
    p = doc.add_paragraph(style="List Bullet")
    if lead:
        r = p.add_run(lead + " ")
        r.bold = True
        r.font.color.rgb = CORAL_STRONG
    p.add_run(text)
    return p


def add_numbered(doc, text, lead=None):
    p = doc.add_paragraph(style="List Number")
    if lead:
        r = p.add_run(lead + " ")
        r.bold = True
        r.font.color.rgb = CORAL_STRONG
    p.add_run(text)
    return p


def add_table(doc, headers, rows):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].paragraphs[0].text = ""
        run = hdr_cells[i].paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = Pt(9.5)
        run.font.color.rgb = WHITE
        shade_cell(hdr_cells[i], CORAL_HEX)
    for r_i, row in enumerate(rows):
        cells = table.add_row().cells
        for i, val in enumerate(row):
            cells[i].paragraphs[0].text = ""
            run = cells[i].paragraphs[0].add_run(str(val))
            run.font.size = Pt(9.5)
            if r_i % 2 == 1:
                shade_cell(cells[i], "FAFAF8")
    doc.add_paragraph()
    return table


def add_image_block(doc, path, width_inches, caption=None):
    doc.add_picture(path, width=Inches(width_inches))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    if caption:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(caption)
        run.italic = True
        run.font.size = Pt(9)
        run.font.color.rgb = MUTED


def add_code_block(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(10)
    shade_cell  # noqa: keep import usage grouped
    run = p.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(9)
    run.font.color.rgb = CHARCOAL
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), "F3F2EE")
    pPr.append(shd)
    pBdr = OxmlElement("w:pBdr")
    for side in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "4")
        el.set(qn("w:color"), "E1E0D9")
        pBdr.append(el)
    pPr.append(pBdr)


# ---------- Document 1 : rapport professionnel ----------

def build_rapport_professionnel():
    doc = new_document()
    add_cover(
        doc,
        "Rapport de projet",
        "DevoTeam Dashboard",
        "Dashboard commercial conversationnel — Rapport professionnel",
    )
    add_sommaire(doc, [
        "Résumé exécutif",
        "Contexte et besoin métier",
        "Solution proposée",
        "Fonctionnalités",
        "Conception et architecture",
        "Stack technique",
        "Sécurité et fiabilité",
        "Preuve de fonctionnement — alertes deadlines",
        "État d'avancement et roadmap",
        "Conclusion",
    ])

    # --- Résumé exécutif ---
    add_h1(doc, "1. Résumé exécutif")
    add_body(doc,
        "DevoTeam Dashboard est une application de tableau de bord commercial "
        "conversationnel : un utilisateur pose une question en français dans un chat "
        "(ex. « budget par pays pour Risk Advisory »), et l'application produit "
        "instantanément le graphique, la carte KPI ou le tableau correspondant, à "
        "partir des données réelles des opportunités commerciales stockées en base. "
        "Aucune compétence SQL ou BI n'est requise côté utilisateur.")
    add_body(doc,
        "Le projet est aujourd'hui fonctionnel de bout en bout, hébergé localement, "
        "et couvre l'ensemble du cycle : compréhension du langage naturel, "
        "génération de requêtes sécurisées, visualisation (huit types de graphiques au "
        "choix), et un système d'alerte proactive par email et dans l'interface pour "
        "les opportunités dont l'échéance approche, avec une donnée « jours restants » "
        "recalculée chaque jour pour rester exacte.")

    # --- Contexte et besoin métier ---
    add_h1(doc, "2. Contexte et besoin métier")
    add_body(doc,
        "Les équipes commerciales suivent un grand nombre d'opportunités (appels "
        "d'offres, manifestations d'intérêt, consultations…) réparties sur plusieurs "
        "pays et practices (Digital Transformation, Risk Advisory, Data Management). "
        "Deux problèmes récurrents motivent ce projet :")
    add_bullet(doc,
        "l'analyse de ces données (budget par pays, taux de réussite, répartition "
        "par statut…) nécessite normalement un outil BI ou des requêtes SQL — un frein "
        "pour un usage quotidien rapide par des non-techniciens ;",
        lead="Accès à l'information :")
    add_bullet(doc,
        "une opportunité dont l'échéance approche peut passer inaperçue si personne "
        "ne consulte le dashboard ce jour-là, avec un risque direct de manquer une "
        "date de remise d'offre.",
        lead="Risque de deadline manquée :")
    add_body(doc,
        "Le besoin métier est donc double : donner un accès conversationnel, "
        "immédiat et fiable aux données commerciales, et transformer le suivi des "
        "échéances d'un geste passif (consulter le dashboard) en une alerte active "
        "(le système prévient l'équipe).")

    # --- Solution proposée ---
    add_h1(doc, "3. Solution proposée")
    add_body(doc,
        "L'application répond à ce besoin par un assistant conversationnel branché "
        "directement sur les données commerciales réelles, avec une garantie forte : "
        "le système ne répond jamais par une donnée inventée. Si la demande est "
        "ambiguë (métrique, filtre ou valeur non reconnue), il demande une "
        "clarification plutôt que de deviner un résultat plausible mais faux — un "
        "choix de conception délibéré, central pour la confiance dans les chiffres "
        "affichés à des fins commerciales.")
    add_body(doc,
        "Pour le risque de deadline manquée, une brique d'alerte a été ajoutée : "
        "chaque jour, le système identifie automatiquement les opportunités encore "
        "actives dont l'échéance tombe dans les 7 jours suivants, envoie un email "
        "récapitulatif, et affiche un bandeau d'alerte directement dans le dashboard.")

    # --- Fonctionnalités ---
    add_h1(doc, "4. Fonctionnalités")
    add_h2(doc, "4.1 Chat et compréhension du langage naturel")
    add_bullet(doc, "Questions en français libre, sans syntaxe imposée.")
    add_bullet(doc, "Contexte multi-tour : une question de suivi (« et pour Data Management ? ») "
                     "hérite automatiquement du contexte de la question précédente.")
    add_bullet(doc, "Dates et périodes relatives comprises et calculées de façon fiable "
                     "(« ce mois-ci », « l'année dernière », « le trimestre dernier »…).")
    add_bullet(doc, "Requêtes de comparaison entre plusieurs valeurs (« compare la France et le Maroc »).")
    add_bullet(doc, "Demande de clarification explicite si la question reste ambiguë, plutôt "
                     "qu'une réponse devinée.")
    add_bullet(doc, "L'historique de conversation reste disponible après un rechargement de page — "
                     "une analyse en cours n'est plus perdue par un rafraîchissement accidentel.")

    add_h2(doc, "4.2 Visualisation")
    add_bullet(doc, "Huit types de rendu au choix, décidés automatiquement selon la question : "
                     "barres, courbes, camemberts, cartes KPI, tableaux détaillés, entonnoir de "
                     "vente, nuage de points et carte de chaleur (Vega-Lite).")
    add_bullet(doc, "Entonnoir de vente : nombre ou budget par étape du pipeline commercial, dans "
                     "l'ordre réel du cycle de vente — visualise directement où les deals se perdent.")
    add_bullet(doc, "Nuage de points : budget vs probabilité de gain, taille des points = montant "
                     "pondéré — révèle si les gros budgets ont statistiquement plus de chances de "
                     "gagner.")
    add_bullet(doc, "Carte de chaleur : intensité croisée entre une dimension (pays, statut…) et "
                     "practice, pour repérer d'un coup d'œil les combinaisons les plus fortes.")
    add_bullet(doc, "Bascule automatique camembert → barres horizontales au-delà de 6 segments, "
                     "pour rester lisible.")
    add_bullet(doc, "Thème clair / sombre, palette de couleurs validée pour l'accessibilité "
                     "(daltonisme).")
    add_bullet(doc, "Mise en cache des graphiques déjà générés pour un ré-affichage instantané.")

    add_h2(doc, "4.3 Alertes deadlines (nouvelle fonctionnalité)")
    add_bullet(doc, "Email quotidien automatique récapitulant les opportunités actives à "
                     "échéance ≤ 7 jours, envoyé chaque matin à 8h.")
    add_bullet(doc, "Rappel répété chaque jour tant que l'échéance n'est pas passée — "
                     "aucune opportunité à risque ne peut être oubliée.")
    add_bullet(doc, "Bandeau d'alerte visible directement dans le dashboard, avec le détail "
                     "par opportunité (client, pays, practice, statut, budget, jours restants).")
    add_bullet(doc, "Exclusion automatique des opportunités déjà closes (gagnées, perdues, "
                     "signées, infructueuses…) pour ne pas polluer l'alerte — la même règle "
                     "s'applique désormais à la question « opportunités urgentes » posée "
                     "directement dans le chat, pour une définition cohérente sur tous les canaux.")
    add_bullet(doc, "Donnée « jours restants » recalculée chaque nuit à partir de la date "
                     "réelle du jour, pour ne jamais afficher un chiffre obsolète.")

    add_h2(doc, "4.4 Synchronisation Google Sheets (nouvelle fonctionnalité)")
    add_bullet(doc, "Un Google Sheet sert de formulaire d'ajout et de modification d'opportunités — "
                     "plus simple à éditer au quotidien qu'une base de données directement.")
    add_bullet(doc, "Synchronisation à sens unique (Sheet vers base) toutes les 15 minutes, au "
                     "démarrage du serveur, et à la demande — la base reste la seule source lue par "
                     "le chat, les graphiques et les alertes, jamais le Sheet directement.")
    add_bullet(doc, "Chaque ligne est validée indépendamment (dates, montants, statuts) ; une ligne "
                     "invalide est journalisée et sautée, sans jamais bloquer l'import des autres.")
    add_bullet(doc, "Volontairement sans suppression automatique : retirer une ligne du Sheet ne "
                     "supprime jamais l'opportunité correspondante en base — un choix de prudence "
                     "assumé sur une tâche qui tourne sans surveillance humaine.")

    add_h2(doc, "4.5 Branding et expérience utilisateur")
    add_bullet(doc, "Interface habillée aux couleurs et au logo Devoteam.")
    add_bullet(doc, "Micro-interactions et animations (fond animé, transitions, mise en avant "
                     "des nouveaux résultats).")
    add_bullet(doc, "Mode sombre entièrement lisible : deux défauts de contraste corrigés "
                     "(en-tête et texte d'alerte) sans rien changer au mode clair déjà validé.")

    # --- Conception et architecture ---
    add_h1(doc, "5. Conception et architecture")
    add_body(doc,
        "L'architecture suit un principe simple : le LLM ne produit jamais "
        "directement un graphique ou du SQL. Il transforme la question de "
        "l'utilisateur en une structure intermédiaire strictement validée (métrique, "
        "dimension, filtres, type de graphique…), qui est ensuite traduite en requête "
        "SQL sécurisée par du code déterministe. Cette séparation garantit que les "
        "résultats affichés proviennent toujours des données réelles.")
    add_table(doc,
        ["Étape", "Rôle"],
        [
            ["1. Chat utilisateur", "L'utilisateur pose sa question en français dans l'interface."],
            ["2. Compréhension d'intention", "Le LLM (ou un parseur rapide par mots-clés pour les cas "
             "simples) extrait une intention structurée et validée."],
            ["3. Résolution des filtres", "Chaque valeur de filtre (pays, statut…) est vérifiée contre "
             "les données réelles ; en cas de doute, une clarification est demandée."],
            ["4. Requête SQL sécurisée", "L'intention est traduite en requête paramétrée sur une liste "
             "blanche de tables/colonnes autorisées."],
            ["5. Génération du résultat", "Graphique Vega-Lite, carte KPI ou tableau, plus un message "
             "texte calculé directement depuis les données (jamais rédigé par le LLM)."],
            ["6. Affichage", "Le frontend React affiche le résultat, avec mise en cache pour les "
             "requêtes déjà vues."],
        ])
    add_body(doc,
        "L'alerte deadlines suit le même principe de fiabilité : la vérification des "
        "échéances se fait par un calcul de date direct en base (jamais une valeur "
        "mise en cache trop longtemps), sur un calendrier automatique indépendant de "
        "toute action utilisateur.")

    # --- Stack technique ---
    add_h1(doc, "6. Stack technique")
    add_table(doc,
        ["Brique", "Technologie", "Pourquoi"],
        [
            ["Backend / API", "FastAPI (Python)", "Framework léger, typé, avec validation de données native "
             "(Pydantic) — cohérent avec l'exigence anti-hallucination."],
            ["Base de données", "MySQL / MariaDB (XAMPP)", "Vues pré-agrégées par dimension, requêtes "
             "paramétrées, adapté au volume et à l'hébergement local."],
            ["Compréhension du langage", "Google Gemini — gemini-flash-lite-latest", "Sortie JSON "
             "structurée, faible latence, complétée par une validation stricte côté serveur."],
            ["Visualisation", "Vega-Lite / vega-embed", "Grammaire de graphiques déclarative en JSON, génération "
             "automatique fiable, rendu navigateur natif."],
            ["Frontend", "Vite + React", "Interface réactive, thème clair/sombre, build optimisé pour "
             "un déploiement local en un seul processus."],
            ["Planification des tâches", "APScheduler", "Exécution fiable des vérifications quotidiennes "
             "(alertes deadlines, mise à jour des données) sans dépendance externe."],
            ["Envoi d'emails", "SMTP Gmail (STARTTLS)", "Solution simple et gratuite pour un usage interne, "
             "sans infrastructure d'envoi supplémentaire à maintenir."],
            ["Synchro Google Sheets", "Google Sheets API (gspread)", "Permet aux équipes commerciales de "
             "gérer les opportunités depuis un tableur familier, plutôt qu'en éditant la base directement."],
            ["Tests", "pytest (143 tests)", "Suite automatisée sans dépendance réseau/DB réelle (mocks), "
             "garde-fou contre les régressions."],
        ])
    add_body(doc,
        "Côté données, la base MySQL repose sur une table principale `opportunities` "
        "(360 opportunités commerciales, 18 colonnes : pays, practice, statut, "
        "budget, échéance…) et six vues pré-agrégées par dimension (pays, practice, "
        "statut, mois, source de financement, croisement pays/practice), qui "
        "accélèrent les questions les plus fréquentes du chat sans dupliquer les "
        "données.")

    # --- Sécurité et fiabilité ---
    add_h1(doc, "7. Sécurité et fiabilité")
    add_bullet(doc, "Aucune clé API ni identifiant n'est versionné dans le code source "
                     "(fichier .env exclu du dépôt git).")
    add_bullet(doc, "Le LLM ne peut interroger que les tables et colonnes d'une liste blanche "
                     "explicite — aucune requête SQL libre.")
    add_bullet(doc, "Toute valeur de filtre non reconnue avec confiance déclenche une demande "
                     "de clarification plutôt qu'une hypothèse silencieuse.")
    add_bullet(doc, "143 tests automatisés couvrent la compréhension du langage, la couche SQL, "
                     "la génération des graphiques, le système d'alerte et la synchronisation Sheets.")
    add_bullet(doc, "Le mot de passe d'envoi d'email est un mot de passe d'application dédié "
                     "(jamais le mot de passe principal du compte), également hors du dépôt git.")
    add_bullet(doc, "La clé de compte de service Google (accès au Sheet) est un fichier JSON exclu "
                     "du dépôt (dossier credentials/ entièrement gitignoré) — jamais commité, quel "
                     "que soit son nom.")

    # --- Preuve de fonctionnement ---
    add_h1(doc, "8. Preuve de fonctionnement — alertes deadlines")
    add_body(doc,
        "Capture d'écran ci-dessous : email de rappel automatique réellement reçu, "
        "listant les opportunités actives dont l'échéance tombait dans les 7 jours "
        "suivants au moment de l'envoi (5 et 7 jours restants), avec pays, practice, "
        "statut et budget pour chacune.")
    add_image_block(doc, EMAIL_PROOF, 6.3,
                     caption="Email d'alerte reçu dans la boîte de réception — preuve de bon fonctionnement.")

    # --- État d'avancement et roadmap ---
    add_h1(doc, "9. État d'avancement et roadmap")
    add_body(doc, "L'application est complète et fonctionnelle de bout en bout, en hébergement local. "
                   "Dix-sept phases de développement ont été livrées, de la mise en place du backend "
                   "jusqu'à la synchronisation Google Sheets et l'optimisation de ses performances "
                   "(dernières phases en date).", bold=False)
    add_h2(doc, "Améliorations envisagées (hors périmètre actuel)")
    add_bullet(doc, "Authentification et gestion multi-utilisateurs (restriction par practice/BU).")
    add_bullet(doc, "Suivi analytique des sessions utilisateur.")
    add_bullet(doc, "Barres empilées/groupées (2 dimensions croisées, ex: budget par pays décomposé "
                     "par statut) — nécessite une évolution du schéma d'intention.")

    # --- Conclusion ---
    add_h1(doc, "10. Conclusion")
    add_body(doc,
        "DevoTeam Dashboard transforme une problématique classique de BI (accès aux "
        "données commerciales, suivi des échéances) en une expérience conversationnelle "
        "fiable, à la fois simple d'usage pour les équipes commerciales et rigoureuse "
        "dans sa conception technique (validation stricte, tests automatisés, "
        "traçabilité des résultats). Les alertes deadlines par email et dans "
        "l'interface répondent directement au risque métier identifié : ne plus "
        "jamais manquer une échéance commerciale faute d'avoir consulté le dashboard "
        "à temps ; les nouveaux types de graphiques donnent aux équipes davantage de "
        "façons de présenter et d'expliquer ces données à un client.")

    out_path = os.path.join(DOC_DIR, "Rapport_Professionnel_DevoTeam_Dashboard.docx")
    doc.save(out_path)
    return out_path


# ---------- Document 2 : guide technique ----------

def build_guide_technique():
    doc = new_document()
    add_cover(
        doc,
        "Documentation technique",
        "DevoTeam Dashboard",
        "Guide technique détaillé — architecture, code et préparation entretien",
    )
    add_sommaire(doc, [
        "Vue d'ensemble de l'architecture",
        "Stack technique et justifications",
        "Structure du dépôt",
        "Base de données",
        "Pipeline requête → réponse",
        "Compréhension du langage naturel (backend/llm.py, intent_refiner.py)",
        "Couche SQL sécurisée (backend/db_layer.py, schema_and_whitelist.py)",
        "Génération des graphiques (backend/vega_generator.py)",
        "Réponses textuelles déterministes (backend/response_builder.py)",
        "Alertes deadlines (backend/alerts.py, maintenance.py, scheduler)",
        "Synchronisation Google Sheets (backend/sheets_sync.py)",
        "Frontend (Vite + React)",
        "Sécurité",
        "Tests automatisés",
        "Questions d'entretien probables",
        "Limites connues",
    ])

    # --- Vue d'ensemble ---
    add_h1(doc, "1. Vue d'ensemble de l'architecture")
    add_body(doc,
        "L'application suit un pipeline linéaire, chaque étape gérée par un module "
        "backend dédié. Le principe directeur : le LLM ne produit jamais directement "
        "un graphique ni du SQL — il produit uniquement un JSON intermédiaire "
        "strictement validé, que du code déterministe transforme ensuite en requête "
        "puis en visualisation.")
    add_code_block(doc,
        "Utilisateur (chat React)\n"
        "   │  POST /dashboard { query, previous_intent }\n"
        "   ▼\n"
        "backend/llm.py :: parse_user_query()\n"
        "   │  parseur rapide (mots-clés) OU appel Gemini + validation Pydantic\n"
        "   │  résolution des filtres (fuzzy match) contre les données réelles\n"
        "   ▼  intent = {metric, dimension, filters, chart_type, aggregation, ...}\n"
        "backend/db_layer.py :: build_and_execute_query(intent)\n"
        "   │  requête SQL paramétrée sur une liste blanche de tables/colonnes\n"
        "   ▼  data = [ {...}, {...} ]\n"
        "backend/vega_generator.py + response_builder.py\n"
        "   │  spec Vega-Lite (ou carte KPI / table) + message texte calculé\n"
        "   ▼\n"
        "Frontend React :: DashboardPanel + vega-embed\n"
        "   affichage du graphique / KPI / tableau")
    add_body(doc,
        "En parallèle, un scheduler (APScheduler) exécute deux tâches quotidiennes "
        "indépendantes du chat : le recalcul de « jours restants » à minuit, et la "
        "vérification des échéances proches à 8h (voir section 10).")

    # --- Stack et justifications ---
    add_h1(doc, "2. Stack technique et justifications")
    add_h2(doc, "2.1 Pourquoi MySQL plutôt que SQLite (prévu dans le brief initial)")
    add_body(doc,
        "Le document de cadrage initial du projet envisageait SQLite pour sa "
        "simplicité. Le choix final s'est porté sur MySQL/MariaDB via XAMPP : accès "
        "concurrent plus robuste pour un backend FastAPI multi-requêtes, support natif "
        "des vues SQL pré-agrégées par dimension (utilisées pour accélérer les "
        "requêtes fréquentes comme « budget par pays »), et un pool de connexions "
        "(DBUtils PooledDB) adapté à ce moteur. Le schéma reste simple (une table "
        "principale `opportunities` + des vues), donc le coût de complexité "
        "supplémentaire par rapport à SQLite reste faible.")
    add_h2(doc, "2.2 Groq → Google Gemini (migration forcée en cours de projet)")
    add_body(doc,
        "Le mandat initial imposait un modèle open source à faible latence : Groq "
        "servait Llama 3.3 70B avec un `response_format: json_object` garantissant "
        "une sortie JSON syntaxiquement valide, mais pas le respect d'un schéma "
        "strict (contrairement à un mode « structured outputs » complet) — d'où "
        "l'importance de la couche de validation Pydantic + liste blanche placée "
        "juste après (section 6). Ce modèle a depuis été retiré du service par Groq "
        "(erreur 404 modèle introuvable, confirmée avec deux clés API différentes — "
        "pas un problème d'accès mais une dépréciation réelle), cassant toute "
        "question ne passant pas par le chemin rapide par mots-clés. Migration vers "
        "Google Gemini (`gemini-flash-lite-latest` — un alias plutôt qu'une version "
        "épinglée, pour ne pas revivre le même type de panne si Google fait tourner "
        "sa gamme) en gardant volontairement la même architecture (JSON libre + "
        "validation Pydantic + réparation heuristique) plutôt que d'adopter les "
        "sorties structurées strictes de Gemini (vérifiées disponibles à cette "
        "occasion) — changer de fournisseur ET d'architecture en même temps aurait "
        "ajouté un risque inutile sous pression. Deuxième surprise trouvée juste "
        "après, en conditions réelles : le premier modèle essayé (`gemini-flash-"
        "latest`) a un quota gratuit de seulement 5 requêtes/minute, épuisé en "
        "quelques messages de chat — la variante « lite » tient ~16 requêtes/minute "
        "pour une qualité d'extraction équivalente sur les mêmes tests, puisque "
        "c'est le schéma + Pydantic qui garantissent la précision, pas la taille du "
        "modèle. Un quota épuisé (429) et une surcharge transitoire (503, avec deux "
        "tentatives automatiques avant abandon) reçoivent maintenant chacun un "
        "message distinct plutôt que la même erreur générique.")
    add_h2(doc, "2.3 Pourquoi APScheduler plutôt qu'une tâche planifiée externe (cron/Task Scheduler)")
    add_body(doc,
        "L'application est un processus unique en local (`uvicorn`). APScheduler "
        "tourne dans ce même processus (`BackgroundScheduler`), démarré/arrêté via le "
        "cycle de vie FastAPI (`lifespan`) — aucune dépendance à un ordonnanceur "
        "système externe, ce qui simplifie le déploiement local. Limite assumée : si "
        "le processus est arrêté au moment précis d'une exécution planifiée, elle est "
        "manquée (pas de rattrapage automatique en cours de journée).")

    # --- Structure du dépôt ---
    add_h1(doc, "3. Structure du dépôt")
    add_table(doc,
        ["Chemin", "Contenu"],
        [
            ["backend/main.py", "Application FastAPI, endpoints, câblage du scheduler."],
            ["backend/llm.py", "Appel LLM, validation Pydantic, résolution des filtres, anti-hallucination."],
            ["backend/intent_refiner.py", "Parseur rapide par mots-clés, dates relatives, affinage de l'intention."],
            ["backend/db_layer.py", "Construction et exécution des requêtes SQL paramétrées."],
            ["backend/schema_and_whitelist.py", "Source unique de vérité : tables/colonnes autorisées, valeurs connues."],
            ["backend/vega_generator.py", "Génération des spécifications Vega-Lite."],
            ["backend/response_builder.py", "Messages texte déterministes (jamais générés par le LLM)."],
            ["backend/alerts.py", "Requête des opportunités à échéance proche, envoi de l'email d'alerte."],
            ["backend/maintenance.py", "Recalcul quotidien de days_remaining."],
            ["backend/sheets_sync.py", "Synchronisation Google Sheets -> MySQL (table opportunities uniquement)."],
            ["backend/db.py", "Pool de connexions MySQL (DBUtils PooledDB), paresseux."],
            ["frontend/src/", "Application Vite + React (composants, hooks, styles)."],
            ["tests/", "Suite pytest — 143 tests, aucune dépendance réseau/DB réelle."],
            ["data/devoteam_dashboard_mysql.sql", "Dump SQL de référence (schéma + données)."],
            ["Documentation/reports/", "Ce rapport, le guide technique et leur générateur (generate_docs.py)."],
            ["Documentation/planning/", "Brief initial du projet et données sources (hors suivi git du dépôt)."],
        ])

    # --- Base de données ---
    add_h1(doc, "4. Base de données")
    add_body(doc,
        "Moteur MySQL/MariaDB (XAMPP en local, utilisateur root sans mot de passe par "
        "défaut). Le schéma tient volontairement en peu de tables : une table de "
        "faits, six vues de lecture pré-agrégées, et deux tables techniques pour le "
        "cache et l'historique.")

    add_h2(doc, "4.1 Table de faits — opportunities")
    add_body(doc,
        "360 lignes au moment de la rédaction. Chaque ligne représente une "
        "opportunité commerciale ; c'est la seule table sur laquelle des écritures "
        "ont lieu (mise à jour quotidienne de days_remaining).")
    add_table(doc,
        ["Colonne", "Type", "Rôle"],
        [
            ["id", "INT, clé primaire", "Identifiant unique."],
            ["country", "VARCHAR(100)", "Pays de l'opportunité (indexé)."],
            ["created_date", "DATE", "Date de création de l'opportunité."],
            ["deadline", "DATE", "Date limite de remise — source de vérité pour toute "
             "notion d'urgence (jamais une valeur mise en cache)."],
            ["deadline_month / deadline_year", "VARCHAR(7) / INT", "Dérivées de deadline, "
             "utilisées comme dimensions d'analyse (indexées)."],
            ["days_remaining", "INT, nullable", "Jours restants — recalculée chaque nuit "
             "depuis deadline (voir section 10.1), jamais la source de vérité elle-même."],
            ["practice", "VARCHAR(100)", "Digital Transformation / Risk Advisory / Data "
             "Management (indexé)."],
            ["description, buyer, partner", "TEXT / VARCHAR", "Informations descriptives "
             "libres."],
            ["opp_type", "VARCHAR(50)", "AO, DP, AMI, Consultation, Prospection…"],
            ["status", "VARCHAR(100)", "Statut du cycle de vente (indexé) — 16 valeurs "
             "possibles, dont les 7 statuts « clos » exclus des alertes."],
            ["budget, financial_offer, weighted_amount", "DOUBLE, nullable", "Montants en "
             "euros ; weighted_amount ~47% NULL (offres sans probabilité assignée)."],
            ["funding_source", "VARCHAR(100), nullable", "Source de financement (indexée)."],
            ["win_probability", "DOUBLE, nullable", "Fraction 0–1 (0.74 = 74%), jamais "
             "stockée déjà multipliée par 100 — voir response_builder.py."],
        ])

    add_h2(doc, "4.2 Vues pré-agrégées (lecture seule)")
    add_body(doc,
        "Chacune est un simple GROUP BY sur opportunities (recalculée à la demande "
        "par MySQL, pas matérialisée) — elles existent pour donner au LLM des noms de "
        "colonnes déjà agrégés et simples plutôt que de lui faire recalculer une "
        "agrégation à chaque requête, et pour que db_layer.py puisse choisir la bonne "
        "source selon la dimension demandée (voir section 7).")
    add_table(doc,
        ["Vue", "Regroupée par", "Colonnes agrégées"],
        [
            ["v_by_country", "country", "nb_opportunities, total_budget, total_offer, total_weighted"],
            ["v_by_practice", "practice", "nb_opportunities, total_budget, total_offer, total_weighted"],
            ["v_by_status", "status", "nb_opportunities, total_budget, total_offer"],
            ["v_by_month", "deadline_month", "nb_opportunities, total_budget, total_offer, total_weighted"],
            ["v_by_funding_source", "funding_source", "nb_opportunities, total_budget"],
            ["v_by_country_practice", "country, practice", "nb_opportunities, total_budget, total_weighted"],
        ])
    add_body(doc,
        "Une vue qui ne couvre pas la métrique demandée (ex. weighted_amount sur "
        "v_by_status) déclenche un repli automatique vers un GROUP BY à la volée sur "
        "opportunities plutôt qu'une erreur (voir section 7).")

    add_h2(doc, "4.3 Tables techniques")
    add_table(doc,
        ["Table", "Rôle"],
        [
            ["dashboard_requests", "Historique : chaque question posée au chat, avec l'intention "
             "JSON extraite — utile pour l'audit et l'amélioration continue du prompt."],
            ["generated_dashboards", "Cache des spécifications Vega-Lite déjà générées, indexé par le "
             "hash SHA-256 de l'intention — évite de régénérer une spec identique."],
            ["scheduler_state", "Une ligne par job planifié (job_name, last_run_date) — permet au "
             "digest email quotidien de savoir s'il a déjà tourné aujourd'hui et de rattraper une "
             "exécution manquée sans jamais en envoyer deux (section 10.9)."],
        ])

    add_h2(doc, "4.4 Accès depuis le backend")
    add_body(doc,
        "backend/db.py centralise l'unique point de connexion : un pool "
        "(DBUtils PooledDB, 2 à 10 connexions) créé de façon paresseuse — importer les "
        "modules backend ne nécessite donc pas que MySQL soit déjà démarré, ce qui "
        "permet à la suite de tests de s'exécuter sans base de données réelle.")

    # --- Pipeline détaillé ---
    add_h1(doc, "5. Pipeline requête → réponse (backend/main.py)")
    add_body(doc, "L'endpoint POST /dashboard orchestre l'ensemble :")
    add_numbered(doc, "appelle parse_user_query(query, previous_intent) — jamais de session serveur, "
                       "le frontend renvoie le dernier intent résolu à chaque nouvelle question.")
    add_numbered(doc, "si l'intention est une conversation générale (salutation, hors sujet) ou "
                       "reste ambiguë, renvoie directement le message de clarification, sans requête SQL.")
    add_numbered(doc, "sinon, exécute build_and_execute_query(intent), puis choisit le format de "
                       "réponse (table brute, carte KPI, ou graphique Vega-Lite).")
    add_numbered(doc, "pour un graphique, un hash de l'intention sert de clé de cache "
                       "(table generated_dashboards) pour éviter de régénérer une spec déjà connue.")
    add_numbered(doc, "chaque requête est aussi journalisée (table dashboard_requests) à des fins "
                       "d'historique.")

    # --- LLM ---
    add_h1(doc, "6. Compréhension du langage naturel")
    add_h2(doc, "6.1 Deux chemins : parseur rapide vs LLM")
    add_body(doc,
        "try_rule_based_parse() (intent_refiner.py) reconnaît par mots-clés fixes les "
        "cas simples (practice, statut, métrique, dimension). Il n'est utilisé que "
        "s'il n'y a pas de contexte de conversation précédent, et seulement après "
        "passage par _augment_rule_based_result(), qui refuse de lui faire confiance "
        "dès qu'une comparaison ou plusieurs pays sont mentionnés (retour à None → "
        "bascule vers le LLM). Dans tous les autres cas, l'appel Gemini (llm.py) prend "
        "le relais, avec le contexte multi-tour injecté dans le prompt système.")
    add_h2(doc, "6.2 Validation stricte — DashboardIntent (Pydantic)")
    add_body(doc,
        "La sortie JSON du LLM est chargée dans un modèle Pydantic dont le "
        "field_validator sur `filters` rejette toute clé absente de VALID_FILTERS. "
        "Toute erreur de validation renvoie un message de clarification à "
        "l'utilisateur — jamais un objet partiellement rempli avec des valeurs par "
        "défaut devinées.")
    add_h2(doc, "6.3 Résolution des valeurs de filtre — _fuzzy_match()")
    add_body(doc, "Ordre de résolution, dans cet ordre strict :")
    add_numbered(doc, "correspondance exacte dans la liste des valeurs connues ;")
    add_numbered(doc, "alias métier explicite (ex. « gagné » → « Offre gagnée ») ;")
    add_numbered(doc, "sous-chaîne bidirectionnelle ;")
    add_numbered(doc, "correspondance approchée via difflib (seuil 0.72).")
    add_body(doc,
        "Si rien ne correspond avec confiance, IntentUnclear est levée et remonte "
        "comme demande de clarification nommant explicitement la valeur non reconnue "
        "— jamais un filtre silencieusement ignoré ou remplacé.")
    add_h2(doc, "6.4 Dates relatives — calcul déterministe, jamais par le LLM")
    add_body(doc,
        "refine_intent() / _apply_relative_period() (intent_refiner.py) résolvent "
        "des expressions comme « ce mois-ci », « l'année dernière » ou « le trimestre "
        "dernier » par de l'arithmétique de date pure en Python (gestion des passages "
        "d'année incluse). Le prompt système interdit explicitement au LLM de deviner "
        "un calcul de date incertain — un choix qui élimine une classe entière "
        "d'erreurs plausibles-mais-fausses.")

    # --- SQL ---
    add_h1(doc, "7. Couche SQL sécurisée")
    add_body(doc,
        "schema_and_whitelist.py est la source unique de vérité : ALLOWED_TABLES "
        "définit les tables/vues et leurs colonnes autorisées ; VALID_METRICS, "
        "VALID_DIMENSIONS, VALID_FILTERS bornent ce que le LLM peut produire. "
        "db_layer.py traduit l'intention validée en requête SQL paramétrée (jamais "
        "de concaténation de valeurs utilisateur dans la chaîne SQL).")
    add_bullet(doc, "Chaque dimension a une vue pré-agrégée dédiée (ex. v_by_country) ; à "
                     "défaut, bascule sur un GROUP BY à la volée sur la table opportunities.")
    add_bullet(doc, "Un filtre à valeurs multiples (comparaison) devient une clause SQL IN (...).")
    add_bullet(doc, "Les filtres numériques (range_filters) supportent <, >, <=, >=, =, et between.")
    add_bullet(doc, "Si une vue ne contient pas la métrique demandée, bascule automatique et "
                     "cohérente vers un calcul groupé sur la table brute plutôt qu'une erreur.")

    # --- Vega ---
    add_h1(doc, "8. Génération des graphiques (Vega-Lite)")
    add_h2(doc, "8.1 Bar / pie / line — règles communes")
    add_bullet(doc, "Un camembert de plus de 6 segments bascule automatiquement en barres "
                     "horizontales (lisibilité) — MAX_PIE_SLICES / MAX_BAR_CATEGORIES.")
    add_bullet(doc, "Pour sum/count, la traîne au-delà du seuil est regroupée dans « Autres » ; "
                     "pour avg (ex. win_probability), simple troncature — une moyenne de moyennes "
                     "n'aurait pas de sens statistique.")
    add_bullet(doc, "Palette catégorielle fixe et validée (contraste daltonisme) pour les "
                     "camemberts, distincte de la teinte de marque (ACCENT) utilisée pour les "
                     "graphiques à série unique (barres/courbes) — séparation volontaire pour ne "
                     "pas perturber la validation CVD de la première en retintant pour le branding.")
    add_bullet(doc, "Les valeurs KPI NULL (win_probability/weighted_amount, ~47% des lignes) "
                     "restent None côté Python et s'affichent « N/A » — jamais silencieusement "
                     "converties en 0.")

    add_h2(doc, "8.2 Quatre types supplémentaires (funnel, scatter, heatmap, area)")
    add_body(doc,
        "Ajoutés après une relecture du skill de data-visualisation (choix de forme par "
        "le job de la donnée, palette validée par un script, specs de marks) pour donner "
        "plus de façons de raconter la même donnée commerciale sans sortir du cadre "
        "CVD-safe déjà en place.")
    add_bullet(doc, "Entonnoir (funnel) : dimension forcée à « status » (backend/intent_refiner.py), "
                     "réordonné selon l'ordre réel du pipeline (FUNNEL_STAGE_ORDER) — jamais trié "
                     "par valeur, qui donnerait un entonnoir qui ne raconte rien. Les statuts de "
                     "sortie (perdu, NO GO, infructueux…) sont exclus : ce sont des sorties du "
                     "pipeline, pas des étapes séquentielles. Géométrie symétrique (x_start/x_end "
                     "centrés sur 0) précalculée en Python — Vega-Lite ne sait pas produire un "
                     "entonnoir nativement. Rampe de bleus ordinale (une teinte par étape).")
    add_bullet(doc, "Nuage de points (scatter) : budget × probabilité de gain, taille = montant "
                     "pondéré, couleur = practice. Practice a exactement 3 valeurs fixes — sous le "
                     "plafond de 3 séries que le skill impose aux formes « toutes paires » "
                     "(scatter/bubble) pour rester lisible en vision daltonienne.")
    add_bullet(doc, "Carte de chaleur (heatmap) : n'importe quelle dimension croisée avec practice, "
                     "plafonnée aux 15 valeurs les plus fortes (MAX_HEATMAP_ROWS) pour rester lisible "
                     "— rampe séquentielle (un seul hue, clair → foncé), jamais une palette "
                     "catégorielle sur un encodage de magnitude.")
    add_bullet(doc, "Aire (area) : même donnée qu'une courbe, remplissage en dégradé pour plus "
                     "d'impact visuel — un principe du skill (« color comes last ») appliqué "
                     "littéralement : la forme est identique à « line », seul l'habillage change.")

    add_h2(doc, "8.3 Étude de cas — deux bugs texte/graphique trouvés en vérifiant en conditions réelles")
    add_body(doc,
        "Les tests automatisés valident la structure des données ; ils ne suffisent pas à "
        "garantir que le message texte affiché au-dessus d'un graphique décrit bien ce que "
        "ce graphique montre. Deux écarts réels ont été trouvés en interrogeant l'application "
        "en direct (pas seulement en pytest) :")
    add_bullet(doc, "Le texte de l'entonnoir décrivait les 19 statuts de la base (y compris "
                     "« Offre perdue ») alors que le graphique n'en affiche que 10 (les étapes du "
                     "pipeline). Corrigé en appliquant le même filtre de statuts au texte qu'au "
                     "graphique — jamais deux sources de vérité différentes pour la même réponse.")
    add_bullet(doc, "Le texte de la carte de chaleur annonçait 21 pays quand le graphique n'en "
                     "affiche que 15 (plafond de lisibilité). Même correction : le texte réutilise "
                     "désormais exactement la fonction de plafonnage du graphique.")
    add_body(doc,
        "Les deux sont couverts par un test de non-régression dédié — la leçon retenue : "
        "un test unitaire qui vérifie chaque brique séparément peut rester vert alors que "
        "l'assemblage final ment à l'utilisateur ; seule une vérification bout-en-bout, sur "
        "de vraies données, le révèle.")

    # --- Réponses texte ---
    add_h1(doc, "9. Réponses textuelles déterministes")
    add_body(doc,
        "response_builder.py calcule le message affiché à l'utilisateur directement "
        "depuis les données retournées par la requête SQL — jamais par le LLM. "
        "format_metric_value() applique les règles d'unité (budget en €, "
        "win_probability en % en multipliant par 100 car stocké en base comme "
        "fraction 0-1, nb_opportunities en entier). Cette séparation garantit que le "
        "texte affiché ne peut jamais diverger des chiffres réels du graphique.")

    # --- Alertes ---
    add_h1(doc, "10. Alertes deadlines")
    add_h2(doc, "10.1 Pourquoi ne pas se fier à la colonne days_remaining seule")
    add_body(doc,
        "days_remaining est une colonne figée au moment de l'import des données — "
        "elle ne diminue pas toute seule au fil des jours. get_upcoming_deadline_"
        "opportunities() (alerts.py) calcule donc la fenêtre « échéance ≤ 7 jours » "
        "en direct via DATEDIFF(deadline, CURDATE()) côté MySQL, jamais depuis cette "
        "colonne. En complément, maintenance.py::refresh_days_remaining() recalcule "
        "purement et simplement cette colonne chaque nuit (UPDATE ... SET "
        "days_remaining = DATEDIFF(deadline, CURDATE())), pour que sa valeur reste "
        "cohérente partout ailleurs dans l'application (tableaux, requêtes « urgentes "
        "< 7 jours » posées au chat).")
    add_h2(doc, "10.2 Pourquoi recalculer plutôt que décrémenter de 1 chaque jour")
    add_body(doc,
        "Un simple `days_remaining = days_remaining - 1` accumulerait une dérive "
        "silencieuse dès que le job est manqué un jour (serveur éteint, redémarrage) "
        "— l'écart resterait indéfiniment. Recalculer depuis la deadline réelle est "
        "idempotent et se corrige tout seul à la prochaine exécution, quel que soit "
        "le nombre de jours manqués entre-temps.")
    add_h2(doc, "10.3 Deux jobs planifiés (APScheduler, backend/main.py)")
    add_table(doc,
        ["Heure", "Job", "Rôle"],
        [
            ["00:05", "refresh_days_remaining", "Recalcule days_remaining pour toutes les opportunités."],
            ["08:00", "run_daily_alert_check", "Requête les opportunités actives à échéance ≤ 7 jours et "
             "envoie l'email récapitulatif si la liste n'est pas vide."],
        ])
    add_body(doc,
        "refresh_days_remaining() est aussi appelée une première fois au démarrage "
        "du serveur (lifespan), pour rattraper immédiatement une valeur restée figée "
        "depuis le dernier arrêt, sans attendre minuit.")
    add_h2(doc, "10.4 Envoi de l'email (Gmail SMTP)")
    add_body(doc,
        "send_alert_email() utilise smtplib avec STARTTLS sur smtp.gmail.com:587, "
        "authentifié par un mot de passe d'application Gmail (jamais le mot de passe "
        "principal du compte) — trois variables d'environnement dédiées "
        "(GMAIL_SENDER, GMAIL_APP_PASSWORD, ALERT_RECIPIENT_EMAIL), absentes du dépôt "
        "git. Le corps de l'email liste chaque opportunité avec son urgence, son "
        "client, son statut et son budget.")
    add_h2(doc, "10.5 Exclusion des statuts clos")
    add_body(doc,
        "EXCLUDED_STATUSES filtre les opportunités déjà gagnées, perdues, signées, "
        "infructueuses, « NO GO », hors scope ou non shortlistées — une opportunité "
        "close ne doit plus jamais déclencher d'alerte, même si sa date d'échéance "
        "reste techniquement proche.")
    add_h2(doc, "10.6 Bandeau frontend (AlertBanner.jsx)")
    add_body(doc,
        "Le composant interroge GET /alerts/deadlines au montage (lecture live, "
        "indépendante du digest email quotidien — mêmes règles métier) et affiche un "
        "bandeau dépliable en haut du dashboard, avec un code couleur d'urgence "
        "(rouge ≤ 3 jours, orange 4-7 jours) réutilisant les jetons de statut déjà "
        "définis dans le design system de l'application.")

    add_h2(doc, "10.7 Bug trouvé : une échéance déjà passée dans une liste « urgente »")
    add_body(doc,
        "En testant la question « liste des opportunités urgentes (< 7 jours) », des "
        "opportunités dont l'échéance était dépassée depuis des mois apparaissaient dans "
        "les résultats. Cause : la traduction en filtre SQL était days_remaining < 7, "
        "et une deadline dépassée depuis 50 jours a days_remaining = -50, donc -50 < 7 "
        "est vrai — mathématiquement correct, sémantiquement faux : « urgent » sous-entend "
        "une échéance encore à venir.")
    add_body(doc,
        "Corrigé à trois niveaux plutôt qu'un seul, par prudence — le même principe de "
        "défense en profondeur que le reste de l'anti-hallucination du projet :")
    add_numbered(doc, "le chemin rapide par mots-clés (intent_refiner.py) produit désormais "
                       "{\"op\": \"between\", \"value\": [0, N]} au lieu de {\"op\": \"<\", \"value\": N} ;")
    add_numbered(doc, "l'exemple few-shot et une instruction explicite ont été ajoutés au prompt "
                       "système du LLM (llm.py) pour le même cas ;")
    add_numbered(doc, "un garde-fou déterministe dans refine_intent() normalise automatiquement "
                       "tout days_remaining avec un opérateur \"<\" ou \"<=\" en \"between\" à partir "
                       "de 0 — quelle que soit son origine (LLM ou règle), et même si les deux "
                       "premiers points étaient un jour contournés.")
    add_body(doc,
        "Le troisième niveau est le plus important pédagogiquement : une instruction de prompt "
        "n'est jamais une garantie (le LLM l'a déjà ignorée une fois pour le scatter, voir "
        "section 15), donc la correction réellement fiable est celle qui ne dépend pas du "
        "LLM pour se déclencher. Le tableau affiche aussi désormais « Échéance dépassée "
        "depuis N jours » plutôt qu'un nombre négatif brut, pour les cas où une deadline "
        "passée reste légitimement visible (ex: une liste non filtrée par date).")

    add_h2(doc, "10.8 Statuts clos exclus des requêtes « urgentes » du chat")
    add_body(doc,
        "Signalé par l'utilisateur : « liste des opportunités urgentes » pouvait afficher "
        "une offre déjà gagnée ou perdue si sa date d'échéance technique tombait dans la "
        "fenêtre demandée — incohérent avec les alertes email/bannière (section 10.5), qui "
        "excluent bien ces statuts. Plutôt que de dupliquer la liste EXCLUDED_STATUSES, "
        "intent_refiner.py::refine_intent() l'importe directement depuis alerts.py et pose "
        "intent[\"exclude_statuses\"] dès qu'un filtre days_remaining est présent — jamais "
        "piloté par le LLM, uniquement par ce garde-fou déterministe. db_layer.py traduit "
        "ce champ en une clause status NOT IN (...), ajoutée à toute requête qui filtre sur "
        "l'urgence. Une seule définition de « actif » pour tout le projet, jamais deux "
        "listes de statuts qui pourraient diverger avec le temps.")

    add_h2(doc, "10.9 Rattrapage du scheduler")
    add_body(doc,
        "APScheduler ne rattrape pas un job manqué si le processus était entièrement arrêté "
        "au moment prévu (contrairement à misfire_grace_time, qui ne couvre qu'un léger "
        "retard sur un processus resté actif). Pour le recalcul de days_remaining, ce n'était "
        "pas un problème : il est déjà rappelé sans condition à chaque démarrage (section "
        "10.2), et le recalculer plusieurs fois ne fait jamais de mal. Pour l'email "
        "quotidien, un rappel sans condition renverrait un doublon si le cron 8h avait déjà "
        "tourné le jour même.")
    add_body(doc,
        "Solution : une table scheduler_state (job_name, last_run_date), auto-créée à la "
        "demande — aucune migration à relancer sur un déploiement existant. "
        "run_daily_alert_check_if_needed() vérifie d'abord si le job a déjà tourné "
        "aujourd'hui ; sinon, elle exécute la vérification puis marque la date. Appelée à "
        "la fois par le cron 8h ET au démarrage du serveur : un serveur éteint pile à 8h "
        "rattrape l'envoi dès qu'il redémarre, quelle que soit l'heure, sans jamais "
        "produire de second email le même jour.")

    # --- Google Sheets ---
    add_h1(doc, "11. Synchronisation Google Sheets -> MySQL")
    add_body(doc,
        "backend/sheets_sync.py. Le Sheet devient un formulaire d'ajout/modification "
        "d'opportunités, plus simple à éditer au quotidien qu'une base de données "
        "directement — l'application continue de LIRE depuis MySQL comme avant (chat, "
        "graphiques, alertes) ; ce module importe uniquement les changements du Sheet "
        "vers la base, jamais l'inverse.")

    add_h2(doc, "11.1 Authentification par compte de service, pas une simple clé API")
    add_body(doc,
        "La synchro doit pouvoir ÉCRIRE dans le Sheet (réinjecter l'id MySQL généré pour "
        "chaque nouvelle ligne, condition de son idempotence — voir 11.3), ce qu'une clé "
        "API seule ne permet pas (lecture seule). Authentification par compte de service "
        "Google (fichier JSON, ajouté en Éditeur sur le Sheet cible) via "
        "gspread.service_account().")

    add_h2(doc, "11.2 Champs toujours recalculés, jamais lus depuis le Sheet")
    add_body(doc,
        "deadline_month, deadline_year, days_remaining et weighted_amount sont toujours "
        "dérivés des colonnes brutes (deadline, financial_offer, win_probability) au "
        "moment de la synchro, même s'ils figurent en colonne dans le Sheet — même "
        "principe que days_remaining ailleurs dans le projet (section 10.1) : une donnée "
        "calculable ne doit jamais dépendre d'une saisie externe qui pourrait diverger.")

    add_h2(doc, "11.3 Idempotence de l'insertion — réécriture de l'id dans le Sheet")
    add_body(doc,
        "Une ligne sans id = nouvelle opportunité. Après l'INSERT MySQL, l'id généré "
        "(cur.lastrowid) est immédiatement réécrit dans la cellule id du Sheet — sans "
        "quoi la synchro suivante (15 minutes plus tard) réinsérerait la même ligne en "
        "double, faute de moyen de la reconnaître comme déjà traitée. Si cette "
        "réécriture échoue (ligne insérée mais Sheet non mis à jour), l'erreur est "
        "journalisée bruyamment plutôt que silencieusement absorbée — l'insertion "
        "MySQL, elle, reste acquise.")

    add_h2(doc, "11.4 Validation par ligne, jamais bloquante")
    add_body(doc,
        "Chaque ligne est validée indépendamment (dates aux deux formats acceptés, "
        "nombres avec virgule décimale, probabilité en fraction ou en pourcentage, "
        "practice/opp_type/status contre la liste blanche déjà utilisée par le chat) — "
        "une ligne invalide est journalisée et sautée, sans jamais empêcher l'import des "
        "autres. Les littéraux \"NULL\"/\"N/A\" laissés par l'export CSV -> Sheets sont "
        "normalisés en valeur vide plutôt que stockés tels quels comme texte.")

    add_h2(doc, "11.5 Bug trouvé en conditions réelles — cursor.rowcount ne veut pas dire ce qu'on croit")
    add_body(doc,
        "Premier test en direct (pas seulement avec des mocks) : la synchro rapportait "
        "1 ligne mise à jour et 359 ignorées pour « id introuvable », alors que ces ids "
        "existaient bel et bien en base. Cause : la détection « id existant vs nouveau » "
        "se fiait à cursor.rowcount après un UPDATE — or PyMySQL (sans CLIENT_FOUND_ROWS) "
        "renvoie le nombre de lignes réellement MODIFIÉES, pas trouvées. Le Sheet étant un "
        "export frais de la base, la quasi-totalité des UPDATE ne changeaient aucune "
        "valeur, donc rowcount valait 0 même sur un id existant. Corrigé en préchargeant "
        "une fois l'ensemble des ids existants (SELECT id FROM opportunities) plutôt que "
        "de déduire l'existence du résultat de l'UPDATE. Vérifié après correction : 348 "
        "lignes mises à jour, 12 sautées à raison — révélant un vrai problème de qualité "
        "de données préexistant (des valeurs opp_type comme \"DP\"/\"AMI\" saisies par "
        "erreur dans la colonne status).")

    add_h2(doc, "11.6 Décision volontaire : pas de suppression automatique")
    add_body(doc,
        "Retirer une ligne du Sheet ne supprime jamais l'opportunité correspondante en "
        "base. Une synchro automatique et non surveillée, qui tourne indéfiniment toutes "
        "les 15 minutes, est le mauvais endroit pour une opération destructive et "
        "irréversible : une lecture partielle, un mauvais onglet ou un Sheet vidé par "
        "erreur pourrait effacer de vraies données sans que personne ne le voie venir "
        "avant le prochain passage. Ajout et modification seulement — un choix de "
        "prudence assumé plutôt qu'un oubli.")

    add_h2(doc, "11.7 Optimisation — mettre en cache la résolution du Sheet, pas seulement le client")
    add_body(doc,
        "Profilage demandé après coup, pour vérifier l'absence de régression de "
        "performance : le coût réel n'était pas les écritures MySQL (360 UPDATE "
        "séquentiels mesurés à 0.032s au total) mais open_by_key() + worksheet(), deux "
        "allers-retours réseau vers l'API Google Sheets (1.6s mesurés à eux deux) — "
        "rejoués à chaque appel de sync_sheet_to_mysql() alors que le client gspread "
        "authentifié, lui, était déjà mis en cache. Corrigé en mettant aussi en cache "
        "l'objet Worksheet résolu : un appel répété passe de 1.6s à 0s, et une synchro "
        "complète de ~1.1s à ~0.4s une fois le cache chaud — un gain qui se répète "
        "indéfiniment, toutes les 15 minutes. Les trois tâches de démarrage (recalcul "
        "days_remaining, vérification d'alerte, synchro Sheets) bloquaient aussi le "
        "démarrage du serveur (exécutées avant que FastAPI n'accepte une seule requête "
        "HTTP, dans lifespan()) ; elles tournent désormais comme jobs « une fois "
        "immédiatement » sur le thread du scheduler, sans retarder la disponibilité du "
        "serveur.")

    add_h2(doc, "11.8 Déclenchement")
    add_body(doc,
        "Trois déclencheurs : toutes les 15 minutes (APScheduler, job "
        "sheets_sync_periodic), une fois au démarrage du serveur, et à la demande via "
        "POST /sheets/sync — utile pour forcer un import sans attendre le prochain "
        "cycle.")

    # --- Frontend ---
    add_h1(doc, "12. Frontend (Vite + React)")
    add_bullet(doc, "Composants principaux : ChatPanel, DashboardPanel, AlertBanner, VegaChart, "
                     "DataTable, StatTile, ThemeToggle, DevoteamLogo.")
    add_bullet(doc, "Hooks dédiés : useTheme (clair/sombre), useChatHistory (persistance "
                     "localStorage), useVegaEmbed (rendu Vega-Lite dans le DOM).")
    add_bullet(doc, "Thème géré par variables CSS (custom properties) — le mode sombre est "
                     "SÉLECTIONNÉ avec ses propres valeurs, pas un simple filtre inversé "
                     "automatique.")
    add_bullet(doc, "Jetons de marque (--brand-primary…) volontairement séparés des jetons "
                     "de sécurité des graphiques (--series-1…8) pour ne jamais mélanger "
                     "esthétique et lisibilité daltonisme.")
    add_bullet(doc, "Astuce React : un compteur dashboardKey, incrémenté à chaque nouvelle "
                     "réponse, est utilisé comme prop key pour forcer le remontage des "
                     "composants et rejouer les animations d'entrée à chaque nouveau résultat.")

    add_h2(doc, "12.1 Historique de conversation persistant (useChatHistory.js)")
    add_body(doc,
        "Messages, dashboard affiché et contexte multi-tour (previous_intent) sont "
        "sérialisés dans localStorage à chaque changement, et restaurés au montage — "
        "plafonnés à 100 messages pour ne pas faire grossir indéfiniment le stockage. Le "
        "compteur d'identifiants de message (nextIdRef) est réinitialisé au-delà du plus "
        "grand id restauré, pour ne jamais entrer en collision avec l'historique repris. "
        "Toute erreur (quota dépassé, navigation privée, JSON corrompu) est absorbée "
        "silencieusement : la persistance est un confort, jamais une dépendance dont "
        "l'absence casserait le chat. Un bouton « Effacer la conversation » (avec "
        "confirmation) a été ajouté dans le header, puisqu'un historique qui persiste "
        "indéfiniment a besoin d'une porte de sortie explicite.")

    add_h2(doc, "12.2 Bug trouvé : header illisible en mode sombre")
    add_body(doc,
        "Trouvé en relisant le CSS (pas en testant à l'œil — aucun outil de capture "
        "d'écran disponible dans cet environnement) : le dégradé du header utilisait "
        "linear-gradient(135deg, var(--brand-primary) 0%, var(--text-primary) 68%). "
        "--text-primary vaut #0b0b0b (presque noir) en mode clair, mais #ffffff (blanc) "
        "en mode sombre — et le texte du header, lui, est en blanc fixe (color: #ffffff). "
        "En mode sombre, le dégradé finissait donc en blanc, sous un texte blanc : "
        "illisible, tout comme le logo (lui aussi dessiné en blanc).")
    add_body(doc,
        "Corrigé avec un nouveau jeton --header-ink, fixé à #0b0b0b et jamais réactif au "
        "thème — le header porte toujours du texte blanc, donc la fin de son dégradé doit "
        "toujours rester sombre, quel que soit le thème actif. Un second bug de même "
        "nature affectait le texte « warning » du bandeau d'alerte "
        "(color-mix(..., black) littéral, qui suppose un fond clair) : corrigé avec un "
        "jeton --warning-ink-mix (black en mode clair, white en mode sombre). Aucune "
        "valeur n'a changé en mode clair dans les deux cas — uniquement des ajouts, "
        "jamais une modification du rendu déjà validé.")

    # --- Sécurité ---
    add_h1(doc, "13. Sécurité")
    add_bullet(doc, "Aucune injection SQL possible : le LLM ne produit jamais de SQL, "
                     "uniquement un JSON borné par une liste blanche, converti en requêtes "
                     "paramétrées.")
    add_bullet(doc, ".env (clés API, identifiants email) exclu du suivi git via .gitignore ; "
                     ".env.example documente les variables attendues sans valeurs réelles.")
    add_bullet(doc, "Le mot de passe d'application Gmail est distinct du mot de passe principal "
                     "du compte et révocable indépendamment.")
    add_bullet(doc, "credentials/ (clé de compte de service Google, section 11.1) est gitignoré "
                     "au niveau du dossier entier — jamais de fichier JSON de credentials commité, "
                     "quel que soit son nom.")

    # --- Tests ---
    add_h1(doc, "14. Tests automatisés")
    add_body(doc,
        "143 tests pytest, sans dépendance réseau ni base de données réelle : le client "
        "Gemini, les connexions MySQL et le client Google Sheets (gspread) sont simulés "
        "(monkeypatch) via de faux objets "
        "(fake cursor/connection capturant la requête générée pour l'affirmer dans le "
        "test). Complétés systématiquement par une vérification en conditions réelles "
        "(DB MySQL réelle, appel Gemini réel, et compilation par le vrai moteur vega-lite "
        "en Node.js) — les tests protègent contre les régressions, la vérification réelle "
        "est ce qui a révélé les deux bugs texte/graphique de la section 8.3.")
    add_table(doc,
        ["Fichier", "Tests", "Ce qu'il protège"],
        [
            ["test_intent_refiner.py", "37", "Dates relatives, parseur par mots-clés, affinage d'intention, "
             "normalisation funnel/heatmap/scatter/days_remaining/exclude_statuses."],
            ["test_vega_generator.py", "18", "Cardinalité des graphiques, palette, valeurs NULL, "
             "les 4 nouveaux types de graphiques."],
            ["test_llm_validation.py", "14", "Anti-hallucination : clarification plutôt que valeur devinée, "
             "résolution fuzzy des filtres, chemin rapide vs LLM."],
            ["test_response_builder.py", "13", "Formatage des unités, messages texte déterministes, "
             "cohérence texte/graphique pour funnel et heatmap."],
            ["test_db_layer.py", "13", "Construction des requêtes SQL, choix de vue, clauses IN/BETWEEN, "
             "requête 2D du heatmap, chemin brut du scatter, exclusion de statuts."],
            ["test_alerts.py", "12", "Fenêtre de 7 jours en direct, exclusion des statuts clos, envoi email, "
             "rattrapage idempotent du scheduler."],
            ["test_maintenance.py", "3", "Recalcul de days_remaining, résilience à une panne DB."],
            ["test_sheets_sync.py", "33", "Parsing/validation par ligne, littéraux NULL, insertion + "
             "réécriture d'id et des colonnes calculées, détection id existant/inconnu, ligne invalide "
             "sautée sans bloquer les autres, résilience à une panne de lecture du Sheet."],
        ])

    # --- Q&A entretien ---
    add_h1(doc, "15. Questions d'entretien probables")
    qa = [
        ("Pourquoi ne pas laisser le LLM écrire du SQL directement ?",
         "Parce qu'un LLM peut halluciner une colonne, une table ou une valeur inexistante. "
         "En le limitant à produire un JSON borné par une liste blanche stricte "
         "(schema_and_whitelist.py), toute requête SQL exécutée est garantie syntaxiquement "
         "et sémantiquement valide, quelle que soit la sortie du modèle."),
        ("Comment évitez-vous les hallucinations, concrètement ?",
         "Trois filets superposés : (1) Pydantic rejette toute clé de filtre hors liste "
         "blanche, (2) _fuzzy_match ne retourne jamais une valeur absente des données "
         "réelles — sinon IntentUnclear déclenche une clarification, (3) les dates relatives "
         "sont calculées par arithmétique Python déterministe, jamais devinées par le LLM."),
        ("Pourquoi MySQL plutôt que SQLite comme prévu dans le brief initial ?",
         "Accès concurrent plus robuste pour un backend multi-requêtes, support natif de "
         "vues pré-agrégées par dimension, et un pool de connexions dédié — le schéma reste "
         "simple, donc la complexité ajoutée reste faible face au bénéfice."),
        ("Comment gérez-vous le contexte multi-tour sans session serveur ?",
         "Le frontend renvoie le dernier intent résolu (previous_intent) à chaque nouvelle "
         "question. Dès qu'un contexte est présent, le parseur rapide est systématiquement "
         "court-circuité au profit du LLM, à qui ce contexte est injecté dans le prompt "
         "système pour qu'il décide d'hériter ou non des paramètres précédents."),
        ("Pourquoi recalculer days_remaining plutôt que le décrémenter de 1 chaque jour ?",
         "Un décrément accumule une dérive silencieuse si un jour est manqué (serveur "
         "éteint). Recalculer depuis DATEDIFF(deadline, CURDATE()) est idempotent : le "
         "résultat est toujours correct, peu importe combien de jours se sont écoulés "
         "depuis la dernière exécution."),
        ("Que se passe-t-il si le LLM renvoie un JSON malformé ou un schéma invalide ?",
         "json.JSONDecodeError et pydantic.ValidationError sont interceptées explicitement "
         "et transformées en message de clarification pour l'utilisateur — jamais une "
         "exception non gérée ni une réponse partiellement remplie."),
        ("Comment le système empêche-t-il un graphique illisible (trop de catégories) ?",
         "MAX_PIE_SLICES (6) et MAX_BAR_CATEGORIES (12) : au-delà, un camembert bascule "
         "en barres horizontales, et la traîne est regroupée dans « Autres » pour les "
         "agrégations sum/count (jamais pour une moyenne, qui n'aurait pas de sens agrégée)."),
        ("Une instruction de prompt suffit-elle à garantir un comportement du LLM ?",
         "Non — observé concrètement : une question de corrélation était systématiquement "
         "interprétée comme un simple KPI malgré un exemple few-shot explicite, parce que "
         "le parseur rapide (mots-clés, avant même l'appel LLM) l'interceptait avec une "
         "confiance mal placée. Corrigé en élargissant la détection de mots-clés — la leçon : "
         "diagnostiquer d'abord QUEL composant a décidé avant de corriger le prompt, le "
         "problème n'est pas toujours là où on l'imagine."),
        ("Pourquoi corriger le bug days_remaining à trois endroits différents ?",
         "Défense en profondeur, le même principe que l'anti-hallucination générale du "
         "projet : le chemin rapide et le prompt LLM sont corrigés pour ne plus produire "
         "le bug, ET un garde-fou déterministe dans refine_intent() normalise le résultat "
         "quelle que soit son origine — utile si jamais les deux premiers correctifs sont "
         "un jour contournés par une reformulation imprévue."),
        ("Comment garantis-tu qu'un email d'alerte n'est jamais envoyé deux fois le même jour ?",
         "Une table scheduler_state (job_name, last_run_date) trace la dernière exécution. "
         "run_daily_alert_check_if_needed() vérifie cette date avant d'agir, et la met à "
         "jour après — appelée à la fois par le cron 8h et au démarrage du serveur, donc "
         "un redémarrage tardif rattrape l'envoi manqué sans risquer un doublon si le cron "
         "avait déjà tourné plus tôt dans la journée."),
        ("Comment as-tu trouvé les bugs de contraste en mode sombre sans navigateur ni capture d'écran ?",
         "En lisant le CSS ligne par ligne plutôt qu'en devinant : chercher chaque endroit "
         "où une couleur qui change avec le thème (var(--text-primary), un color-mix vers "
         "un noir/blanc littéral) est combinée avec une couleur de texte fixe. Le header "
         "avait un texte blanc fixe sur un dégradé qui finissait par --text-primary — "
         "blanc lui aussi en mode sombre. Un raisonnement statique suffit à repérer ce "
         "type de bug ; il n'a fallu aucun rendu réel pour le localiser, seulement pour le "
         "confirmer visuellement ensuite."),
        ("Pourquoi ne pas synchroniser aussi les suppressions (Sheet -> base) ?",
         "Choix de prudence délibéré, pas un oubli : la synchro tourne toutes les 15 "
         "minutes sans supervision humaine. Une suppression automatique y est le pire "
         "endroit possible pour une opération destructive et irréversible — une lecture "
         "partielle, un mauvais onglet ou un Sheet vidé par erreur effacerait de vraies "
         "données avant que quiconque ne le remarque. Le risque a été explicitement "
         "évalué avec le porteur du projet, qui a choisi de garantir seulement l'ajout et "
         "la modification plutôt que la fonctionnalité complète."),
        ("Un test avec des mocks peut-il garantir qu'une intégration externe (Google Sheets, MySQL) "
         "fonctionne réellement ?",
         "Non — exemple concret rencontré sur ce projet : tous les tests mockés de la "
         "synchro Sheets passaient, mais le premier essai en conditions réelles rapportait "
         "359 lignes sur 360 comme « id introuvable » alors qu'elles existaient toutes en "
         "base. La cause (cursor.rowcount qui compte les lignes modifiées, pas trouvées) "
         "n'était visible qu'avec de vraies données où la plupart des UPDATE ne changent "
         "rien. Les mocks avaient simulé le comportement qu'on attendait de rowcount, pas "
         "son vrai comportement — la leçon : les mocks valident la logique connue, seule "
         "une vérification en conditions réelles révèle ce qu'on n'avait pas anticipé."),
    ]
    for question, answer in qa:
        add_h3(doc, "Q : " + question)
        add_body(doc, answer)

    # --- Limites ---
    add_h1(doc, "16. Limites connues")
    add_bullet(doc, "Google Gemini (fournisseur actuel depuis la migration forcée, section 2.2) "
                     "supporte en fait les sorties structurées strictes (vérifié empiriquement), "
                     "mais l'app garde volontairement l'architecture JSON libre héritée de Groq "
                     "— le filet de sécurité Pydantic + liste blanche reste donc le mécanisme "
                     "d'application des règles, plutôt qu'une garantie au niveau du schéma du "
                     "modèle. Adopter le mode strict resterait une amélioration possible.")
    add_bullet(doc, "L'historique de conversation persistant (localStorage) est par "
                     "navigateur/appareil, pas partagé entre postes — nécessiterait un compte "
                     "utilisateur pour ça.")
    add_bullet(doc, "Le nuage de points et la carte de chaleur n'ont pas de garde-fou de "
                     "cardinalité aussi mûr que bar/pie pour des cas extrêmes (dimension à très "
                     "forte cardinalité en axe du heatmap au-delà du plafond testé).")
    add_bullet(doc, "La synchro Google Sheets ne détecte pas les suppressions (section 11.6, "
                     "choix délibéré) et retraite chaque ligne à chaque passage plutôt que de "
                     "ne toucher que les lignes changées — sans impact réel à l'échelle actuelle "
                     "(360 lignes/15 min), mais à reconsidérer si le Sheet grossissait beaucoup.")
    add_bullet(doc, "12 opportunités en base ont un status invalide, présent avant même la "
                     "synchro Sheets et jamais détecté faute de validation stricte à l'écriture "
                     "d'origine (section 11.5) — à corriger manuellement ou à ajouter à la liste "
                     "blanche si ce sont des statuts légitimes.")

    out_path = os.path.join(DOC_DIR, "Guide_Technique_DevoTeam_Dashboard.docx")
    doc.save(out_path)
    return out_path


# ---------- Document 3 : script de présentation orale ----------

def build_presentation_script():
    doc = new_document()
    add_cover(
        doc,
        "Notes de présentation",
        "DevoTeam Dashboard",
        "Script pour une présentation orale — à lire, pas à distribuer",
    )

    add_h1(doc, "Accroche")
    add_cue(doc, "[Ton confiant, ne pas se presser — laisser la phrase respirer]")
    add_body(doc,
        "Je vais vous présenter DevoTeam Dashboard. En une phrase : c'est un tableau de "
        "bord commercial à qui on parle en français, et qui répond avec le bon graphique — "
        "pas de menu à chercher, pas de SQL à écrire, pas de formation à prévoir.")
    add_body(doc,
        "L'idée de départ tient en une ligne : « montre-moi le budget par pays pour Risk "
        "Advisory », et une seconde plus tard, le graphique est là, à l'écran, à côté du "
        "chat.")

    add_h1(doc, "Le problème que ça résout")
    add_body(doc,
        "Les équipes commerciales suivent des centaines d'opportunités — budgets, pays, "
        "statuts, échéances. Deux frictions reviennent tout le temps : il faut un outil BI "
        "ou des requêtes SQL pour croiser ces données, et une échéance qui approche peut "
        "passer inaperçue si personne ne pense à consulter le dashboard ce jour-là. Ce "
        "projet attaque les deux en même temps : l'accès aux données devient conversationnel, "
        "et le système prévient tout seul quand une échéance approche.")

    add_h1(doc, "Ce qui va vous surprendre : huit façons de voir les mêmes données")
    add_cue(doc, "[Montrer le chat à l'écran — poser une vraie question en direct si possible]")
    add_body(doc,
        "Barres, courbes, aires, camemberts, cartes KPI, tableaux — jusque-là, classique. "
        "Mais j'ai aussi construit un entonnoir de vente, qui montre visuellement où les "
        "deals se perdent dans le pipeline commercial, et un nuage de points qui croise le "
        "budget avec la probabilité de gain pour révéler une vraie corrélation : "
        "est-ce que les gros budgets ont statistiquement plus de chances d'être gagnés ? "
        "Ce sont des types de graphiques qu'on ne trouve pas dans un dashboard interne "
        "standard, et le système choisit tout seul lequel utiliser selon la question posée.")
    add_body(doc,
        "Le chat comprend aussi le contexte : je peux demander « et pour Data Management ? » "
        "juste après une première question, et il comprend que je veux le même graphique, "
        "juste filtré différemment. Il comprend aussi les dates relatives — « ce mois-ci », "
        "« le trimestre dernier » — et les comparaisons — « compare la France et le Maroc ».")

    add_h1(doc, "Ce qu'on ne voit pas : pourquoi on peut lui faire confiance")
    add_body(doc,
        "C'est le point sur lequel j'ai le plus travaillé, et c'est invisible à l'écran. "
        "Un assistant qui invente un chiffre plausible mais faux, c'est pire qu'un assistant "
        "qui ne répond pas — surtout sur des données commerciales. Alors la règle absolue "
        "du projet, c'est : jamais deviner. Si le système n'est pas sûr de ce qu'on lui "
        "demande, il pose une question de clarification, plutôt que d'afficher un résultat "
        "séduisant mais inventé.")
    add_body(doc,
        "Concrètement, ça veut dire que le modèle de langage ne touche jamais directement "
        "la base de données. Il produit uniquement une intention structurée, entièrement "
        "validée contre une liste blanche de colonnes et de valeurs réelles avant qu'une "
        "seule requête SQL soit construite. Et cette architecture est vérifiée par cent "
        "tests automatisés, qui tournent sans base de données réelle ni connexion internet.")

    add_h1(doc, "Une fonctionnalité que personne ne m'a demandée")
    add_body(doc,
        "Au-delà du périmètre initial, j'ai ajouté un système d'alertes deadlines : chaque "
        "jour, l'application envoie automatiquement un email récapitulant les opportunités "
        "dont l'échéance approche, et affiche la même liste dans un bandeau du dashboard. "
        "Et j'ai poussé le soin du détail jusqu'à gérer le cas où le serveur serait éteint "
        "pile à l'heure prévue : au redémarrage, le système vérifie tout seul s'il a manqué "
        "l'envoi du jour et le rattrape, sans jamais envoyer le même email deux fois.")

    add_h1(doc, "Des bugs trouvés en testant pour de vrai, pas juste en croisant les doigts")
    add_cue(doc, "[C'est la partie qui montre la rigueur — ne pas la survoler]")
    add_body(doc,
        "Les tests automatisés, c'est nécessaire, mais ça ne suffit pas. J'ai trouvé un vrai "
        "bug en utilisant l'application moi-même : demander la liste des « opportunités "
        "urgentes » remontait des deadlines dépassées depuis des mois, parce que "
        "mathématiquement, moins sept jours est bien inférieur à sept jours — juste que ça "
        "n'a aucun sens métier. Je l'ai corrigé à trois niveaux différents plutôt qu'un "
        "seul, par prudence : le raisonnement, c'est qu'une instruction donnée à un modèle "
        "de langage n'est jamais une garantie à cent pour cent, donc la correction qui "
        "compte vraiment est celle qui ne dépend pas du modèle pour s'appliquer.")
    add_body(doc,
        "Même logique pour deux graphiques : le texte qui accompagnait l'entonnoir de vente "
        "et la carte de chaleur décrivait plus de données que ce que le graphique affichait "
        "réellement à l'écran. Des tests unitaires bien écrits n'auraient jamais attrapé ça "
        "— il a fallu utiliser l'application comme un vrai utilisateur pour le voir.")

    add_h1(doc, "Le soin du détail")
    add_body(doc,
        "L'interface reprend les couleurs et le logo Devoteam, avec un mode sombre "
        "entièrement lisible — et pas juste esthétique : j'ai trouvé et corrigé deux bugs "
        "de contraste où le texte devenait quasiment invisible en mode sombre, en relisant "
        "le CSS ligne par ligne plutôt qu'en devinant. Et pour que ce soit simple à lancer "
        "au quotidien, j'ai construit un raccourci bureau en un clic qui démarre MySQL, le "
        "serveur et l'interface, puis ouvre directement la page.")

    add_h1(doc, "Les chiffres à retenir")
    add_bullet(doc, "8 types de graphiques choisis automatiquement selon la question posée.")
    add_bullet(doc, "100 tests automatisés, aucune dépendance à une base de données réelle.")
    add_bullet(doc, "15 phases de développement livrées, de bout en bout, en autonomie.")
    add_bullet(doc, "0 hallucination tolérée : donnée non fiable = question posée en retour, jamais un chiffre inventé.")

    add_h1(doc, "Pour conclure")
    add_cue(doc, "[Marquer une pause avant cette dernière phrase]")
    add_body(doc,
        "Ce projet, c'est un dashboard qu'on peut vraiment donner à une équipe commerciale "
        "sans formation, avec la rigueur d'ingénierie qui garantit que ce qu'il affiche est "
        "juste — et deux documents détaillés, un rapport et un guide technique, pour qui "
        "veut aller plus loin. Je suis disponible pour une démonstration en direct, ou pour "
        "répondre à vos questions dès maintenant.")

    out_path = os.path.join(DOC_DIR, "Script_Presentation_DevoTeam_Dashboard.docx")
    doc.save(out_path)
    return out_path


if __name__ == "__main__":
    p1 = build_rapport_professionnel()
    p2 = build_guide_technique()
    p3 = build_presentation_script()
    print("Généré :", p1)
    print("Généré :", p2)
    print("Généré :", p3)
