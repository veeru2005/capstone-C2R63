// Backend URL.
//  - npm run dev            -> http://localhost:8000
//  - production build       -> same origin as the page ("" = /health, /costs ...)
//  - separate hosting       -> set VITE_API_BASE=https://your-backend.example.com at build time
export const API_BASE =
  import.meta.env.VITE_API_BASE ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

export async function getJSON(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}`);
  return res.json();
}

export const fmtPct = (v, d = 1) => (v === null || v === undefined ? "—" : `${Number(v).toFixed(d)}%`);
