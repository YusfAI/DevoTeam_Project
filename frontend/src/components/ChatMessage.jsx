import { motion } from 'motion/react'
import { ArrowUpRight } from 'lucide-react'

// Chaque message entre par un léger glissement vers le haut : l'œil suit ce qui
// vient d'arriver sans que la conversation saute. Les messages déjà présents au
// chargement de la page n'en ont pas (AnimatePresence initial={false}, ChatPanel).
const ENTREE = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.22, ease: 'easeOut' },
}

export default function ChatMessage({ type, text, dashboardName, question, onOpenDashboard }) {
  // Une réponse qui a produit un dashboard devient cliquable : sans ça, seul le
  // dernier résultat restait accessible et les analyses précédentes étaient perdues.
  const replayable = Boolean(dashboardName && onOpenDashboard)

  if (!replayable) {
    return <motion.div className={`message ${type}`} {...ENTREE}>{text}</motion.div>
  }

  return (
    <motion.div className={`message ${type} replayable`} {...ENTREE}>
      {text}
      <button
        type="button"
        className="message-replay"
        onClick={() => onOpenDashboard(dashboardName, question)}
        title="Réafficher ce tableau de bord"
      >
        <ArrowUpRight size={14} aria-hidden="true" />
        Revoir ce tableau de bord
      </button>
    </motion.div>
  )
}
