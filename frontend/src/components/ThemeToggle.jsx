import { AnimatePresence, motion } from 'motion/react'
import { Moon, Sun } from 'lucide-react'
import { Infobulle } from './ui/Infobulle'

export default function ThemeToggle({ theme, onToggle }) {
  const sombre = theme === 'dark'
  // Le libellé dit ce que fait le clic, pas l'état actuel : « Changer de thème »
  // ne disait pas vers lequel.
  const libelle = sombre ? 'Passer en mode clair' : 'Passer en mode sombre'
  return (
    <Infobulle texte={libelle}>
      <button className="theme-toggle" onClick={onToggle} aria-label={libelle} type="button">
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={theme}
            className="icon-swap"
            initial={{ rotate: -90, opacity: 0, scale: 0.6 }}
            animate={{ rotate: 0, opacity: 1, scale: 1 }}
            exit={{ rotate: 90, opacity: 0, scale: 0.6 }}
            transition={{ duration: 0.18 }}
          >
            {sombre ? <Sun size={17} aria-hidden="true" /> : <Moon size={17} aria-hidden="true" />}
          </motion.span>
        </AnimatePresence>
      </button>
    </Infobulle>
  )
}
