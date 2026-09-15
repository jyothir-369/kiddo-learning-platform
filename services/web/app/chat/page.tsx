"use client";

import { useState } from "react";

// Stream-by-reference player: the video URL is always the original source
// (Wikimedia, NASA, ...) — never a proxied/local byte copy (guide §6.9).
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type VideoSuggestion = {
  id: string;
  title: string;
  reason?: string;
};

type ChatResponse = {
  assistant_name: string;
  answer: string;
  video_url: string | null;
  video: { id: string; title: string; attribution?: string; license?: string; duration_s?: number } | null;
  suggested_videos: VideoSuggestion[];
  tutorial: { id: string; title: string; step: number; total_steps: number } | null;
  safety: { verdict: string; flag?: string };
};

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<ChatResponse | null>(null);

  async function ask(text: string) {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, age: 8 }),
      });
      if (!res.ok) {
        const detail = (await res.json().catch(() => null))?.detail;
        throw new Error(detail || `Request failed (${res.status})`);
      }
      const data = (await res.json()) as ChatResponse;
      setResponse(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function playSuggestion(s: VideoSuggestion) {
    await ask(`tell me about ${s.title}`);
  }

  const styles = {
    page: {
      fontFamily: "'Segoe UI', system-ui, sans-serif",
      maxWidth: "900px",
      margin: "0 auto",
      padding: "1rem",
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column" as const,
      background: "#f8fafc",
    },
    header: {
      display: "flex",
      alignItems: "center",
      gap: "0.5rem",
      padding: "0.75rem 0",
    },
    logo: { fontSize: "2rem" },
    title: { fontSize: "1.5rem", fontWeight: 600 as const, color: "#0f172a" },
    card: {
      backgroundColor: "#ffffff",
      borderRadius: "16px",
      boxShadow: "0 2px 8px rgba(15, 23, 42, 0.08)",
      padding: "1.25rem",
      marginBottom: "1rem",
    },
    video: {
      width: "100%",
      maxHeight: "420px",
      borderRadius: "12px",
      backgroundColor: "#0f172a",
    },
    attribution: {
      fontSize: "0.8rem",
      color: "#64748b",
      marginTop: "0.5rem",
    },
    answer: {
      fontSize: "1.05rem",
      lineHeight: "1.6",
      color: "#1e293b",
      whiteSpace: "pre-wrap",
    },
    chips: {
      display: "flex",
      flexWrap: "wrap" as const,
      gap: "0.5rem",
      marginTop: "0.75rem",
    },
    chip: {
      border: "2px solid #22c55e",
      backgroundColor: "#f0fdf4",
      color: "#15803d",
      borderRadius: "9999px",
      padding: "0.4rem 0.9rem",
      fontSize: "0.95rem",
      cursor: "pointer",
      transition: "background-color 0.15s",
    },
    inputBar: {
      display: "flex",
      gap: "0.5rem",
      marginTop: "auto",
      padding: "0.75rem 0",
    },
    input: {
      flex: 1,
      padding: "0.9rem 1rem",
      borderRadius: "9999px",
      border: "2px solid #cbd5e1",
      fontSize: "1.05rem",
      outline: "none",
    },
    send: {
      backgroundColor: "#22c55e",
      color: "#ffffff",
      border: "none",
      borderRadius: "9999px",
      padding: "0 1.25rem",
      fontSize: "1rem",
      fontWeight: 600 as const,
      cursor: "pointer",
    },
    error: { color: "#dc2626", marginTop: "0.5rem" },
    hint: { color: "#94a3b8", fontSize: "0.85rem", marginTop: "0.5rem", textAlign: "center" as const },
  };

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <span style={styles.logo}>🎈</span>
        <h1 style={styles.title}>Kiddo Assist</h1>
      </header>

      {error && <div style={styles.error}>⚠️ {error}</div>}

      {loading && (
        <div style={{ ...styles.card, textAlign: "center", color: "#64748b" }}>
          Kiddo Assist is thinking… ⏳
        </div>
      )}

      {response && !loading && (
        <>
          {/* Video player — plays on this platform, stream-by-reference */}
          {response.video_url && response.video && (
            <div style={styles.card}>
              <video
                controls
                autoPlay
                style={styles.video}
                src={response.video_url}
                poster={undefined}
              >
                Your browser doesn&apos;t support video playback.
              </video>
              <p style={styles.attribution}>
                🎬 {response.video.title} · {response.video.attribution}{" "}
                {response.video.license && <>· {response.video.license}</>}
              </p>
            </div>
          )}

          {/* Kiddo Assist's spoken/written explanation */}
          <div style={styles.card}>
            <div style={styles.answer}>💬 {response.answer}</div>

            {/* Suggestion chips — tap to play another best video */}
            {response.suggested_videos.length > 0 && (
              <>
                <div style={{ ...styles.chips, marginTop: "1rem" }}>
                  {response.suggested_videos.map((s) => (
                    <button key={s.id} style={styles.chip} onClick={() => playSuggestion(s)}>
                      ▶ {s.title}
                    </button>
                  ))}
                </div>
                <p style={styles.hint}>Tap a suggestion to play more!</p>
              </>
            )}
          </div>
        </>
      )}

      {!response && !loading && !error && (
        <div style={styles.card}>
          <div style={styles.answer}>
            Hi! I&apos;m Kiddo Assist 🎈 Ask me anything — like
            &quot;why is the sky blue?&quot;
          </div>
        </div>
      )}

      {/* Type box (mic arrives in Iteration 8) */}
      <div style={styles.inputBar}>
        <input
          style={styles.input}
          placeholder="Ask me something…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !loading) {
              ask(input);
              setInput("");
            }
          }}
        />
        <button
          style={styles.send}
          disabled={loading}
          onClick={() => {
            ask(input);
            setInput("");
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}