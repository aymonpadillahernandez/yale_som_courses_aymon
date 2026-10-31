import { useEffect, useRef, useState } from "react";
import { sendChat } from "../api";

interface Turn {
  role: "user" | "agent";
  text: string;
  tools?: string[];
  failed?: boolean;
}

const TOOL_LABELS: Record<string, string> = {
  search_courses: "searched the catalog",
  web_search: "searched the web",
};

const SUGGESTIONS = [
  "Which SOM electives meet on Tuesday?",
  "Machine learning courses outside SOM",
  "Climate courses at the School of the Environment",
];

export default function ChatPanel() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const log = logRef.current;
    if (log) {
      log.scrollTop = log.scrollHeight;
    }
  }, [turns, busy]);

  async function ask(question: string) {
    const trimmed = question.trim();
    if (!trimmed) {
      setError("Type a question first.");
      return;
    }
    setError("");
    setDraft("");
    setTurns((prev) => [...prev, { role: "user", text: trimmed }]);
    setBusy(true);
    try {
      const data = await sendChat(trimmed);
      setTurns((prev) => [
        ...prev,
        { role: "agent", text: data.reply, tools: data.tools_used },
      ]);
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      setTurns((prev) => [
        ...prev,
        {
          role: "agent",
          text: `Could not reach the agent (${detail}). Is uvicorn running on port 8000?`,
          failed: true,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="chat" aria-label="Course assistant">
      <header className="chat-head">
        <h2>Course assistant</h2>
        <p>Asks the catalog first, the web only when it has to.</p>
      </header>

      <div className="chat-log" ref={logRef}>
        {turns.length === 0 && !busy && (
          <div className="chat-empty">
            <p>Ask about courses in any Yale school, their faculty or meeting times.</p>
            <ul>
              {SUGGESTIONS.map((s) => (
                <li key={s}>
                  <button type="button" className="chip-button" onClick={() => ask(s)}>
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {turns.map((turn, i) => (
          <div key={i} className={`turn turn-${turn.role}`}>
            <p className={turn.failed ? "bubble bubble-failed" : "bubble"}>{turn.text}</p>
            {turn.role === "agent" && turn.tools && turn.tools.length > 0 && (
              <ul className="tools">
                {turn.tools.map((tool) => (
                  <li key={tool} className="tool-chip">
                    {TOOL_LABELS[tool] ?? tool}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}

        {busy && (
          <div className="turn turn-agent">
            <p className="bubble thinking" role="status">
              <span>Thinking</span>
              <span className="dots" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
            </p>
          </div>
        )}
      </div>

      <form
        className="chat-form"
        onSubmit={(event) => {
          event.preventDefault();
          ask(draft);
        }}
      >
        <label className="sr-only" htmlFor="chat-input">
          Ask the course assistant
        </label>
        <input
          id="chat-input"
          value={draft}
          placeholder="Which AI courses meet on Wednesday?"
          onChange={(event) => {
            setDraft(event.target.value);
            if (error) setError("");
          }}
          disabled={busy}
        />
        <button type="submit" disabled={busy}>
          Ask
        </button>
      </form>
      {error && <p className="chat-error">{error}</p>}
    </section>
  );
}
