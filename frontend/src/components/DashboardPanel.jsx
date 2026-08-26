import { useEffect, useRef, useState } from 'react'
import { OVERVIEW_DASHBOARD_NAME, dacDashboardUrl } from '../dac'
import { getHealth } from '../api'
import DevoteamLogo from './DevoteamLogo'

// Durée du fondu entre deux états du tableau de bord. Doit rester égale à la
// transition d'opacité de .dac-frame : l'ancien cadre n'est retiré qu'une fois le
// nouveau complètement opaque, sinon le fond apparaîtrait entre les deux.
const FONDU_MS = 320

export default function DashboardPanel({
  dashboard, dashboardKey, historyOpen, onToggleHistory,
}) {
  // UN SEUL tableau de bord affiché. Il montre la vue d'ensemble tant qu'aucune
  // question n'a été posée, puis ce que les questions en ont fait. Il n'y a plus de
  // bascule entre deux pages : le prompt modifie ce tableau de bord, il n'en ouvre
  // pas un second à côté.
  const currentName = dashboard?.dac_dashboard || OVERVIEW_DASHBOARD_NAME
  const frameUrl = dacDashboardUrl(currentName)

  // État du serveur de dashboards. null = vérification en cours ; false = injoignable,
  // auquel cas on affiche une consigne au lieu d'une iframe vide et muette — une
  // panne de DAC était jusqu'ici indiscernable d'une absence de données.
  const [dacStatus, setDacStatus] = useState(null)
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
  const token = `${currentName}::${dashboardKey}`
  const [frames, setFrames] = useState(() => [{ token, src: frameUrl }])
  const [ready, setReady] = useState({})
  const timers = useRef([])

  useEffect(() => {
    setFrames((prev) => {
      if (prev.some((f) => f.token === token)) return prev
      // Au plus deux : le cadre affiché et le nouveau. Si une troisième demande
      // arrive pendant un chargement, elle remplace celui qui n'est pas encore visible.
      return [prev[0], { token, src: frameUrl }]
    })
  }, [token, frameUrl])

  useEffect(() => () => timers.current.forEach(window.clearTimeout), [])

  function handleLoad(chargé) {
    setReady((prev) => ({ ...prev, [chargé]: true }))
    const timer = window.setTimeout(() => {
      setFrames((prev) => (prev.length > 1 ? prev.filter((f) => f.token === chargé) : prev))
      // Sans ce ménage, la table des cadres prêts grossirait à chaque question.
      setReady((prev) => (prev[chargé] ? { [chargé]: true } : prev))
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
  const title = surLaVueDEnsemble ? 'Vue d’ensemble commerciale' : dashboard?.goal || 'Analyse'
  let subtitle
  if (surLaVueDEnsemble) {
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
