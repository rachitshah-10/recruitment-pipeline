import { useEffect, useRef, useState } from 'react'
import { MessageCircle, Send, X } from 'lucide-react'

const WELCOME = {
  from: 'bot',
  text: 'Hi! Ask me about hiring, revenue, bench, contracts, clients, training, or a person by name.',
}

const STARTERS = ['How is the pipeline?', 'What is our monthly revenue?', 'Who is on the bench?', 'What should leadership do?']

export default function Chatbot() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([WELCOME])
  const [suggestions, setSuggestions] = useState(STARTERS)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

  async function send(text) {
    const message = text.trim()
    if (!message || busy) return
    setInput('')
    setMessages((current) => [...current, { from: 'user', text: message }])
    setBusy(true)
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      })
      if (!response.ok) throw new Error(`Request failed (${response.status})`)
      const json = await response.json()
      setMessages((current) => [...current, { from: 'bot', text: json.reply }])
      setSuggestions(json.suggestions || [])
    } catch (err) {
      setMessages((current) => [...current, { from: 'bot', text: `I couldn't reach the operations API. ${err.message}.` }])
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open assistant"
        className="fixed bottom-5 right-5 z-50 flex items-center gap-2 rounded-full bg-ink text-white px-4 py-3 shadow-lg hover:bg-ink/90"
      >
        <MessageCircle className="w-5 h-5" />
        <span className="text-sm font-medium">Ask</span>
      </button>
    )
  }

  return (
    <section className="fixed bottom-5 right-5 z-50 w-[min(380px,calc(100vw-2.5rem))] h-[min(560px,calc(100vh-2.5rem))] flex flex-col bg-card border border-line rounded-lg shadow-xl">
      <header className="flex items-center justify-between px-4 py-3 border-b border-line bg-ink text-white rounded-t-lg">
        <div>
          <p className="text-sm font-semibold">Operations assistant</p>
          <p className="text-[11px] text-white/55">Answers from live dashboard data</p>
        </div>
        <button type="button" onClick={() => setOpen(false)} aria-label="Close assistant" className="text-white/70 hover:text-white">
          <X className="w-4 h-4" />
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
        {messages.map((message, index) => (
          <div key={index} className={`flex ${message.from === 'user' ? 'justify-end' : 'justify-start'}`}>
            <p
              className={`max-w-[85%] whitespace-pre-line rounded-lg px-3 py-2 text-sm leading-snug ${
                message.from === 'user' ? 'bg-moss text-white' : 'bg-paper text-ink border border-line'
              }`}
            >
              {message.text}
            </p>
          </div>
        ))}
        {busy ? <p className="text-xs text-ink/50 px-1">Thinking…</p> : null}
        <div ref={endRef} />
      </div>

      {suggestions.length ? (
        <div className="flex flex-wrap gap-1.5 px-3 pb-2">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => send(suggestion)}
              disabled={busy}
              className="rounded-full border border-line px-2.5 py-1 text-xs text-ink/70 hover:text-ink hover:border-moss disabled:opacity-50"
            >
              {suggestion}
            </button>
          ))}
        </div>
      ) : null}

      <form
        onSubmit={(event) => {
          event.preventDefault()
          send(input)
        }}
        className="flex items-center gap-2 border-t border-line px-3 py-2.5"
      >
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask a question…"
          className="flex-1 bg-transparent text-sm outline-none placeholder:text-ink/40"
        />
        <button type="submit" disabled={busy || !input.trim()} aria-label="Send" className="text-moss disabled:text-ink/30">
          <Send className="w-4 h-4" />
        </button>
      </form>
    </section>
  )
}
