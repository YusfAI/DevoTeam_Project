export default function ChatInput({ inputRef, loading, onSubmit }) {
  function handleSubmit(e) {
    e.preventDefault()
    const value = inputRef.current.value.trim()
    if (!value) return
    onSubmit(value)
    inputRef.current.value = ''
  }

  return (
    <form className="chat-form" onSubmit={handleSubmit}>
      <input
        ref={inputRef}
        type="text"
        placeholder="Posez votre question..."
        required
        autoComplete="off"
        disabled={loading}
      />
      <button type="submit" disabled={loading}>Envoyer</button>
    </form>
  )
}
