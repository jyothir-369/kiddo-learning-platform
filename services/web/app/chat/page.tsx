"use client";

import { useEffect, useRef, useState } from "react";

// Stream-by-reference player: the video URL is always the original source
// (Wikimedia, NASA, ...) — never a proxied/local byte copy (guide §6.9).
// audio_url is our own endpoint, so it is prefixed with API_URL.
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function fullAudioUrl(p: string) {
  return p.startsWith("http") ? p : `${API_URL}${p}`;
}

type VideoSuggestion = {
  id: string;
  title: string;
  reason?: string;
};

type ChatResponse = {
  assistant_name: string;
  answer: string;
  audio_url: string | null;
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
  const [responses, setResponses] = useState<ChatResponse[]>([]);
  // Speaks Kiddo's line once the turn renders (Iteration 5).
  const audioCtxRef = useRef<AudioContext | null>(null);
  const spokenRef = useRef<string | null>(null);
  const [learnerName, setLearnerName] = useState<string | null>(null);
  const [introPlayed, setIntroPlayed] = useState(false);
  const [recording, setRecording] = useState(false);

  useEffect(() => {
    // On mount fetch profile for learner (demo uses fixed id) — never nags; just reads.
    fetch(`${API_URL}/api/profile/demo-learner-01`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d && d.name) setLearnerName(d.name);
      })
      .catch(() => {});
  }, []);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const [speakBlocked, setSpeakBlocked] = useState(false);
  const [streak, setStreak] = useState<number>(0);
  const [badges, setBadges] = useState<string[]>([]);

  useEffect(() => {
    fetch(`${API_URL}/api/play/streak/demo-learner-01`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setStreak(d.current || 0); })
      .catch(() => {});
    fetch(`${API_URL}/api/play/badges/demo-learner-01`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setBadges(d.badges || []); })
      .catch(() => {});
  }, []);

  // Play the spoken explanation right after the turn renders. The AudioContext
  // was unlocked by the submit click (browser autoplay policy, guide risk 6);
  // if the policy still blocks programmatic play, surface a tap-to-play button
  // so the demo never dead-ends on silence.
  useEffect(() => {
    if (!responses[responses.length-1]?.audio_url) return;
    if (spokenRef.current === responses[responses.length-1]?.audio_url) return;
    spokenRef.current = responses[responses.length-1]?.audio_url;

    const play = () => {
      const audio = new Audio(fullAudioUrl(responses[responses.length-1]?.audio_url as string));
      audio.play().catch(() => setSpeakBlocked(true));
    };
    try {
      audioCtxRef.current ??= new AudioContext();
      if (audioCtxRef.current.state === "suspended") {
        void audioCtxRef.current.resume().then(play);
      } else {
        play();
      }
    } catch {
      play();
    }
  }, [responses]);

  async function askText(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg) return;
    setLoading(true);
    setError(null);
    // Unlock audio from this user gesture so the closing speak still plays.
    try {
      audioCtxRef.current ??= new AudioContext();
      void audioCtxRef.current.resume();
    } catch {
      /* audio context unsupported — speak button still works */
    }
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
      responses.push(data); setResponses([...responses, data]);
      setSpeakBlocked(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  function speakNow() {
    if (!responses[responses.length-1]?.audio_url) return;
    setSpeakBlocked(false);
    const lastAudio = responses[responses.length-1]?.audio_url; if (lastAudio) {
      const audio = new Audio(fullAudioUrl(lastAudio as string));
      audio.play().catch(() => setSpeakBlocked(true));
    }
  }

  async function playSuggestion(s: VideoSuggestion) {
    await ask(`tell me about ${s.title}`);
  }

  async function ask(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg) return;
    setLoading(true);
    setError(null);
    try {
      audioCtxRef.current ??= new AudioContext();
      void audioCtxRef.current.resume();
    } catch {}
    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: msg, age: 8 }),
      });
      if (!res.ok) {
        const detail = (await res.json().catch(() => null))?.detail;
        throw new Error(detail || `Request failed (${res.status})`);
      }
      const data = (await res.json()) as ChatResponse;
      responses.push(data); setResponses([...responses, data]);
      setSpeakBlocked(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function startMic() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Microphone not available — please type for me.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunksRef.current = [];
      const recorder = new MediaRecorder(stream, { mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : (MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "") });
      mediaRecorderRef.current = recorder;
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      recorder.onstop = async () => {
        setRecording(false);
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        if (!blob.size) return;
        const form = new FormData();
        form.append("audio", blob, "recording.webm");
        form.append("age", "8");
        setLoading(true);
        try {
          const res = await fetch(`${API_URL}/api/chat`, { method: "POST", body: form });
          if (!res.ok) {
            const detail = (await res.json().catch(() => null))?.detail;
            throw new Error(detail || `Request failed (${res.status})`);
          }
          const data = (await res.json()) as ChatResponse;
          responses.push(data); setResponses([...responses, data]);
          setSpeakBlocked(false);
        } catch (e) {
          setError(e instanceof Error ? e.message : "Something went wrong.");
        } finally {
          setLoading(false);
        }
      };
      recorder.start();
      setRecording(true);
    } catch (e) {
      setError("Couldn't start microphone — please type for me.");
    }
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
    speakButton: {
      display: "block",
      marginTop: "0.75rem",
      backgroundColor: "#818cf8",
      color: "#ffffff",
      border: "none",
      borderRadius: "9999px",
      padding: "0.5rem 1.2rem",
      fontSize: "1rem",
      fontWeight: 600 as const,
      cursor: "pointer",
    },
    hint: { color: "#94a3b8", fontSize: "0.85rem", marginTop: "0.5rem", textAlign: "center" as const },
  };

  return (
    <div style={styles.page}>
      {/* Streak / badge strip (Iteration 13) — never punitive, just celebratory */}
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", padding: "0.25rem 0", flexWrap: "wrap" }}>
        <span style={{ fontSize: "1rem", fontWeight: 600 }}>
          🔥 Streak: {streak || 0}
        </span>
        {badges.map(b => (
          <span key={b} style={{ background: "#fde047", borderRadius: "9999px", padding: "0.2rem 0.6rem", fontSize: "0.8rem", fontWeight: 600 }}>
            🏅 {b}
          </span>
        ))}
      </div>

      <header style={styles.header}>
        <span style={styles.logo}>🎈</span>
        <h1 style={styles.title}>Kiddo Assist</h1>
      </header>

      {error && <div style={styles.error}>⚠️ {error}</div>}

      {loading && (
        <div style={{ ...styles.card, textAlign: "center", color: "#64748b" }}>
          <div>Kiddo is thinking… ⏳</div>
          <div style={{ fontSize: "0.85rem", marginTop: "0.25rem", color: "#94a3b8" }}>
            Listening back • Finding a good answer • Speaking soon
          </div>
        </div>
      )}

      {response && !loading && (
        <>
          {/* Video player — plays on this platform, stream-by-reference */}
          {responses[responses.length-1]?.video_url && responses[responses.length-1]?.video && (
            <div style={styles.card}>
              <video
                controls
                autoPlay
                style={styles.video}
                src={responses[responses.length-1]?.video_url}
                poster={undefined}
              >
                Your browser doesn&apos;t support video playback.
              </video>
              <p style={styles.attribution}>
                🎬 {responses[responses.length-1]?.video.title} · {responses[responses.length-1]?.video.attribution}{" "}
                {responses[responses.length-1]?.video.license && <>· {responses[responses.length-1]?.video.license}</>}
              </p>
            </div>
          )}

          {/* Kiddo Assist's spoken/written explanation */}
          <div style={styles.card}>
            <div aria-live="polite" aria-atomic="true" style={styles.answer}>💬 {responses[responses.length-1]?.answer}</div>

            {/* Speak on demand — shown if the browser stood up to autoplay */}
            {responses[responses.length-1]?.audio_url && speakBlocked && (
              <button style={styles.speakButton} onClick={speakNow}>
                🔊 Hear Kiddo say it
              </button>
            )}

            {/* Tutorial card (P0 #5 — was dead API data) */}
            {responses[responses.length-1]?.tutorial && (
              <div style={{ ...styles.card, marginTop: "0.75rem", background: "#fef3c7" }}>
                <h3 style={{ margin: 0, fontSize: "1rem" }}>Tutorial: step {responses[responses.length-1]?.tutorial.step} of {responses[responses.length-1]?.tutorial.total_steps}</h3>
                <p style={{ margin: "0.25rem 0 0" }}>
                  <button style={styles.chip} onClick={() => {}}>Next →</button>
                </p>
              </div>
            )}

            {/* Quiz card (P0 #5 — was dead API data) */}
            {responses[responses.length-1]?.quiz && (
              <div style={{ ...styles.card, marginTop: "0.75rem", background: "#dbeafe" }}>
                <p style={{ fontWeight: 600 }}>{responses[responses.length-1]?.quiz.question}</p>
                <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                  {responses[responses.length-1]?.quiz.options?.map((opt) => (
                    <button key={opt} style={styles.chip} onClick={() => {}}>{opt}</button>
                  ))}
                </div>
              </div>
            )}

            {/* Suggested next (P0 #5) */}
            {responses[responses.length-1]?.suggested_next && (
              <p style={{ ...styles.hint, marginTop: "0.5rem" }}>
                🌱 Next: {responses[responses.length-1]?.suggested_next}
              </p>
            )}

            {/* Suggestion chips — tap to play another best video */}
            {responses[responses.length-1]?.suggested_videos.length > 0 && (
              <>
                <div style={{ ...styles.chips, marginTop: "1rem" }}>
                  {responses[responses.length-1]?.suggested_videos.map((s) => (
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
            {learnerName ? `Hello ${learnerName}! I'm Kiddo Assist 🎈` : "Hi! I'm Kiddo Assist 🎈"}
            {learnerName && " I'd love to explore your favorites with you!"}
            {!learnerName && " Ask me anything — like \"why is the sky blue?\""}
          </div>
        </div>
      )}

      <div style={{ ...styles.inputBar, alignItems: "flex-end" }}>
        {/* BIG MIC — Iteration 8 / Phase 5, part A */}
        <button
          style={{ ...styles.send, backgroundColor: recording ? "#dc2626" : "#f59e0b", fontSize: "1.3rem", padding: "0.6rem 1rem", borderRadius: "9999px" }}
          aria-label={recording ? "Stop listening" : "Tap to speak"}
          onClick={recording ? () => { mediaRecorderRef.current?.stop(); } : startMic}
          disabled={loading}
        >
          {recording ? "⏹" : "🎤"}
        </button>

        <input
          style={{ ...styles.input, flex: 1 }}
          placeholder="Ask me something… (or tap 🎤)" aria-label="Type your question"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !loading) { askText(); }
          }}
        />
        <button
          style={styles.send}
          disabled={loading}
          onClick={() => askText()}
        >
          Send
        </button>
      </div>
      <p style={styles.hint}>Tap 🎤 to talk — or type for me. Speech miss? I’ll ask you to tap it. 💬</p>
    </div>
  );
}
