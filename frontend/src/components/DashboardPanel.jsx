import { useEffect, useRef, useState } from 'react'
import {
  DAC_DARK_BASE_URL, DATA_QUALITY_DASHBOARD_NAME, OVERVIEW_DASHBOARD_NAME, SECTIONS,
  dacDashboardUrl, estUneSection,
} from '../dac'
import { getHealth } from '../api'
import DevoteamLogo from './DevoteamLogo'

// Durée du fondu entre deux états du tableau de bord. Doit rester égale à la
// transition d'opacité de .dac-frame : l'ancien cadre n'est retiré qu'une fois le
// nouveau complètement opaque, sinon le fond apparaîtrait entre les deux.
const FONDU_MS = 320

// Paliers de zoom du tableau de bord. DAC n'expose aucun jeton de typographie — son
// bundle ne lit que onze variables `--dac-*` et huit teintes, aucune taille de texte —
// donc agrandir la police depuis le thème est impossible. Zoomer le cadre produit le
// même effet, et le choix revient à qui regarde l'écran.
const ZOOMS = [0.9, 1, 1.1, 1.25, 1.4]
const ZOOM_STORAGE = 'devoteam-dashboard-zoom'

function zoomInitial() {
  try {
    const enregistre = Number(window.localStorage.getItem(ZOOM_STORAGE))
    return ZOOMS.includes(enregistre) ? enregistre : 1
  } catch {
    // Navigation privée ou stockage indisponible : le zoom par défaut suffit.
    return 1
  }
}

export default function DashboardPanel({
  dashboard, dashboardKey, historyOpen, onToggleHistory, onOpenSection, theme,
}) {
  // UN SEUL tableau de bord affiché. Il montre la vue d'ensemble tant qu'aucune
  // question n'a été posée, puis ce que les questions en ont fait. Il n'y a plus de
  // bascule entre deux pages : le prompt modifie ce tableau de bord, il n'en ouvre
  // pas un second à côté.
  const currentName = dashboard?.dac_dashboard || OVERVIEW_DASHBOARD_NAME

  // État du serveur de dashboards. null = vérification en cours ; false = injoignable,
  // auquel cas on affiche une consigne au lieu d'une iframe vide et muette — une
  // panne de DAC était jusqu'ici indiscernable d'une absence de données.
  const [zoom, setZoom] = useState(zoomInitial)
  useEffect(() => {
    try {
      window.localStorage.setItem(ZOOM_STORAGE, String(zoom))
    } catch {
      // Le réglage est un confort, pas une garantie.
    }
  }, [zoom])

  function decalerZoom(pas) {
    setZoom((actuel) => {
      const index = ZOOMS.indexOf(actuel)
      return ZOOMS[Math.min(ZOOMS.length - 1, Math.max(0, index + pas))]
    })
  }

  const [dacStatus, setDacStatus] = useState(null)

  // Le mode sombre du tableau de bord passe par un SECOND serveur DAC : un thème DAC
  // est figé au lancement du processus, il n'y a rien à basculer dans le fichier.
  // Tant qu'on ne sait pas s'il tourne, on garde le serveur clair — mieux vaut un
  // tableau de bord dans le mauvais thème qu'un cadre vide le temps de la sonde.
  const racineSombre = dacStatus?.sombre_url || null
  // L'origine des tableaux de bord vient du backend, pas du bundle : derrière un
  // tunnel ou un reverse proxy, l'adresse à donner au navigateur n'est pas celle que
  // le serveur emploie pour lui-même. `undefined` laisse dac.js retomber sur la
  // valeur de compilation, qui reste la bonne en usage local.
  const racineClaire = dacStatus?.url || undefined
  const racine = theme === 'dark' && racineSombre ? racineSombre : racineClaire
  const frameUrl = dacDashboardUrl(currentName, dashboard?.dac_filters, racine)
  useEffect(() => {
    let cancelled = false
    getHealth()
      .then((h) => { if (!cancelled) setDacStatus(h.dac) })
      .catch(() => { if (!cancelled) setDacStatus({ ok: false, aide: 'Le serveur ne répond pas.' }) })
    return () => { cancelled = true }
  }, [dashboardKey])

  // --- Fondu enchaîné entre deux états ------------------------------------
  //
  // Recharger l'iframe en place la vidait le temps du chargement : l'écran passait
  // au blanc à chaque question. On garde donc DEUX cadres au maximum — celui qu'on
  // regarde, et le suivant qui charge par-dessus, invisible. Quand il est prêt il
  // devient opaque, puis seulement après le fondu l'ancien est retiré. À aucun
  // instant l'utilisateur ne voit du vide.
  //
  // Le jeton inclut dashboardKey : reposer la même question régénère le tableau de
  // bord sans changer son nom, l'URL seule ne suffirait donc pas à détecter qu'un
  // nouveau chargement commence.
  // Les filtres entrent dans le jeton : deux questions peuvent viser la MÊME page
  // avec deux practices différentes, et le cadre doit alors se recharger.
  const token = `${frameUrl}::${dashboardKey}`
  const [frames, setFrames] = useState([])
  const [ready, setReady] = useState({})
  const timers = useRef([])

  useEffect(() => {
    // Tant que /health n'a pas répondu, on ne sait pas quelle origine employer.
    // Charger un cadre en attendant viserait, derrière un tunnel, le 127.0.0.1 du
    // visiteur : une erreur de navigateur bien visible, corrigée une seconde plus
    // tard — le squelette dit la même chose sans faire peur.
    if (dacStatus === null) return
    setFrames((prev) => {
      if (prev.some((f) => f.token === token)) return prev
      // Au plus deux : le cadre affiché et le nouveau. Si une troisième demande
      // arrive pendant un chargement, elle remplace celui qui n'est pas encore visible.
      return prev.length ? [prev[0], { token, src: frameUrl }] : [{ token, src: frameUrl }]
    })
  }, [token, frameUrl, dacStatus])

  useEffect(() => () => timers.current.forEach(window.clearTimeout), [])

  function handleLoad(chargé) {
    setReady((prev) => ({ ...prev, [chargé]: true }))
    const timer = window.setTimeout(() => {
      setFrames((prev) => {
        // Le cadre qui vient de charger est-il TOUJOURS à l'écran ? Une question
        // posée pendant le fondu l'a peut-être déjà remplacé. Sans cette
        // vérification, le filtre ne gardait alors plus rien : la liste se vidait et
        // l'utilisateur se retrouvait devant un panneau blanc, sans rien pour en
        // sortir sinon reposer une question.
        if (!prev.some((f) => f.token === chargé)) return prev
        return prev.length > 1 ? prev.filter((f) => f.token === chargé) : prev
      })
      // Sans ce ménage, la table des cadres prêts grossirait à chaque question.
      setReady((prev) => (prev[chargé] ? { [chargé]: true } : prev))
      // Le minuteur a fait son travail : le retirer évite que la liste enfle d'une
      // entrée morte à chaque question de la session.
      timers.current = timers.current.filter((t) => t !== timer)
    }, FONDU_MS)
    timers.current.push(timer)
  }

  // Le squelette ne sert qu'au tout premier affichage, quand il n'y a rien à montrer
  // en attendant (démarrage à froid du moteur de requête, une douzaine de secondes).
  // Les fois suivantes, le tableau de bord précédent tient ce rôle bien mieux.
  const rienDePret = !frames.some((f) => ready[f.token])
  const chargementEnCours = frames.length > 1

  const isReplay = Boolean(dashboard?.replay)
  const surLaVueDEnsemble = currentName === OVERVIEW_DASHBOARD_NAME
  // La vue d'ensemble sert à deux choses : le point de départ, et la RÉPONSE à une
  // question qu'elle traite déjà. Dans le second cas elle est filtrée comme demandé,
  // et lui laisser le sous-titre « posez une question » ferait croire qu'elle n'a
  // rien fait de la question qu'on vient justement de poser.
  const reutilisee = Boolean(dashboard?.reused_overview)
  // Le bouton de retour n'a de sens que si l'on en est parti. Sur la vue
  // d'ensemble elle-même, il ne ferait que recharger la page affichée.
  const peutRevenir = currentName !== OVERVIEW_DASHBOARD_NAME
  const title = surLaVueDEnsemble && !reutilisee
    ? 'Vue d’ensemble commerciale'
    : dashboard?.goal || 'Vue d’ensemble commerciale'
  let subtitle
  if (reutilisee) {
    subtitle = 'Cette section répond déjà à votre question — filtrée comme demandé'
  } else if (surLaVueDEnsemble) {
    subtitle = 'Point de départ — posez une question pour le transformer'
  } else if (isReplay) {
    subtitle = 'Analyse enregistrée — figée telle qu’elle était lors de cette question'
  } else {
    subtitle = 'Modifié par vos questions — mêmes filtres sur tous les widgets'
  }

  return (
    <div className="dashboard-panel">
      <div className="dashboard-header">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        <div className="dashboard-header-actions">
          {/* La sortie de secours de l'écran. Une question mène ailleurs — une autre
              section, une analyse composée — et rien n'indiquait comment revenir au
              point de départ : il fallait reposer une question pour y retourner.
              Placé en tête des actions et seul à porter la couleur de marque, il se
              distingue des commandes discrètes qui l'entourent. */}
          {peutRevenir && (
            <button
              type="button"
              className="back-to-overview"
              onClick={() => onOpenSection(OVERVIEW_DASHBOARD_NAME)}
              title="Revenir au tableau de bord principal"
            >
              ← Tableau de bord principal
            </button>
          )}
          {/* DAC ne permet pas d'agrandir la police de ses graphiques ; zoomer le
              cadre revient au même et laisse le réglage à qui lit l'écran. */}
          <div className="zoom-control" role="group" aria-label="Taille d’affichage">
            <button
              type="button"
              onClick={() => decalerZoom(-1)}
              disabled={zoom === ZOOMS[0]}
              title="Réduire l’affichage"
              /* Le contenu visible est un signe « − » : un lecteur d'écran
                 l'annonce « moins », sans dire moins de quoi. Le libellé
                 accessible porte l'action, le title reste l'infobulle. */
              aria-label="Réduire l’affichage"
            >
              −
            </button>
            {/* `aria-live` annonce la nouvelle valeur après chaque clic ; le
                libellé dit CE QUE le nombre mesure, que rien d'autre n'indique. */}
            <span aria-live="polite" aria-label={`Taille d’affichage : ${Math.round(zoom * 100)} %`}>
              {Math.round(zoom * 100)} %
            </span>
            <button
              type="button"
              onClick={() => decalerZoom(1)}
              disabled={zoom === ZOOMS[ZOOMS.length - 1]}
              title="Agrandir l’affichage"
              aria-label="Agrandir l’affichage"
            >
              +
            </button>
          </div>
          {/* Ouvrir l'analyse dans son propre onglet. C'est ce qui permet de la
              GARDER : l'imprimer, l'enregistrer en PDF, la joindre à un mail. Un
              bouton d'export intégré n'était pas possible — le tableau de bord est
              servi par un autre port, donc une iframe d'origine différente, que le
              navigateur interdit de capturer et imprime en blanc. Dans son propre
              onglet, la page est de plein droit : Ctrl+P y fonctionne normalement. */}
          <a
            className="quality-link"
            href={frameUrl}
            target="_blank"
            rel="noreferrer"
            title="Ouvrir dans un onglet — pour imprimer ou enregistrer en PDF"
          >
            ⧉ Ouvrir en grand
          </a>
          {/* Ouvre le tableau de bord de qualité dans un onglet : il répond à une
              question ponctuelle (« sur quoi ce chiffre repose-t-il ? ») et n'a pas
              à remplacer l'analyse en cours dans le cadre. */}
          <a
            className="quality-link"
            href={dacDashboardUrl(DATA_QUALITY_DASHBOARD_NAME, null, racine)}
            target="_blank"
            rel="noreferrer"
            title="Ce que les données contiennent, et ce qui leur manque"
          >
            ⓘ Qualité des données
          </a>
          <button
            type="button"
            className={`history-button${historyOpen ? ' active' : ''}`}
            onClick={onToggleHistory}
            title="Historique des analyses"
            aria-expanded={historyOpen}
          >
            🕘 Historique
          </button>
        </div>
      </div>

      {/* Les onglets de section. La vue d'ensemble comptait douze rangées qu'il
          fallait parcourir au défilement en sachant où regarder ; elle est
          désormais découpée en cinq tableaux de bord, et une question peut ouvrir
          directement celui qui la traite. Les onglets disparaissent dès qu'une
          analyse composée est affichée : elle n'appartient à aucune section. */}
      {estUneSection(currentName) && (
        <nav className="dashboard-sections" aria-label="Sections du tableau de bord">
          {SECTIONS.map((s) => (
            <button
              key={s.nom}
              type="button"
              className={`section-tab${s.nom === currentName ? ' active' : ''}`}
              aria-current={s.nom === currentName ? 'page' : undefined}
              onClick={() => onOpenSection(s.nom)}
            >
              {s.onglet}
            </button>
          ))}
        </nav>
      )}

      <div className="dashboard-body align-top">
        {/* Le tableau de bord reste lisible pendant qu'il se met à jour : un fil
            d'attente en tête vaut mieux qu'un écran vidé, mais il faut tout de même
            dire que quelque chose est en train de se passer. */}
        {chargementEnCours && <div className="dashboard-progress" aria-hidden="true" />}

        {dacStatus && !dacStatus.ok ? (
          <div className="dashboard-unavailable">
            <DevoteamLogo size={56} className="placeholder-mark" />
            <h3>Serveur de dashboards injoignable</h3>
            <p>{dacStatus.aide}</p>
            <button type="button" onClick={() => window.location.reload()}>
              Réessayer
            </button>
          </div>
        ) : (
          <>
            {rienDePret && (
              <div className="dac-skeleton" aria-hidden="true">
                <div className="dac-skeleton-row">
                  <span /><span /><span /><span />
                </div>
                <div className="dac-skeleton-row tall">
                  <span /><span />
                </div>
                <div className="dac-skeleton-caption">Préparation du tableau de bord…</div>
              </div>
            )}
            {frames.map((frame) => (
              <iframe
                key={frame.token}
                className={`dac-frame${ready[frame.token] ? '' : ' loading'}`}
                // La largeur et la hauteur compensent le zoom : sans elles, le cadre
                // grandirait avec son contenu et déborderait de son conteneur. Ainsi
                // seule la taille du RENDU change, pas celle du bloc.
                style={{ zoom, width: `${100 / zoom}%`, height: `${100 / zoom}%` }}
                src={frame.src}
                title={currentName}
                onLoad={() => handleLoad(frame.token)}
              />
            ))}
          </>
        )}
      </div>
    </div>
  )
}
