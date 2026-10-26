import * as Tooltip from '@radix-ui/react-tooltip'

// Infobulle (Radix Tooltip) à la place de l'attribut `title` du navigateur : elle
// s'affiche aussi au clavier (focus), reprend la charte de l'application et ne
// met pas une seconde à apparaître. Le Provider est posé une fois, dans App.jsx.
export function Infobulle({ texte, children, cote = 'bottom' }) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content className="ui-tooltip" side={cote} sideOffset={6} collisionPadding={8}>
          {texte}
          <Tooltip.Arrow className="ui-tooltip-arrow" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  )
}

// Un bouton réduit à son icône. Le libellé n'est pas facultatif : il sert à la
// fois d'infobulle et de nom accessible — sans lui, un lecteur d'écran
// n'annoncerait qu'« bouton ».
export function BoutonIcone({ icone: Icone, libelle, className = 'theme-toggle', taille = 17, ...props }) {
  return (
    <Infobulle texte={libelle}>
      <button type="button" className={className} aria-label={libelle} {...props}>
        <Icone size={taille} strokeWidth={2} aria-hidden="true" />
      </button>
    </Infobulle>
  )
}
