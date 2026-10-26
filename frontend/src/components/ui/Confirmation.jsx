import * as AlertDialog from '@radix-ui/react-alert-dialog'

// Demande de confirmation (Radix AlertDialog) à la place de `window.confirm` : la
// boîte grise du navigateur jurait avec l'application et ne disait pas ce qui
// allait être perdu. Celle-ci garde le focus, se ferme par Échap, et place le
// focus sur « Annuler » — une action destructive ne doit pas être celle qu'un
// Entrée trop rapide déclenche.
export default function Confirmation({ ouvert, onOuvertChange, titre, description, action, onConfirmer }) {
  return (
    <AlertDialog.Root open={ouvert} onOpenChange={onOuvertChange}>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="ui-overlay" />
        <AlertDialog.Content className="ui-confirm">
          <AlertDialog.Title className="ui-confirm-title">{titre}</AlertDialog.Title>
          <AlertDialog.Description className="ui-confirm-text">{description}</AlertDialog.Description>
          <div className="ui-confirm-actions">
            <AlertDialog.Cancel asChild>
              <button type="button" className="data-button">Annuler</button>
            </AlertDialog.Cancel>
            <AlertDialog.Action asChild>
              <button type="button" className="data-button data-button-danger" onClick={onConfirmer}>
                {action}
              </button>
            </AlertDialog.Action>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  )
}
