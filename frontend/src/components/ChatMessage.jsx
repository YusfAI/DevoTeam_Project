export default function ChatMessage({ type, text }) {
  return <div className={`message ${type}`}>{text}</div>
}
