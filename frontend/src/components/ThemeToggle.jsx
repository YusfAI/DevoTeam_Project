export default function ThemeToggle({ theme, onToggle }) {
  return (
    <button
      className="theme-toggle"
      onClick={onToggle}
      title="Changer de thème"
      aria-label="Changer de thème"
      type="button"
    >
      {theme === 'dark' ? '☀️' : '🌙'}
    </button>
  )
}
