"use client";

export default function ParentDashboardPage() {
  return (
    <main style={{ fontFamily: "'Segoe UI', system-ui, sans-serif", padding: "2rem", maxWidth: "800px", margin: "0 auto" }}>
      <h1>Parent Dashboard</h1>
      <p>Authenticated parent space — rebuilt per directive P0 #4.</p>
      <section>
        <h2>Reports</h2>
        <p>Warm, parent-facing reports (not surveillance logs).</p>
      </section>
      <section>
        <h2>Config</h2>
        <p>Content approval and restriction settings.</p>
      </section>
    </main>
  );
}
