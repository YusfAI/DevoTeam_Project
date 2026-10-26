import { useEffect, useRef } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Link2, Trash2 } from 'lucide-react'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import HistoryPanel from './HistoryPanel'
import TypingIndicator from './TypingIndicator'
import ThemeToggle from './ThemeToggle'
import DevoteamLogo from './DevoteamLogo'
import { BoutonIcone } from './ui/Infobulle'

// Les questions d'amorce arrivent l'une après l'autre, d'un mouvement bref : elles
// se lisent comme une liste qu'on découvre plutôt qu'un bloc posé d'un coup.
const SUGGESTIONS_CONTENEUR = {
  visible: { transition: { staggerChildren: 0.04 } },
}
const SUGGESTION_ENTREE = {
  hidden: { opacity: 0, y: 6 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.2 } },
}

// Questions d'amorce : un chat vide ne dit pas ce qu'on peut lui demander. Chacune
// exerce une capacité différente (filtre, comparaison, pipeline, urgence), pour que
// l'utilisateur découvre l'étendue de l'outil en cliquant plutôt qu'en devinant.
// Elles disparaissent dès la première réponse : passé ce point, c'est la phrase
// tapée qui pilote le tableau de bord, pas des boutons.
// Les trois premières sont celles que la direction pose réellement, dans l'ordre où
// elle les pose : le volume déposé et son issue, puis la répartition par practice,
// puis la période. Elles ouvrent la liste parce que ce sont elles qu'on cherche.
const SUGGESTIONS = [
  'Sur le total des offres remises, combien gagnées, perdues, et en attente ?',
  'Quelle est la répartition par practice ?',
  "Combien d'offres a-t-on remis entre novembre 2025 et à date actuelle ?",
  'Budget par pays pour Risk Advisory',
  'Compare le budget entre la France et le Maroc',
  "Montre-moi l'entonnoir de vente",
  'Liste des opportunités urgentes (< 7 jours)',
]

export default function ChatPanel({
  messages, loading, onSubmit, theme, onToggleTheme, onClearHistory, onOpenLinkSheet,
  inputRef, onOpenDashboard, history, currentDashboardName,
  historyOpen, onCloseHistory,
}) {
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, loading])

  function handleOpenFromHistory(name, question) {
    onOpenDashboard(name, question)
    onCloseHistory()
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <div className="chat-header-brand">
          <DevoteamLogo size={36} glow />
          <div>
            <h1>DevoTeam Assistant</h1>
            <p className="tagline">Dashboard commercial</p>
          </div>
        </div>
        <div className="chat-header-actions">
          {/* Choisir la feuille Google lue par l'application — sans invite de
              commandes. La relecture manuelle qu'occupait ce bouton (🔄) est dans
              « Santé des données », avec le détail de ce qu'elle a lu. */}
          <BoutonIcone icone={Link2} libelle="Lier une feuille Google" onClick={onOpenLinkSheet} />
          <BoutonIcone icone={Trash2} libelle="Effacer la conversation" onClick={onClearHistory} />
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      </div>

      {/* La zone de saisie est en tête de panneau : c'est le point de départ de
          chaque interaction, et elle ne doit pas se déplacer avec la conversation ni
          demander de faire défiler pour être atteinte. C'est aussi le SEUL moyen de
          modifier le tableau de bord affiché — décrire le changement en toutes
          lettres plutôt que le choisir dans une liste de retouches préparées. */}
      <div className="chat-composer">
        <ChatInput inputRef={inputRef} loading={loading} onSubmit={onSubmit} />
      </div>

      {/* `aria-live` ici, et pas seulement sur le pourcentage de zoom : un lecteur
          d'écran n'annonçait jamais la réponse de l'assistant, alors qu'il annonçait
          « 110 % » à chaque clic de zoom. La priorité était exactement inversée.
          `polite` plutôt que `assertive` : la réponse ne doit pas couper l'utilisateur
          en train de taper. */}
      <div className="chat-messages" role="log" aria-live="polite" aria-relevant="additions">
        <AnimatePresence initial={false}>
          {messages.map((m) => (
            <ChatMessage
              key={m.id}
              type={m.type}
              text={m.text}
              dashboardName={m.dashboardName}
              question={m.question}
              onOpenDashboard={onOpenDashboard}
            />
          ))}
        </AnimatePresence>

        {/* Affichées tant que la conversation n'a produit aucune réponse : une fois
            l'utilisateur lancé, elles n'ont plus lieu d'être et laissent la place. */}
        {!loading && history.length === 0 && (
          <motion.div
            className="chat-suggestions"
            variants={SUGGESTIONS_CONTENEUR}
            initial="hidden"
            animate="visible"
          >
            <span className="chat-suggestions-label">Essayez :</span>
            {SUGGESTIONS.map((q) => (
              <motion.button
                key={q}
                type="button"
                className="chat-suggestion"
                variants={SUGGESTION_ENTREE}
                onClick={() => onSubmit(q)}
              >
                {q}
              </motion.button>
            ))}
          </motion.div>
        )}

        {loading && <TypingIndicator />}
        <div ref={endRef} />
      </div>

      <AnimatePresence>
        {historyOpen && (
          <HistoryPanel
            key="historique"
            history={history}
            currentName={currentDashboardName}
            onOpen={handleOpenFromHistory}
            onClose={onCloseHistory}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
