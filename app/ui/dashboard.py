"""Single-page dashboard served by FastAPI.

Self-contained HTML/CSS/JS — no build step, no bundler, no dependency tree.
Talks to the JSON API exposed under ``/tasks``, ``/status/{id}``, ``/run-task``,
``/cancel/{id}``, ``/stats``, ``/health``, ``/screenshots/{file}``.
"""

from __future__ import annotations


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Windows Desktop Automation</title>
<style>
  :root {
    --ink: #0f172a;
    --ink-soft: #334155;
    --muted: #64748b;
    --line: #e2e8f0;
    --line-strong: #cbd5e1;
    --panel: #ffffff;
    --panel-soft: #f8fafc;
    --page: #f1f5f9;
    --green: #16794c;   --green-bg: #dcfce7;
    --red: #b91c1c;     --red-bg:   #fee2e2;
    --blue: #1d4ed8;    --blue-bg:  #dbeafe;
    --amber: #b45309;   --amber-bg: #fef3c7;
    --grey: #475569;    --grey-bg:  #e2e8f0;
    --violet:#6d28d9;   --violet-bg:#ede9fe;
    --accent: #2563eb;
    --accent-soft: #dbeafe;
    --accent-strong:#1d4ed8;
    --shadow: 0 24px 60px -20px rgba(15,23,42,.18);
    --shadow-sm: 0 1px 2px rgba(15,23,42,.06);
    --code-bg: #f1f5f9;
    --sidebar-bg: #0b1220;
    --sidebar-ink: #cbd5e1;
    --sidebar-ink-strong: #f8fafc;
    --sidebar-muted: #64748b;
    --sidebar-active: #1e293b;
    --sidebar-accent: #38bdf8;
    color-scheme: light;
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  [data-theme="dark"] {
    --ink: #e2e8f0;
    --ink-soft: #cbd5e1;
    --muted: #94a3b8;
    --line: #1e293b;
    --line-strong: #334155;
    --panel: #0f172a;
    --panel-soft: #0b1220;
    --page: #060a13;
    --green: #4ade80;   --green-bg: rgba(74,222,128,.14);
    --red: #f87171;     --red-bg:   rgba(248,113,113,.14);
    --blue: #60a5fa;    --blue-bg:  rgba(96,165,250,.14);
    --amber: #fbbf24;   --amber-bg: rgba(251,191,36,.14);
    --grey: #94a3b8;    --grey-bg:  rgba(148,163,184,.14);
    --violet:#a78bfa;   --violet-bg:rgba(167,139,250,.14);
    --accent: #60a5fa;
    --accent-soft: rgba(96,165,250,.16);
    --accent-strong: #93c5fd;
    --shadow: 0 24px 60px -20px rgba(0,0,0,.6);
    --shadow-sm: 0 1px 2px rgba(0,0,0,.4);
    --code-bg: #060a13;
    --sidebar-bg: #03060c;
    --sidebar-ink: #cbd5e1;
    --sidebar-active: #0f172a;
    color-scheme: dark;
  }
  *, *::before, *::after { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    color: var(--ink);
    background: var(--page);
    overflow: hidden;
  }
  button, textarea, input, select { font: inherit; color: inherit; }
  button {
    border: 1px solid var(--line);
    background: var(--panel);
    color: var(--ink);
    border-radius: 8px;
    min-height: 36px;
    padding: 0 14px;
    cursor: pointer;
    font-weight: 500;
    transition: border-color .15s, background .15s, transform .12s, box-shadow .15s;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  button:hover:not(:disabled) { border-color: var(--line-strong); box-shadow: var(--shadow-sm); }
  button:active:not(:disabled) { transform: translateY(1px); }
  button:disabled { opacity: .45; cursor: not-allowed; }
  button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
  button.primary:hover:not(:disabled) { background: var(--accent-strong); border-color: var(--accent-strong); }
  button.danger { color: var(--red); border-color: rgba(185,28,28,.28); }
  button.danger:hover:not(:disabled) { background: var(--red-bg); }
  button.ghost { background: transparent; }
  button.icon { padding: 0; width: 36px; justify-content: center; }
  button.tiny { min-height: 28px; font-size: 12px; padding: 0 8px; border-radius: 6px; }
  input, select, textarea {
    width: 100%;
    border: 1px solid var(--line);
    background: var(--panel-soft);
    border-radius: 8px;
    padding: 8px 10px;
    min-height: 36px;
  }
  textarea {
    line-height: 1.5;
    font-family: "Cascadia Mono", "SFMono-Regular", Consolas, monospace;
    font-size: 13px;
    min-height: 200px;
    resize: vertical;
  }
  input:focus, textarea:focus, select:focus, button:focus-visible {
    outline: 3px solid var(--accent-soft);
    border-color: var(--accent);
  }
  ::-webkit-scrollbar { width: 10px; height: 10px; }
  ::-webkit-scrollbar-thumb { background: var(--line-strong); border-radius: 8px; }
  ::-webkit-scrollbar-track { background: transparent; }

  /* ---------------- App shell ---------------- */
  .app {
    display: grid;
    grid-template-columns: 240px minmax(0,1fr);
    height: 100vh;
  }
  .sidebar {
    background: var(--sidebar-bg);
    color: var(--sidebar-ink);
    display: flex;
    flex-direction: column;
    padding: 18px 14px;
    gap: 14px;
    border-right: 1px solid rgba(255,255,255,.04);
  }
  .sidebar .brand { display: flex; align-items: center; gap: 10px; padding: 4px 6px 16px; border-bottom: 1px solid rgba(255,255,255,.06); }
  .sidebar .brand .mark {
    width: 36px; height: 36px; border-radius: 8px;
    display: grid; place-items: center;
    background: linear-gradient(135deg,#0ea5e9 0,#6366f1 50%,#22c55e 100%);
    color: #fff; font-weight: 800;
  }
  .sidebar .brand .title { color: var(--sidebar-ink-strong); font-weight: 700; line-height: 1.2; font-size: 14px; }
  .sidebar .brand .subtitle { font-size: 11px; color: #94a3b8; letter-spacing: .04em; text-transform: uppercase; }
  .sidebar nav { display: grid; gap: 2px; }
  .nav-item {
    display: flex; align-items: center; gap: 10px;
    padding: 9px 12px;
    background: transparent;
    border: 0;
    border-radius: 8px;
    color: var(--sidebar-ink);
    text-align: left;
    cursor: pointer;
    font-weight: 500;
    transition: background .15s, color .15s;
  }
  .nav-item:hover { background: var(--sidebar-active); color: var(--sidebar-ink-strong); }
  .nav-item[aria-current="page"] {
    background: var(--sidebar-active);
    color: var(--sidebar-ink-strong);
    box-shadow: inset 3px 0 0 var(--sidebar-accent);
  }
  .nav-item svg { width: 18px; height: 18px; flex: 0 0 auto; opacity: .8; }
  .nav-item .badge-pill {
    margin-left: auto;
    font-size: 11px;
    background: rgba(255,255,255,.06);
    border-radius: 999px;
    padding: 2px 8px;
    min-width: 22px;
    text-align: center;
  }
  .sidebar-foot { margin-top: auto; display: grid; gap: 8px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,.06); }
  .sidebar-foot .health {
    display: flex; align-items: center; gap: 8px;
    font-size: 12px;
    padding: 6px 8px;
    border-radius: 6px;
    background: rgba(255,255,255,.04);
    color: var(--sidebar-ink);
  }
  .sidebar-foot .health .dot { width: 8px; height: 8px; border-radius: 50%; background: #94a3b8; }
  .sidebar-foot .health.ok .dot { background: #4ade80; }
  .sidebar-foot .health.degraded .dot { background: #fbbf24; }
  .sidebar-foot .health.down .dot { background: #f87171; }

  .content { display: flex; flex-direction: column; min-width: 0; height: 100vh; overflow: hidden; }
  .content-header {
    display: flex; align-items: center; justify-content: space-between; gap: 16px;
    padding: 18px 28px;
    border-bottom: 1px solid var(--line);
    background: var(--panel);
  }
  .content-header h1 { margin: 0; font-size: 18px; }
  .content-header .crumb { color: var(--muted); font-size: 13px; }
  .content-header .toolbar { display: flex; gap: 8px; flex-wrap: wrap; }
  .content-body { padding: 22px 28px 32px; overflow-y: auto; flex: 1 1 auto; }
  .view { display: none; animation: fade .25s ease; }
  .view.active { display: block; }
  @keyframes fade { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }

  /* ---------------- Cards ---------------- */
  .grid { display: grid; gap: 14px; }
  .grid.cols-4 { grid-template-columns: repeat(4, minmax(0,1fr)); }
  .grid.cols-3 { grid-template-columns: repeat(3, minmax(0,1fr)); }
  .grid.cols-2 { grid-template-columns: repeat(2, minmax(0,1fr)); }
  .card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 16px;
    box-shadow: var(--shadow-sm);
  }
  .card h3 { margin: 0 0 10px; font-size: 14px; }
  .stat { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
  .stat .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; font-weight: 600; }
  .stat .value { font-size: 28px; font-weight: 700; line-height: 1; margin-top: 8px; }
  .stat .delta { font-size: 12px; color: var(--muted); margin-top: 6px; display: inline-flex; align-items: center; gap: 4px; }
  .stat .delta.up { color: var(--green); }
  .stat .delta.down { color: var(--red); }
  .stat .icon-bubble {
    width: 36px; height: 36px; border-radius: 9px;
    display: grid; place-items: center;
    color: var(--accent); background: var(--accent-soft);
  }
  .icon-bubble.green { color: var(--green); background: var(--green-bg); }
  .icon-bubble.red { color: var(--red); background: var(--red-bg); }
  .icon-bubble.amber { color: var(--amber); background: var(--amber-bg); }
  .icon-bubble.violet { color: var(--violet); background: var(--violet-bg); }
  .icon-bubble.blue { color: var(--blue); background: var(--blue-bg); }
  .stat-spark { margin-top: 10px; height: 30px; }
  .stat-spark svg { width: 100%; height: 100%; display: block; }

  /* ---------------- Charts ---------------- */
  .chart-row { display: grid; grid-template-columns: minmax(0,1.5fr) minmax(0,1fr); gap: 14px; }
  .chart { width: 100%; height: 220px; }
  .chart svg { width: 100%; height: 100%; display: block; }
  .chart-legend { display: flex; flex-wrap: wrap; gap: 10px; font-size: 12px; color: var(--muted); margin-top: 8px; }
  .chart-legend span { display: inline-flex; align-items: center; gap: 6px; }
  .chart-legend i { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
  .empty {
    color: var(--muted); padding: 28px; text-align: center;
  }

  /* ---------------- Tasks view ---------------- */
  .tasks-layout {
    display: grid;
    grid-template-columns: minmax(360px, 460px) minmax(0,1fr);
    gap: 16px;
    align-items: start;
  }
  .filters { display: grid; gap: 10px; padding: 10px 14px; border-bottom: 1px solid var(--line); }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip {
    border: 1px solid var(--line);
    background: var(--panel-soft);
    color: var(--ink-soft);
    border-radius: 999px;
    padding: 5px 11px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
  }
  .chip[aria-pressed="true"] { background: var(--accent); border-color: var(--accent); color: #fff; }
  .search-wrap { position: relative; }
  .search-wrap input { padding-left: 34px; }
  .search-wrap svg {
    position: absolute; left: 10px; top: 50%; transform: translateY(-50%);
    width: 16px; height: 16px; color: var(--muted);
  }
  .task-list { display: grid; gap: 8px; padding: 12px; max-height: calc(100vh - 280px); overflow: auto; }
  .task-item {
    width: 100%;
    text-align: left;
    display: grid;
    grid-template-columns: minmax(0,1fr) auto;
    gap: 10px;
    padding: 12px;
    background: var(--panel);
  }
  .task-item[aria-selected="true"] {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-soft);
  }
  .task-name { font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .task-sub { color: var(--muted); font-size: 12px; margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .task-meta { display: flex; gap: 10px; align-items: center; margin-top: 6px; font-size: 12px; color: var(--muted); }
  .progress {
    margin-top: 8px; height: 4px; background: var(--line); border-radius: 999px; overflow: hidden;
  }
  .progress > div { height: 100%; background: var(--accent); transition: width .25s ease; }

  .badge {
    display: inline-flex; align-items: center; justify-content: center;
    border-radius: 999px;
    padding: 3px 9px;
    font-size: 11px;
    font-weight: 700;
    height: 22px;
    text-transform: uppercase;
    letter-spacing: .04em;
  }
  .b-success { color: var(--green); background: var(--green-bg); }
  .b-failed { color: var(--red); background: var(--red-bg); }
  .b-running { color: var(--blue); background: var(--blue-bg); }
  .b-queued { color: var(--amber); background: var(--amber-bg); }
  .b-cancelled { color: var(--grey); background: var(--grey-bg); }

  .detail-grid {
    display: grid;
    grid-template-columns: minmax(0,1.2fr) minmax(280px,.8fr);
    gap: 16px;
    align-items: start;
  }
  .headline {
    display: flex; justify-content: space-between; align-items: flex-start; gap: 14px;
    padding: 18px 18px 8px;
  }
  .headline h2 { margin: 0; font-size: 20px; line-height: 1.2; }
  .id-line { margin-top: 6px; color: var(--muted); font-size: 12px; word-break: break-all; }
  .actions { display: flex; gap: 8px; flex-wrap: wrap; padding: 0 18px 14px; }
  .timeline { padding: 4px 18px 18px; display: grid; gap: 12px; }
  .step {
    display: grid;
    grid-template-columns: 36px minmax(0,1fr) auto;
    gap: 12px;
    align-items: start;
    padding: 12px 0;
    border-top: 1px solid var(--line);
  }
  .step:first-child { border-top: 0; }
  .step .icon-bubble { width: 32px; height: 32px; border-radius: 9px; }
  .step-title { font-weight: 700; }
  .step-sub { margin-top: 4px; color: var(--muted); font-size: 12px; }
  pre {
    margin: 8px 0 0;
    padding: 10px;
    background: var(--code-bg);
    border: 1px solid var(--line);
    border-radius: 8px;
    overflow: auto;
    font-size: 12px;
    line-height: 1.5;
    max-height: 220px;
    font-family: "Cascadia Mono", "SFMono-Regular", Consolas, monospace;
  }
  .err {
    margin-top: 8px;
    color: var(--red);
    background: var(--red-bg);
    border: 1px solid rgba(185,28,28,.25);
    border-radius: 8px;
    padding: 10px;
    font-size: 12px;
    white-space: pre-wrap;
  }
  .sidebox { border-top: 1px solid var(--line); padding: 16px 18px; }
  .sidebox:first-child { border-top: 0; }
  .sidebox h3 { margin: 0 0 10px; font-size: 14px; }
  .kv { display: grid; gap: 8px; font-size: 13px; }
  .kv div { display: grid; grid-template-columns: 96px minmax(0,1fr); gap: 10px; }
  .kv span { color: var(--muted); }
  .kv strong { min-width: 0; overflow-wrap: anywhere; }
  .shots { display: grid; gap: 10px; }
  .shot {
    display: grid;
    grid-template-columns: 78px minmax(0,1fr);
    gap: 10px;
    align-items: center;
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 8px;
    background: var(--panel);
    cursor: zoom-in;
    text-decoration: none;
    color: inherit;
  }
  .shot img { width: 78px; height: 50px; object-fit: cover; border-radius: 6px; background: var(--grey-bg); }
  .shot strong { display: block; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  /* ---------------- Builder ---------------- */
  .builder-grid { display: grid; grid-template-columns: minmax(0,1.2fr) minmax(0,.8fr); gap: 16px; align-items: start; }
  .builder-toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; padding: 12px 14px; border-bottom: 1px solid var(--line); }
  .step-row {
    display: grid;
    grid-template-columns: 36px minmax(0,1fr) auto;
    align-items: start;
    gap: 12px;
    padding: 12px;
    border: 1px solid var(--line);
    border-radius: 10px;
    background: var(--panel-soft);
    margin-bottom: 10px;
  }
  .step-row .grip { cursor: grab; user-select: none; color: var(--muted); display: grid; place-items: center; }
  .step-row.dragging { opacity: .55; }
  .step-row .body { min-width: 0; }
  .step-row .head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .step-row select.type { min-width: 160px; }
  .step-row .params { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; margin-top: 8px; }
  .step-row .params label { font-size: 12px; color: var(--muted); display: grid; gap: 4px; }
  .step-row .controls { display: flex; flex-direction: column; gap: 6px; }
  .step-row .advanced { margin-top: 8px; display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; }
  .step-row details summary { color: var(--muted); cursor: pointer; font-size: 12px; padding: 6px 0; }
  .templates { display: grid; gap: 8px; }
  .template {
    display: grid; grid-template-columns: 36px minmax(0,1fr) auto;
    gap: 10px; align-items: center;
    padding: 10px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--panel-soft);
    text-align: left;
    cursor: pointer;
  }
  .template:hover { border-color: var(--accent); }
  .template strong { display: block; font-size: 13px; }
  .template span { color: var(--muted); font-size: 12px; }

  /* ---------------- Modal & toast ---------------- */
  .toast-wrap { position: fixed; right: 22px; bottom: 22px; display: grid; gap: 8px; z-index: 100; }
  .toast {
    padding: 12px 14px;
    background: var(--panel);
    color: var(--ink);
    border: 1px solid var(--line);
    border-left: 4px solid var(--accent);
    border-radius: 8px;
    box-shadow: var(--shadow);
    max-width: 360px;
    font-size: 13px;
    animation: pop .2s ease;
  }
  .toast.success { border-left-color: var(--green); }
  .toast.error { border-left-color: var(--red); }
  .toast.warn { border-left-color: var(--amber); }
  @keyframes pop { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

  .lightbox {
    position: fixed; inset: 0;
    background: rgba(2,6,12,.8);
    display: none;
    align-items: center;
    justify-content: center;
    padding: 24px;
    z-index: 80;
  }
  .lightbox.open { display: flex; }
  .lightbox img { max-width: 100%; max-height: 100%; box-shadow: 0 20px 60px rgba(0,0,0,.6); border-radius: 8px; }
  .lightbox button.close {
    position: absolute; top: 18px; right: 18px;
    background: rgba(255,255,255,.12); color: #fff; border: 0;
  }

  .kbd {
    display: inline-block;
    padding: 1px 6px;
    border: 1px solid var(--line);
    border-bottom-width: 2px;
    border-radius: 4px;
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 11px;
    color: var(--ink-soft);
    background: var(--panel-soft);
  }

  @media (max-width: 1180px) {
    .app { grid-template-columns: 64px minmax(0,1fr); }
    .sidebar .brand .title, .sidebar .brand .subtitle, .nav-item span:not(.badge-pill), .sidebar-foot .health span:not(.dot) { display: none; }
    .nav-item { justify-content: center; padding: 10px; }
    .nav-item .badge-pill { display: none; }
    .grid.cols-4 { grid-template-columns: repeat(2, minmax(0,1fr)); }
    .grid.cols-3 { grid-template-columns: repeat(2, minmax(0,1fr)); }
    .chart-row, .tasks-layout, .detail-grid, .builder-grid { grid-template-columns: 1fr; }
  }
  @media (max-width: 720px) {
    .grid.cols-4, .grid.cols-3, .grid.cols-2 { grid-template-columns: 1fr; }
    .content-header { padding: 14px 16px; }
    .content-body { padding: 14px 16px 24px; }
    .step { grid-template-columns: 32px minmax(0,1fr); }
  }
</style>
</head>
<body>

<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <defs>
    <symbol id="i-dashboard" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-6H3zM13 9h8V3h-8z"/>
    </symbol>
    <symbol id="i-tasks" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M9 5h11M9 12h11M9 19h11"/><path d="M5 5l-1 1 1 1M5 12l-1 1 1 1M5 19l-1 1 1 1"/>
    </symbol>
    <symbol id="i-builder" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M14 3l7 7-11 11H3v-7z"/><path d="M14 3l7 7"/>
    </symbol>
    <symbol id="i-templates" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1.5"/>
      <rect x="14" y="3" width="7" height="7" rx="1.5"/>
      <rect x="3" y="14" width="7" height="7" rx="1.5"/>
      <rect x="14" y="14" width="7" height="7" rx="1.5"/>
    </symbol>
    <symbol id="i-settings" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3h.1a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>
    </symbol>
    <symbol id="i-search" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>
    </symbol>
    <symbol id="i-plus" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 5v14M5 12h14"/>
    </symbol>
    <symbol id="i-refresh" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 12a9 9 0 0 1 15.5-6.3L21 8M21 3v5h-5M21 12a9 9 0 0 1-15.5 6.3L3 16M3 21v-5h5"/>
    </symbol>
    <symbol id="i-theme" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>
    </symbol>
    <symbol id="i-x" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M6 6l12 12M6 18L18 6"/>
    </symbol>
    <symbol id="i-trash" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
    </symbol>
    <symbol id="i-grip" viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="6" r="1.5"/><circle cx="15" cy="6" r="1.5"/><circle cx="9" cy="12" r="1.5"/><circle cx="15" cy="12" r="1.5"/><circle cx="9" cy="18" r="1.5"/><circle cx="15" cy="18" r="1.5"/></symbol>
    <symbol id="i-up" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 15l7-7 7 7"/></symbol>
    <symbol id="i-down" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 9l7 7 7-7"/></symbol>

    <!-- Step type icons -->
    <symbol id="s-launch_app" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M5 13a7 7 0 0 1 7-7 7 7 0 0 1 7 7c-1 4-4 6-7 6s-6-2-7-6z"/><circle cx="12" cy="11" r="2"/>
      <path d="M5 19l3-3M16 19l3-3"/>
    </symbol>
    <symbol id="s-close_app" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M9 15l6-6"/>
    </symbol>
    <symbol id="s-click" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M8 4l3 14 2.5-5.5L19 11z"/>
    </symbol>
    <symbol id="s-move_mouse" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M5 9h14M9 5l-4 4 4 4M15 13l4 4-4 4M5 17h14"/>
    </symbol>
    <symbol id="s-type_text" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M5 6h14M12 6v14M9 20h6"/>
    </symbol>
    <symbol id="s-hotkey" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <rect x="3" y="6" width="18" height="12" rx="2"/><path d="M7 10h.01M11 10h.01M15 10h.01M7 14h10"/>
    </symbol>
    <symbol id="s-key_press" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <rect x="4" y="5" width="16" height="14" rx="2"/><path d="M8 9h.01M12 9h.01M16 9h.01M8 13h.01M12 13h.01M16 13h.01"/>
    </symbol>
    <symbol id="s-wait" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>
    </symbol>
    <symbol id="s-screenshot" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M4 8h3l1.5-2h7L17 8h3v11H4z"/><circle cx="12" cy="13" r="4"/>
    </symbol>
    <symbol id="s-scroll" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <rect x="9" y="3" width="6" height="18" rx="3"/><path d="M12 7v3"/>
    </symbol>
    <symbol id="s-drag" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M9 5v6M9 5l-3 3M9 5l3 3"/>
      <path d="M15 19v-6M15 19l-3-3M15 19l3-3"/>
    </symbol>
    <symbol id="s-write_clipboard" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4h6M9 12h6M9 16h4"/>
    </symbol>
    <symbol id="s-read_clipboard" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4h6M9 13l3-3 3 3M12 10v7"/>
    </symbol>
  </defs>
</svg>

<div class="app">
  <aside class="sidebar">
    <div class="brand">
      <div class="mark">W</div>
      <div>
        <div class="title">Desktop Automation</div>
        <div class="subtitle">v1</div>
      </div>
    </div>
    <nav id="nav">
      <button class="nav-item" data-view="dashboard" aria-current="page">
        <svg><use href="#i-dashboard"/></svg><span>Dashboard</span>
      </button>
      <button class="nav-item" data-view="tasks">
        <svg><use href="#i-tasks"/></svg><span>Tasks</span><span class="badge-pill" id="navTasksBadge">0</span>
      </button>
      <button class="nav-item" data-view="builder">
        <svg><use href="#i-builder"/></svg><span>Builder</span>
      </button>
      <button class="nav-item" data-view="templates">
        <svg><use href="#i-templates"/></svg><span>Templates</span>
      </button>
      <button class="nav-item" data-view="settings">
        <svg><use href="#i-settings"/></svg><span>Settings</span>
      </button>
    </nav>
    <div class="sidebar-foot">
      <div class="health" id="healthPill">
        <span class="dot"></span><span id="healthText">checking…</span>
      </div>
    </div>
  </aside>

  <div class="content">
    <header class="content-header">
      <div>
        <h1 id="viewTitle">Dashboard</h1>
        <div class="crumb" id="viewCrumb">Live overview of automation runs</div>
      </div>
      <div class="toolbar">
        <button id="themeBtn" class="icon" title="Toggle theme (T)"><svg width="16" height="16"><use href="#i-theme"/></svg></button>
        <button id="refreshBtn" title="Refresh (R)"><svg width="16" height="16"><use href="#i-refresh"/></svg> Refresh</button>
        <button id="newTaskBtn" class="primary" title="Open the visual builder"><svg width="16" height="16"><use href="#i-plus"/></svg> New task</button>
      </div>
    </header>
    <div class="content-body">

      <!-- ============ DASHBOARD ============ -->
      <section class="view active" id="view-dashboard">
        <div class="grid cols-4" id="statCards"></div>

        <div class="chart-row" style="margin-top:14px">
          <div class="card">
            <h3>Runs in the last 24 hours</h3>
            <div class="chart" id="chartHourly"></div>
            <div class="chart-legend">
              <span><i style="background:var(--green)"></i>Success</span>
              <span><i style="background:var(--red)"></i>Failed</span>
              <span><i style="background:var(--amber)"></i>Cancelled</span>
            </div>
          </div>
          <div class="card">
            <h3>Status distribution</h3>
            <div class="chart" id="chartDonut"></div>
          </div>
        </div>

        <div class="grid cols-2" style="margin-top:14px">
          <div class="card">
            <h3>Most-used step types</h3>
            <div class="chart" id="chartSteps"></div>
          </div>
          <div class="card">
            <h3>Recent activity</h3>
            <div id="recentList"></div>
          </div>
        </div>
      </section>

      <!-- ============ TASKS ============ -->
      <section class="view" id="view-tasks">
        <div class="tasks-layout">
          <div class="card" style="padding:0">
            <div class="filters">
              <div class="chips" id="statusChips" role="tablist">
                <button class="chip" data-status="" aria-pressed="true">All</button>
                <button class="chip" data-status="queued" aria-pressed="false">Queued</button>
                <button class="chip" data-status="running" aria-pressed="false">Running</button>
                <button class="chip" data-status="success" aria-pressed="false">Success</button>
                <button class="chip" data-status="failed" aria-pressed="false">Failed</button>
                <button class="chip" data-status="cancelled" aria-pressed="false">Cancelled</button>
              </div>
              <div class="search-wrap">
                <svg><use href="#i-search"/></svg>
                <input id="searchInput" placeholder="Search by name or id…" autocomplete="off">
              </div>
            </div>
            <div class="task-list" id="taskList"></div>
          </div>
          <div class="card" id="detailPanel" style="padding:0">
            <div class="empty">Select a task to inspect its step audit.</div>
          </div>
        </div>
      </section>

      <!-- ============ BUILDER ============ -->
      <section class="view" id="view-builder">
        <div class="builder-grid">
          <div class="card" style="padding:0">
            <div class="builder-toolbar">
              <input id="bName" placeholder="Pipeline name (required)" style="max-width:280px">
              <select id="bAddType" style="max-width:200px"></select>
              <button id="bAdd"><svg width="14" height="14"><use href="#i-plus"/></svg> Add step</button>
              <button id="bClear" class="ghost">Clear</button>
              <span style="flex:1"></span>
              <button id="bRun" class="primary">Run pipeline</button>
            </div>
            <div id="bSteps" style="padding: 14px"></div>
          </div>
          <div class="card">
            <h3>JSON preview</h3>
            <textarea id="bJson" spellcheck="false"></textarea>
            <div style="display:flex; gap:8px; margin-top:10px; justify-content:flex-end">
              <button class="ghost" id="bImport">Import JSON</button>
              <button class="ghost" id="bCopy">Copy JSON</button>
            </div>
          </div>
        </div>
      </section>

      <!-- ============ TEMPLATES ============ -->
      <section class="view" id="view-templates">
        <div class="card">
          <h3>Pre-built pipelines</h3>
          <p class="empty" style="padding:6px 0; text-align:left;">Click any template to load it into the Builder.</p>
          <div class="templates" id="templateList"></div>
        </div>
      </section>

      <!-- ============ SETTINGS ============ -->
      <section class="view" id="view-settings">
        <div class="grid cols-2">
          <div class="card">
            <h3>Appearance</h3>
            <label style="display:grid; gap:6px; margin-bottom:12px">
              <span>Theme</span>
              <select id="setTheme">
                <option value="auto">System</option>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </select>
            </label>
          </div>
          <div class="card">
            <h3>Live updates</h3>
            <label style="display:grid; gap:6px; margin-bottom:12px">
              <span>Polling interval (seconds)</span>
              <input id="setPoll" type="number" min="1" max="60" step="1">
            </label>
            <label style="display:flex; gap:8px; align-items:center; margin-top:4px;">
              <input id="setNotify" type="checkbox"> Browser notification when a task completes
            </label>
          </div>
          <div class="card">
            <h3>Server info</h3>
            <div class="kv" id="serverInfo"></div>
          </div>
          <div class="card">
            <h3>Keyboard shortcuts</h3>
            <div class="kv">
              <div><span><span class="kbd">R</span></span><strong>Refresh</strong></div>
              <div><span><span class="kbd">T</span></span><strong>Toggle theme</strong></div>
              <div><span><span class="kbd">N</span></span><strong>New task (Builder)</strong></div>
              <div><span><span class="kbd">/</span></span><strong>Focus search</strong></div>
              <div><span><span class="kbd">Esc</span></span><strong>Close lightbox</strong></div>
              <div><span><span class="kbd">Ctrl</span>+<span class="kbd">Enter</span></span><strong>Submit task JSON</strong></div>
            </div>
          </div>
        </div>
      </section>

    </div>
  </div>
</div>

<div class="toast-wrap" id="toasts"></div>
<div class="lightbox" id="lightbox" role="dialog" aria-label="Screenshot">
  <button class="close" id="lightboxClose" aria-label="Close"><svg width="16" height="16"><use href="#i-x"/></svg></button>
  <img id="lightboxImg" src="" alt="">
</div>

<script>
(function () {
  "use strict";

  // ====================================================================
  //  Constants & state
  // ====================================================================
  const STORAGE = { theme: "wda.theme", poll: "wda.poll", notify: "wda.notify" };
  const STEP_TYPES = [
    "launch_app","close_app","click","move_mouse","type_text",
    "hotkey","key_press","wait","screenshot","scroll","drag",
    "write_clipboard","read_clipboard"
  ];
  const STATUS_COLORS = {
    success:  "var(--green)",
    failed:   "var(--red)",
    running:  "var(--blue)",
    queued:   "var(--amber)",
    cancelled:"var(--grey)"
  };
  const ICON_BUBBLE = {
    launch_app:"violet", close_app:"red", click:"blue", move_mouse:"blue",
    type_text:"green", hotkey:"green", key_press:"green", wait:"amber",
    screenshot:"blue", scroll:"blue", drag:"violet",
    write_clipboard:"green", read_clipboard:"green"
  };
  const TEMPLATES = [
    {
      name: "open-calculator-and-add",
      summary: "Launch calc.exe, type 12+30=, screenshot, close.",
      pipeline: {
        name: "open-calculator-and-add",
        steps: [
          { type:"launch_app", params:{ path:"calc.exe", wait_seconds:1.5 } },
          { type:"type_text",  params:{ text:"12+30=", interval:0.05 } },
          { type:"wait",       params:{ seconds:0.5 } },
          { type:"screenshot", params:{ label:"calc_result" } },
          { type:"close_app",  params:{ image_name:"Calculator.exe", force:true }, on_failure:"continue" }
        ]
      }
    },
    {
      name: "open-notepad-and-save",
      summary: "Notepad: type a paragraph, Ctrl+S, save under wda_demo_output.txt.",
      pipeline: {
        name: "open-notepad-and-save",
        steps: [
          { type:"launch_app", params:{ path:"notepad.exe", wait_seconds:1.5 }, retries:1 },
          { type:"type_text",  params:{ text:"Hello from the Windows Desktop Automation Framework!\nThis file was generated by an automated pipeline.\n", interval:0.01 } },
          { type:"hotkey",     params:{ keys:["ctrl","s"] } },
          { type:"wait",       params:{ seconds:1.0 } },
          { type:"type_text",  params:{ text:"wda_demo_output.txt", interval:0.01 } },
          { type:"hotkey",     params:{ keys:["enter"] } },
          { type:"wait",       params:{ seconds:0.5 } },
          { type:"screenshot", params:{ label:"after_save" } }
        ]
      }
    },
    {
      name: "paint-doodle-and-screenshot",
      summary: "Paint: drag two diagonals, scroll, screenshot, close.",
      pipeline: {
        name: "paint-doodle-and-screenshot",
        steps: [
          { type:"launch_app", params:{ path:"mspaint.exe", wait_seconds:2.0 } },
          { type:"drag",       params:{ from_x:400, from_y:400, to_x:800, to_y:600, duration:0.6 } },
          { type:"drag",       params:{ from_x:800, from_y:400, to_x:400, to_y:600, duration:0.6 } },
          { type:"scroll",     params:{ clicks:-3 } },
          { type:"wait",       params:{ seconds:0.4 } },
          { type:"screenshot", params:{ label:"paint_doodle" }, timeout_seconds:5 },
          { type:"close_app",  params:{ image_name:"mspaint.exe", force:true }, on_failure:"continue" }
        ]
      }
    },
    {
      name: "clipboard-roundtrip",
      summary: "Write and read the clipboard via clip.exe / Get-Clipboard.",
      pipeline: {
        name: "clipboard-roundtrip",
        steps: [
          { type:"write_clipboard", params:{ text:"hello from automation" } },
          { type:"wait", params:{ seconds:0.2 } },
          { type:"read_clipboard", params:{} }
        ]
      }
    }
  ];
  // Per-step-type input form definitions.
  const STEP_FORMS = {
    launch_app:    [{ k:"path", t:"text", req:true, ph:"notepad.exe" }, { k:"args", t:"text", ph:"optional, list or string" }, { k:"wait_seconds", t:"number", ph:"1.5", step:"0.1" }],
    close_app:     [{ k:"image_name", t:"text", req:true, ph:"Calculator.exe" }, { k:"force", t:"checkbox", default:true }],
    click:         [{ k:"x", t:"number" }, { k:"y", t:"number" }, { k:"image", t:"text", ph:"optional .png path" }, { k:"button", t:"select", options:["left","right","middle"], default:"left" }, { k:"clicks", t:"number", default:1 }, { k:"confidence", t:"number", step:"0.05", ph:"0.9" }],
    move_mouse:    [{ k:"x", t:"number", req:true }, { k:"y", t:"number", req:true }, { k:"duration", t:"number", step:"0.1" }],
    type_text:     [{ k:"text", t:"textarea", req:true }, { k:"interval", t:"number", step:"0.01", ph:"0.02" }],
    hotkey:        [{ k:"keys", t:"text", req:true, ph:"ctrl,s" }],
    key_press:     [{ k:"key", t:"text", req:true, ph:"enter" }, { k:"presses", t:"number", default:1 }, { k:"interval", t:"number", step:"0.01" }],
    wait:          [{ k:"seconds", t:"number", default:1.0, step:"0.1" }],
    screenshot:    [{ k:"label", t:"text", ph:"step" }],
    scroll:        [{ k:"clicks", t:"number", req:true, ph:"-3" }, { k:"x", t:"number" }, { k:"y", t:"number" }],
    drag:          [{ k:"from_x", t:"number", req:true }, { k:"from_y", t:"number", req:true }, { k:"to_x", t:"number", req:true }, { k:"to_y", t:"number", req:true }, { k:"duration", t:"number", step:"0.1" }, { k:"button", t:"select", options:["left","right","middle"], default:"left" }],
    write_clipboard:[{ k:"text", t:"textarea", req:true }],
    read_clipboard:[]
  };

  const state = {
    view: "dashboard",
    tasks: [],
    selectedId: null,
    detail: null,
    stats: null,
    health: null,
    filterStatus: "",
    query: "",
    pollMs: 2500,
    notifyOnDone: false,
    seenTerminal: new Set(),  // for desktop notifications
    timer: null,
    builder: { name: "", steps: [] }
  };

  // ====================================================================
  //  Utilities
  // ====================================================================
  const $ = (id) => document.getElementById(id);
  const fmt = (v) => v ? new Date(v).toLocaleString() : "—";
  const fmtTime = (v) => v ? new Date(v).toLocaleTimeString() : "—";
  const statusClass = (s) => "b-" + String(s || "").toLowerCase();
  const basename = (p) => String(p || "").split(/[\\/]/).pop();
  const escapeHtml = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
  const fmtDuration = (start, end) => {
    if (!start) return "—";
    const startMs = new Date(start).getTime();
    const endMs = end ? new Date(end).getTime() : Date.now();
    const sec = Math.max(0, (endMs - startMs) / 1000);
    if (sec < 60) return sec.toFixed(sec < 10 ? 1 : 0) + "s";
    const m = Math.floor(sec / 60);
    return m + "m " + Math.round(sec - m * 60) + "s";
  };
  const colorVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  function toast(message, kind = "info") {
    const el = document.createElement("div");
    el.className = "toast " + (kind || "");
    el.textContent = message;
    $("toasts").appendChild(el);
    setTimeout(() => { el.style.opacity = "0"; el.style.transform = "translateY(8px)"; }, 2400);
    setTimeout(() => el.remove(), 2700);
  }

  async function api(path, options) {
    const res = await fetch(path, options);
    if (!res.ok) {
      let detail = await res.text();
      try { detail = JSON.parse(detail).detail || detail; } catch (_) {}
      throw new Error(detail || res.statusText);
    }
    const text = await res.text();
    return text ? JSON.parse(text) : null;
  }

  // ====================================================================
  //  Theme & settings
  // ====================================================================
  function applyTheme(mode) {
    let theme = mode;
    if (mode === "auto") theme = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem(STORAGE.theme, mode); } catch (_) {}
    $("setTheme").value = mode;
  }
  function loadSettings() {
    const t = (localStorage.getItem(STORAGE.theme) || "auto");
    applyTheme(t);
    const p = parseInt(localStorage.getItem(STORAGE.poll) || "2500", 10);
    state.pollMs = isFinite(p) ? p : 2500;
    $("setPoll").value = Math.round(state.pollMs / 1000);
    state.notifyOnDone = localStorage.getItem(STORAGE.notify) === "1";
    $("setNotify").checked = state.notifyOnDone;
  }
  $("setTheme")?.addEventListener("change", (e) => applyTheme(e.target.value));
  $("setPoll")?.addEventListener("change", (e) => {
    const sec = Math.max(1, Math.min(60, parseInt(e.target.value, 10) || 2));
    state.pollMs = sec * 1000;
    localStorage.setItem(STORAGE.poll, String(state.pollMs));
    startPolling();
    toast("Polling every " + sec + "s", "success");
  });
  $("setNotify")?.addEventListener("change", async (e) => {
    state.notifyOnDone = e.target.checked;
    localStorage.setItem(STORAGE.notify, e.target.checked ? "1" : "0");
    if (e.target.checked && "Notification" in window && Notification.permission !== "granted") {
      const result = await Notification.requestPermission();
      if (result !== "granted") {
        e.target.checked = false;
        state.notifyOnDone = false;
        localStorage.setItem(STORAGE.notify, "0");
        toast("Notification permission denied", "warn");
      }
    }
  });
  $("themeBtn").addEventListener("click", () => {
    const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(t);
  });

  // ====================================================================
  //  Navigation
  // ====================================================================
  const VIEW_TITLES = {
    dashboard: ["Dashboard", "Live overview of automation runs"],
    tasks:     ["Tasks", "Audit trail and step-by-step status"],
    builder:   ["Builder", "Compose a pipeline visually, then run it"],
    templates: ["Templates", "Pre-built pipelines you can load and edit"],
    settings:  ["Settings", "Theme, polling, and notifications"]
  };
  function setView(name) {
    state.view = name;
    document.querySelectorAll(".nav-item").forEach(b => {
      b.toggleAttribute("aria-current", b.dataset.view === name);
      if (b.dataset.view === name) b.setAttribute("aria-current", "page");
      else b.removeAttribute("aria-current");
    });
    document.querySelectorAll(".view").forEach(v => v.classList.toggle("active", v.id === "view-" + name));
    const [t, c] = VIEW_TITLES[name] || ["", ""];
    $("viewTitle").textContent = t;
    $("viewCrumb").textContent = c;
    if (name === "templates") renderTemplates();
    if (name === "settings") renderServerInfo();
    if (name === "dashboard") renderDashboard();
  }
  $("nav").addEventListener("click", (e) => {
    const item = e.target.closest(".nav-item");
    if (item) setView(item.dataset.view);
  });
  $("newTaskBtn").addEventListener("click", () => setView("builder"));

  // ====================================================================
  //  Data load
  // ====================================================================
  async function loadAll() {
    await Promise.all([loadTasks(true), loadStats(), loadHealth()]);
    if (state.view === "dashboard") renderDashboard();
  }
  async function loadTasks(keepSelection = true) {
    const params = new URLSearchParams({ limit: "120" });
    if (state.filterStatus) params.set("status", state.filterStatus);
    if (state.query) params.set("q", state.query);
    state.tasks = await api("/tasks?" + params.toString());
    detectTerminalTransitions();
    if (!keepSelection || !state.selectedId || !state.tasks.some(t => t.id === state.selectedId)) {
      state.selectedId = state.tasks[0]?.id || null;
    }
    $("navTasksBadge").textContent = state.tasks.length;
    renderTaskList();
    if (state.selectedId) await loadDetail(state.selectedId, false);
    else renderEmptyDetail();
  }
  async function loadStats() {
    try {
      state.stats = await api("/stats");
      renderStatCards();
    } catch (_) {}
  }
  async function loadHealth() {
    try {
      state.health = await api("/health");
      const pill = $("healthPill");
      pill.classList.remove("ok","degraded","down");
      pill.classList.add(state.health.status === "ok" ? "ok" : "degraded");
      $("healthText").textContent = "API " + state.health.status + " · DB " + state.health.database + " · worker " + state.health.worker;
    } catch (_) {
      $("healthPill").classList.add("down");
      $("healthText").textContent = "API unreachable";
    }
  }
  async function loadDetail(id, scroll = true) {
    state.selectedId = id;
    try {
      state.detail = await api("/status/" + encodeURIComponent(id));
    } catch (err) { toast(err.message, "error"); return; }
    renderTaskList();
    renderDetail();
    if (scroll && state.view !== "tasks") setView("tasks");
  }

  function detectTerminalTransitions() {
    if (!state.notifyOnDone || !("Notification" in window) || Notification.permission !== "granted") return;
    state.tasks.forEach(t => {
      const isTerminal = ["success","failed","cancelled"].includes(t.status);
      if (!isTerminal) return;
      if (state.seenTerminal.has(t.id)) return;
      state.seenTerminal.add(t.id);
      // Skip first load — only notify on transitions seen after page open.
      if (state.seenTerminal.size > state.tasks.length) {
        try {
          new Notification("Task " + t.status, { body: t.name });
        } catch (_) {}
      }
    });
  }

  // ====================================================================
  //  Renderers — Dashboard
  // ====================================================================
  function renderStatCards() {
    const s = state.stats;
    if (!s) return;
    const c = s.by_status || {};
    const success = c.success || 0;
    const failed = c.failed || 0;
    const denom = success + failed;
    const rate = denom ? Math.round((success / denom) * 100) : 0;
    const cards = [
      { label:"Total runs", value:s.total || 0, sub:(s.last_task_at ? "last " + fmtTime(s.last_task_at) : "no runs yet"), icon:"i-tasks", color:"" },
      { label:"Running",    value:c.running || 0, sub:(s.running_task_id ? s.running_task_id.slice(0,8) + "…" : "idle"), icon:"s-launch_app", color:"blue" },
      { label:"Queue depth",value:s.queue_depth || 0, sub:(c.queued || 0) + " queued", icon:"i-tasks", color:"amber" },
      { label:"Success rate", value: rate + "%", sub: success + " ok / " + failed + " fail", icon:"s-screenshot", color:"green" }
    ];
    $("statCards").innerHTML = cards.map(card => `
      <div class="card">
        <div class="stat">
          <div>
            <div class="label">${escapeHtml(card.label)}</div>
            <div class="value">${escapeHtml(card.value)}</div>
            <div class="delta">${escapeHtml(card.sub)}</div>
          </div>
          <div class="icon-bubble ${card.color}"><svg width="18" height="18"><use href="#${card.icon}"/></svg></div>
        </div>
      </div>
    `).join("");
  }

  function renderDashboard() {
    renderStatCards();
    renderHourlyChart();
    renderDonut();
    renderStepBars();
    renderRecentList();
  }

  function svgEl(tag, attrs = {}, inner = "") {
    return `<${tag} ${Object.entries(attrs).map(([k,v]) => `${k}="${v}"`).join(" ")}>${inner}</${tag}>`;
  }

  function renderHourlyChart() {
    const buckets = new Array(24).fill(0).map(() => ({ success:0, failed:0, cancelled:0, other:0 }));
    const now = Date.now();
    state.tasks.forEach(t => {
      const ts = t.created_at ? new Date(t.created_at).getTime() : 0;
      const diffH = Math.floor((now - ts) / 3600000);
      if (diffH < 0 || diffH > 23) return;
      const bucket = buckets[23 - diffH];
      if (["success","failed","cancelled"].includes(t.status)) bucket[t.status] += 1;
      else bucket.other += 1;
    });
    const W = 720, H = 200, P = 26;
    const innerW = W - P * 2, innerH = H - P * 2;
    const max = Math.max(1, ...buckets.map(b => b.success + b.failed + b.cancelled + b.other));
    const barW = innerW / 24 - 4;
    let bars = "";
    buckets.forEach((b, i) => {
      const x = P + i * (innerW / 24);
      let yCursor = H - P;
      const segments = [
        { val: b.success,   color: colorVar("--green") },
        { val: b.failed,    color: colorVar("--red") },
        { val: b.cancelled, color: colorVar("--amber") },
        { val: b.other,     color: colorVar("--blue") }
      ];
      segments.forEach(seg => {
        if (!seg.val) return;
        const h = (seg.val / max) * innerH;
        yCursor -= h;
        bars += svgEl("rect", { x: x.toFixed(1), y: yCursor.toFixed(1), width: barW.toFixed(1), height: h.toFixed(1), fill: seg.color, rx: 2 });
      });
    });
    // axis ticks
    let ticks = "";
    for (let g = 0; g <= 4; g++) {
      const y = P + (innerH * g / 4);
      const v = Math.round(max - (max * g / 4));
      ticks += svgEl("line", { x1: P, x2: W - P, y1: y, y2: y, stroke: colorVar("--line"), "stroke-dasharray": "2 4" });
      ticks += svgEl("text", { x: 4, y: y + 4, "font-size": 10, fill: colorVar("--muted") }, v);
    }
    let xlabels = "";
    [0, 6, 12, 18, 23].forEach(i => {
      const x = P + i * (innerW / 24);
      xlabels += svgEl("text", { x: x + barW / 2, y: H - 6, "font-size": 10, fill: colorVar("--muted"), "text-anchor": "middle" }, (i === 23 ? "now" : (i + "h")));
    });
    $("chartHourly").innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${ticks}${bars}${xlabels}</svg>`;
  }

  function renderDonut() {
    const c = (state.stats && state.stats.by_status) || {};
    const data = [
      { k:"success", v: c.success || 0 },
      { k:"failed",  v: c.failed || 0 },
      { k:"running", v: c.running || 0 },
      { k:"queued",  v: c.queued || 0 },
      { k:"cancelled", v: c.cancelled || 0 }
    ];
    const total = data.reduce((a, b) => a + b.v, 0);
    const W = 240, H = 200, R = 76, IR = 50, CX = W / 2, CY = H / 2;
    let segs = "";
    if (total === 0) {
      segs = svgEl("circle", { cx: CX, cy: CY, r: R, fill: "none", stroke: colorVar("--line"), "stroke-width": R - IR });
    } else {
      let a0 = -Math.PI / 2;
      data.forEach(d => {
        if (!d.v) return;
        const a1 = a0 + (d.v / total) * Math.PI * 2;
        const big = (a1 - a0) > Math.PI ? 1 : 0;
        const x0 = CX + R * Math.cos(a0), y0 = CY + R * Math.sin(a0);
        const x1 = CX + R * Math.cos(a1), y1 = CY + R * Math.sin(a1);
        const ix0 = CX + IR * Math.cos(a0), iy0 = CY + IR * Math.sin(a0);
        const ix1 = CX + IR * Math.cos(a1), iy1 = CY + IR * Math.sin(a1);
        const path = `M ${x0} ${y0} A ${R} ${R} 0 ${big} 1 ${x1} ${y1} L ${ix1} ${iy1} A ${IR} ${IR} 0 ${big} 0 ${ix0} ${iy0} Z`;
        segs += svgEl("path", { d: path, fill: STATUS_COLORS[d.k] });
        a0 = a1;
      });
    }
    const center = svgEl("text", { x: CX, y: CY - 4, "text-anchor": "middle", "font-size": 26, "font-weight": 700, fill: colorVar("--ink") }, total);
    const label = svgEl("text", { x: CX, y: CY + 16, "text-anchor": "middle", "font-size": 11, fill: colorVar("--muted") }, "tasks");
    const legendItems = data.filter(d => d.v).map(d => svgEl("text", { x: 0, y: 0 }));
    let legend = "";
    data.filter(d => d.v).forEach((d, i) => {
      const lx = 12, ly = 28 + i * 18;
      legend += svgEl("rect", { x: lx, y: ly - 9, width: 10, height: 10, rx: 2, fill: STATUS_COLORS[d.k] });
      legend += svgEl("text", { x: lx + 16, y: ly, "font-size": 11, fill: colorVar("--muted") }, d.k + " · " + d.v);
    });
    $("chartDonut").innerHTML = `<svg viewBox="0 0 ${W} ${H}">${segs}${center}${label}${legend}</svg>`;
  }

  function renderStepBars() {
    const counts = {};
    state.tasks.forEach(t => {
      // We only know the step types from /status; that's expensive to fetch for every task on every poll.
      // The dashboard chart approximates from the currently selected detail + cached counts.
      // For a richer view we count from the loaded detail of the currently selected task plus our cache.
    });
    // Instead, read from a running cache of step types we have observed in `state.detail`.
    if (!state._stepCounts) state._stepCounts = {};
    if (state.detail && Array.isArray(state.detail.steps)) {
      state.detail.steps.forEach(s => {
        state._stepCounts[s.step_type] = (state._stepCounts[s.step_type] || 0) + 1;
      });
    }
    const entries = Object.entries(state._stepCounts).sort((a, b) => b[1] - a[1]).slice(0, 8);
    if (entries.length === 0) {
      $("chartSteps").innerHTML = `<div class="empty">Open a task to populate this chart.</div>`;
      return;
    }
    const W = 480, H = 200, P = 16, ROW = 22;
    const max = Math.max(...entries.map(([, n]) => n));
    let body = "";
    entries.forEach(([k, n], i) => {
      const y = P + i * ROW;
      body += svgEl("text", { x: 0, y: y + 13, "font-size": 11, fill: colorVar("--muted") }, k);
      const bw = ((W - 110) * (n / max));
      body += svgEl("rect", { x: 100, y: y + 4, width: bw.toFixed(1), height: 14, rx: 4, fill: colorVar("--accent") });
      body += svgEl("text", { x: 100 + bw + 6, y: y + 14, "font-size": 11, fill: colorVar("--ink-soft") }, n);
    });
    $("chartSteps").innerHTML = `<svg viewBox="0 0 ${W} ${H}">${body}</svg>`;
  }

  function renderRecentList() {
    const recent = state.tasks.slice(0, 6);
    if (recent.length === 0) {
      $("recentList").innerHTML = `<div class="empty">No runs yet — try a template.</div>`;
      return;
    }
    $("recentList").innerHTML = recent.map(t => `
      <div style="display:flex; align-items:center; gap:12px; padding:8px 0; border-top:1px solid var(--line)">
        <div class="icon-bubble ${ICON_BUBBLE.launch_app || ""}"><svg width="14" height="14"><use href="#i-tasks"/></svg></div>
        <div style="min-width:0; flex:1">
          <div style="font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap">${escapeHtml(t.name)}</div>
          <div style="color:var(--muted); font-size:12px">${fmt(t.created_at)} · ${fmtDuration(t.started_at, t.finished_at)}</div>
        </div>
        <span class="badge ${statusClass(t.status)}">${escapeHtml(t.status)}</span>
      </div>
    `).join("");
  }

  // ====================================================================
  //  Renderers — Tasks
  // ====================================================================
  function renderTaskList() {
    const list = $("taskList");
    if (!state.tasks.length) {
      list.innerHTML = `<div class="empty">No tasks match.</div>`;
      return;
    }
    list.innerHTML = state.tasks.map(t => {
      const running = t.status === "running";
      const progress = running ? `<div class="progress"><div style="width:${(state.detail && state.detail.id===t.id) ? Math.min(99, (state.detail.steps.length / Math.max(1, state.detail.steps.length))*100) : 30}%"></div></div>` : "";
      return `
      <button class="task-item" aria-selected="${t.id === state.selectedId}" data-id="${escapeHtml(t.id)}">
        <span style="min-width:0">
          <span class="task-name">${escapeHtml(t.name)}</span>
          <span class="task-sub">${escapeHtml(t.id)}</span>
          <span class="task-meta">${fmt(t.created_at)} · ${fmtDuration(t.started_at, t.finished_at)}</span>
          ${progress}
        </span>
        <span class="badge ${statusClass(t.status)}">${escapeHtml(t.status)}</span>
      </button>`;
    }).join("");
    list.querySelectorAll("[data-id]").forEach(btn => {
      btn.addEventListener("click", () => loadDetail(btn.dataset.id));
    });
  }

  function renderEmptyDetail() {
    $("detailPanel").innerHTML = `<div class="empty">Select a task to inspect its step audit.</div>`;
  }

  function renderDetail() {
    const d = state.detail;
    if (!d) return renderEmptyDetail();
    const stepCount = (d.steps || []).length;
    const completed = (d.steps || []).filter(s => s.finished_at).length;
    const isQueued = d.status === "queued";
    const isTerminal = ["success","failed","cancelled"].includes(d.status);
    const screenshots = (d.steps || []).filter(s => s.screenshot_path);

    const stepsHtml = (d.steps || []).map(s => `
      <div class="step">
        <div class="icon-bubble ${ICON_BUBBLE[s.step_type] || "blue"}"><svg width="16" height="16"><use href="#s-${s.step_type}"/></svg></div>
        <div>
          <div class="step-title">${escapeHtml(s.step_type)} <span style="color:var(--muted); font-weight:500; font-size:12px">(step ${Number(s.step_index) + 1})</span></div>
          <div class="step-sub">
            Attempts ${escapeHtml(s.attempts)} · ${fmtDuration(s.started_at, s.finished_at)} · ${fmtTime(s.started_at)} → ${fmtTime(s.finished_at)}
          </div>
          <pre>${escapeHtml(JSON.stringify(s.params || {}, null, 2))}</pre>
          ${s.error ? `<div class="err">${escapeHtml(s.error)}</div>` : ""}
        </div>
        <span class="badge ${s.success ? "b-success" : (s.finished_at ? "b-failed" : "b-running")}">${s.success ? "ok" : (s.finished_at ? "failed" : "…")}</span>
      </div>
    `).join("");

    $("detailPanel").innerHTML = `
      <div class="detail-grid">
        <div>
          <div class="headline">
            <div>
              <h2>${escapeHtml(d.name)}</h2>
              <div class="id-line">${escapeHtml(d.id)}</div>
              <div class="progress" style="margin-top:10px"><div style="width:${stepCount ? (completed/stepCount)*100 : 0}%"></div></div>
              <div style="font-size:12px; color:var(--muted); margin-top:6px">${completed} / ${stepCount} steps complete</div>
            </div>
            <span class="badge ${statusClass(d.status)}">${escapeHtml(d.status)}</span>
          </div>
          <div class="actions">
            <button id="rerunBtn" class="primary">Re-run</button>
            <button id="cancelBtn" class="danger" ${isQueued ? "" : "disabled"}>Cancel</button>
            <button id="copyJsonBtn" class="ghost">Copy JSON</button>
            ${isTerminal ? `<button id="downloadJsonBtn" class="ghost">Download log</button>` : ""}
            <button id="openInBuilder" class="ghost">Open in Builder</button>
          </div>
          ${d.error ? `<div class="err" style="margin:0 18px 10px">${escapeHtml(d.error)}</div>` : ""}
          <div class="timeline">${stepsHtml || `<div class="empty">Waiting for step logs.</div>`}</div>
        </div>
        <aside>
          <div class="sidebox">
            <h3>Run details</h3>
            <div class="kv">
              <div><span>Created</span><strong>${fmt(d.created_at)}</strong></div>
              <div><span>Started</span><strong>${fmt(d.started_at)}</strong></div>
              <div><span>Finished</span><strong>${fmt(d.finished_at)}</strong></div>
              <div><span>Duration</span><strong>${fmtDuration(d.started_at, d.finished_at)}</strong></div>
              <div><span>Steps</span><strong>${stepCount}</strong></div>
            </div>
          </div>
          <div class="sidebox">
            <h3>Screenshots</h3>
            <div class="shots">
              ${screenshots.length ? screenshots.map(s => {
                const file = basename(s.screenshot_path);
                const url = "/screenshots/" + encodeURIComponent(file);
                return `<a class="shot" href="${url}" data-shot="${url}">
                  <img src="${url}" alt="" loading="lazy">
                  <div style="min-width:0"><strong>${escapeHtml(file)}</strong><div style="color:var(--muted); font-size:12px">Step ${Number(s.step_index) + 1}</div></div>
                </a>`;
              }).join("") : `<div class="empty" style="padding:8px 0; text-align:left">No screenshots recorded.</div>`}
            </div>
          </div>
        </aside>
      </div>
    `;
    $("rerunBtn").addEventListener("click", () => rerun(d));
    $("cancelBtn").addEventListener("click", () => cancelTask(d.id));
    $("copyJsonBtn").addEventListener("click", () => copyJson(d));
    const dl = $("downloadJsonBtn"); if (dl) dl.addEventListener("click", () => downloadJson(d));
    $("openInBuilder").addEventListener("click", () => loadIntoBuilder(d));
    document.querySelectorAll("#detailPanel .shot").forEach(el => {
      el.addEventListener("click", (ev) => { ev.preventDefault(); openLightbox(el.dataset.shot); });
    });
  }

  // ====================================================================
  //  Renderers — Templates / Settings
  // ====================================================================
  function renderTemplates() {
    $("templateList").innerHTML = TEMPLATES.map((tpl, i) => `
      <button class="template" data-i="${i}">
        <div class="icon-bubble violet"><svg width="16" height="16"><use href="#i-templates"/></svg></div>
        <div><strong>${escapeHtml(tpl.name)}</strong><span>${escapeHtml(tpl.summary)}</span></div>
        <span class="badge b-running">${tpl.pipeline.steps.length} steps</span>
      </button>
    `).join("");
    document.querySelectorAll("#templateList .template").forEach(btn => {
      btn.addEventListener("click", () => {
        const tpl = TEMPLATES[parseInt(btn.dataset.i, 10)];
        loadIntoBuilder(tpl.pipeline);
        toast("Loaded \"" + tpl.name + "\" into the builder", "success");
      });
    });
  }

  function renderServerInfo() {
    const h = state.health || {};
    $("serverInfo").innerHTML = [
      ["API status", h.status || "unknown"],
      ["Database", h.database || "unknown"],
      ["Worker", h.worker || "unknown"],
      ["Queue depth", String(h.queue_depth ?? "—")],
      ["Version", h.version || "—"]
    ].map(([k, v]) => `<div><span>${escapeHtml(k)}</span><strong>${escapeHtml(v)}</strong></div>`).join("");
  }

  // ====================================================================
  //  Builder
  // ====================================================================
  function buildPipelineJSON() {
    return {
      name: state.builder.name || "untitled-pipeline",
      steps: state.builder.steps.map(s => {
        const out = { type: s.type, params: { ...(s.params || {}) } };
        if (s.retries !== undefined && s.retries !== "") out.retries = Number(s.retries);
        if (s.retry_delay !== undefined && s.retry_delay !== "") out.retry_delay = Number(s.retry_delay);
        if (s.timeout_seconds !== undefined && s.timeout_seconds !== "") out.timeout_seconds = Number(s.timeout_seconds);
        if (s.on_failure && s.on_failure !== "abort") out.on_failure = s.on_failure;
        return out;
      })
    };
  }

  function syncJsonPreview() {
    $("bJson").value = JSON.stringify(buildPipelineJSON(), null, 2);
  }

  function loadIntoBuilder(pipeline) {
    state.builder.name = pipeline.name || "";
    state.builder.steps = (pipeline.steps || []).map(s => normalizeStep(s));
    $("bName").value = state.builder.name;
    renderBuilder();
    syncJsonPreview();
    setView("builder");
  }

  function normalizeStep(s) {
    const params = (typeof s.params === "object" && s.params) ? s.params : {};
    if (s.type === "hotkey" && Array.isArray(params.keys)) {
      params.keys = params.keys.join(",");
    }
    if (s.type === "click" && Array.isArray(params)) { /* defensive */ }
    return {
      type: s.step_type || s.type || "wait",
      params: params,
      retries: s.retries ?? "",
      retry_delay: s.retry_delay ?? "",
      timeout_seconds: s.timeout_seconds ?? "",
      on_failure: s.on_failure ?? "abort"
    };
  }

  function renderBuilder() {
    const select = $("bAddType");
    if (!select.options.length) {
      select.innerHTML = STEP_TYPES.map(t => `<option value="${t}">${t}</option>`).join("");
    }
    const wrap = $("bSteps");
    if (!state.builder.steps.length) {
      wrap.innerHTML = `<div class="empty">No steps yet. Add one above, or open a template.</div>`;
      return;
    }
    wrap.innerHTML = state.builder.steps.map((s, i) => renderStepRow(s, i)).join("");
    wrap.querySelectorAll(".step-row").forEach(row => {
      const i = Number(row.dataset.i);
      row.querySelectorAll("[data-field]").forEach(input => {
        input.addEventListener("input", (ev) => {
          const field = ev.target.dataset.field;
          const cast = ev.target.dataset.cast;
          let v = ev.target.type === "checkbox" ? ev.target.checked : ev.target.value;
          if (cast === "number" && v !== "") v = Number(v);
          setBuilderField(i, field, v);
        });
      });
      row.querySelector("[data-act='up']")?.addEventListener("click", () => moveStep(i, -1));
      row.querySelector("[data-act='down']")?.addEventListener("click", () => moveStep(i, +1));
      row.querySelector("[data-act='delete']")?.addEventListener("click", () => removeStep(i));
      row.querySelector("[data-act='type']")?.addEventListener("change", (ev) => changeType(i, ev.target.value));
      // drag reorder
      row.draggable = true;
      row.addEventListener("dragstart", (ev) => { ev.dataTransfer.setData("text/plain", String(i)); row.classList.add("dragging"); });
      row.addEventListener("dragend", () => row.classList.remove("dragging"));
      row.addEventListener("dragover", (ev) => ev.preventDefault());
      row.addEventListener("drop", (ev) => {
        ev.preventDefault();
        const from = Number(ev.dataTransfer.getData("text/plain"));
        const to = i;
        if (from === to || isNaN(from)) return;
        const moved = state.builder.steps.splice(from, 1)[0];
        state.builder.steps.splice(to, 0, moved);
        renderBuilder(); syncJsonPreview();
      });
    });
  }

  function renderStepRow(step, i) {
    const def = STEP_FORMS[step.type] || [];
    const params = step.params || {};
    const fields = def.map(f => {
      const id = `f${i}_${f.k}`;
      const v = params[f.k] ?? (f.default ?? "");
      if (f.t === "checkbox") {
        return `<label style="flex-direction:row; align-items:center; gap:8px"><input id="${id}" type="checkbox" data-field="param.${f.k}" ${v ? "checked" : ""}> ${f.k}${f.req ? " *" : ""}</label>`;
      }
      if (f.t === "select") {
        return `<label><span>${f.k}${f.req ? " *" : ""}</span><select data-field="param.${f.k}">${(f.options||[]).map(o => `<option value="${o}" ${v===o?"selected":""}>${o}</option>`).join("")}</select></label>`;
      }
      if (f.t === "textarea") {
        return `<label style="grid-column:1/-1"><span>${f.k}${f.req ? " *" : ""}</span><textarea data-field="param.${f.k}" placeholder="${f.ph||""}" style="min-height:80px">${escapeHtml(v)}</textarea></label>`;
      }
      const type = f.t === "number" ? "number" : "text";
      const step = f.step ? ` step="${f.step}"` : "";
      const cast = f.t === "number" ? ' data-cast="number"' : '';
      return `<label><span>${f.k}${f.req ? " *" : ""}</span><input type="${type}"${step}${cast} data-field="param.${f.k}" placeholder="${f.ph||""}" value="${escapeHtml(v)}"></label>`;
    }).join("");
    const opts = STEP_TYPES.map(t => `<option value="${t}" ${t===step.type?"selected":""}>${t}</option>`).join("");
    return `
      <div class="step-row" data-i="${i}">
        <div class="grip" title="Drag to reorder"><svg width="18" height="18"><use href="#i-grip"/></svg></div>
        <div class="body">
          <div class="head">
            <div class="icon-bubble ${ICON_BUBBLE[step.type] || "blue"}"><svg width="14" height="14"><use href="#s-${step.type}"/></svg></div>
            <select class="type" data-act="type">${opts}</select>
            <span style="color:var(--muted); font-size:12px">step ${i + 1}</span>
          </div>
          <div class="params">${fields || "<span style='color:var(--muted); font-size:12px'>No parameters.</span>"}</div>
          <details>
            <summary>Advanced (retries, timeout, on_failure)</summary>
            <div class="advanced">
              <label><span>retries</span><input type="number" data-cast="number" data-field="retries" value="${escapeHtml(step.retries)}"></label>
              <label><span>retry_delay (s)</span><input type="number" step="0.1" data-cast="number" data-field="retry_delay" value="${escapeHtml(step.retry_delay)}"></label>
              <label><span>timeout_seconds</span><input type="number" step="0.1" data-cast="number" data-field="timeout_seconds" value="${escapeHtml(step.timeout_seconds)}"></label>
              <label><span>on_failure</span>
                <select data-field="on_failure">
                  <option value="abort" ${step.on_failure==="abort"?"selected":""}>abort</option>
                  <option value="continue" ${step.on_failure==="continue"?"selected":""}>continue</option>
                </select>
              </label>
            </div>
          </details>
        </div>
        <div class="controls">
          <button class="tiny ghost" data-act="up" title="Move up"><svg width="12" height="12"><use href="#i-up"/></svg></button>
          <button class="tiny ghost" data-act="down" title="Move down"><svg width="12" height="12"><use href="#i-down"/></svg></button>
          <button class="tiny danger" data-act="delete" title="Delete step"><svg width="12" height="12"><use href="#i-trash"/></svg></button>
        </div>
      </div>
    `;
  }

  function setBuilderField(i, field, v) {
    const step = state.builder.steps[i];
    if (!step) return;
    if (field.startsWith("param.")) {
      const k = field.slice(6);
      if (!step.params) step.params = {};
      if (v === "" || v === undefined || v === null) delete step.params[k];
      else step.params[k] = v;
    } else {
      step[field] = v;
    }
    syncJsonPreview();
  }

  function moveStep(i, dir) {
    const j = i + dir;
    if (j < 0 || j >= state.builder.steps.length) return;
    [state.builder.steps[i], state.builder.steps[j]] = [state.builder.steps[j], state.builder.steps[i]];
    renderBuilder(); syncJsonPreview();
  }
  function removeStep(i) {
    state.builder.steps.splice(i, 1);
    renderBuilder(); syncJsonPreview();
  }
  function changeType(i, type) {
    const step = state.builder.steps[i];
    step.type = type;
    step.params = {};
    renderBuilder(); syncJsonPreview();
  }
  $("bAdd").addEventListener("click", () => {
    const type = $("bAddType").value;
    state.builder.steps.push({ type, params: {}, retries:"", retry_delay:"", timeout_seconds:"", on_failure:"abort" });
    renderBuilder(); syncJsonPreview();
  });
  $("bClear").addEventListener("click", () => {
    state.builder.steps = []; state.builder.name = "";
    $("bName").value = ""; renderBuilder(); syncJsonPreview();
  });
  $("bName").addEventListener("input", (e) => { state.builder.name = e.target.value; syncJsonPreview(); });
  $("bCopy").addEventListener("click", () => {
    navigator.clipboard.writeText($("bJson").value).then(
      () => toast("Pipeline JSON copied", "success"),
      () => toast("Clipboard write blocked", "error")
    );
  });
  $("bImport").addEventListener("click", () => {
    try {
      const obj = JSON.parse($("bJson").value);
      loadIntoBuilder(obj);
      toast("JSON imported", "success");
    } catch (err) { toast("Invalid JSON: " + err.message, "error"); }
  });
  $("bRun").addEventListener("click", async () => {
    let payload;
    try { payload = buildPipelineJSON(); }
    catch (err) { toast(err.message, "error"); return; }
    if (!payload.steps.length) { toast("Add at least one step", "warn"); return; }
    // Convert hotkey "ctrl,s" to ["ctrl","s"] just-in-time.
    payload.steps.forEach(s => {
      if (s.type === "hotkey" && typeof s.params.keys === "string") {
        s.params.keys = s.params.keys.split(",").map(t => t.trim()).filter(Boolean);
      }
    });
    try {
      const body = await api("/run-task", {
        method: "POST",
        headers: { "Content-Type":"application/json" },
        body: JSON.stringify(payload)
      });
      toast("Submitted " + body.task_id.slice(0,8) + "…", "success");
      await loadAll();
      await loadDetail(body.task_id);
    } catch (err) { toast(err.message, "error"); }
  });

  // ====================================================================
  //  Actions
  // ====================================================================
  async function rerun(detail) {
    const payload = {
      name: detail.name + " (rerun)",
      steps: (detail.steps || []).map(s => ({ type: s.step_type, params: s.params }))
    };
    if (!payload.steps.length) { toast("No steps to rerun", "warn"); return; }
    try {
      const body = await api("/run-task", {
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body: JSON.stringify(payload)
      });
      toast("Re-running as " + body.task_id.slice(0,8) + "…", "success");
      await loadAll();
      await loadDetail(body.task_id);
    } catch (err) { toast(err.message, "error"); }
  }
  async function cancelTask(id) {
    try {
      const r = await api("/cancel/" + encodeURIComponent(id), { method:"POST" });
      toast(r.cancelled ? "Cancelled " + id.slice(0,8) : r.message, r.cancelled ? "success" : "warn");
      await loadAll();
    } catch (err) { toast(err.message, "error"); }
  }
  function copyJson(d) {
    navigator.clipboard.writeText(JSON.stringify(d, null, 2)).then(
      () => toast("Task JSON copied", "success"),
      () => toast("Clipboard write blocked", "error")
    );
  }
  function downloadJson(d) {
    const blob = new Blob([JSON.stringify(d, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "task-" + d.id + ".json"; a.click();
    URL.revokeObjectURL(url);
  }
  function openLightbox(url) {
    $("lightboxImg").src = url;
    $("lightbox").classList.add("open");
  }
  $("lightboxClose").addEventListener("click", () => $("lightbox").classList.remove("open"));
  $("lightbox").addEventListener("click", (e) => { if (e.target.id === "lightbox") $("lightbox").classList.remove("open"); });

  // ====================================================================
  //  Filters / search
  // ====================================================================
  $("statusChips").addEventListener("click", (ev) => {
    const chip = ev.target.closest(".chip");
    if (!chip) return;
    document.querySelectorAll("#statusChips .chip").forEach(c => c.setAttribute("aria-pressed","false"));
    chip.setAttribute("aria-pressed","true");
    state.filterStatus = chip.dataset.status || "";
    loadTasks(false).catch(err => toast(err.message, "error"));
  });
  let searchTimer = null;
  $("searchInput").addEventListener("input", (ev) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.query = ev.target.value.trim();
      loadTasks(false).catch(err => toast(err.message, "error"));
    }, 220);
  });

  $("refreshBtn").addEventListener("click", () => loadAll().catch(err => toast(err.message, "error")));

  // ====================================================================
  //  Keyboard shortcuts
  // ====================================================================
  document.addEventListener("keydown", (ev) => {
    if (ev.target.matches("input,textarea,select")) {
      if ((ev.ctrlKey || ev.metaKey) && ev.key === "Enter" && state.view === "builder") {
        ev.preventDefault(); $("bRun").click();
      }
      return;
    }
    if (ev.key === "Escape") $("lightbox").classList.remove("open");
    else if (ev.key === "r" || ev.key === "R") loadAll().catch(() => {});
    else if (ev.key === "t" || ev.key === "T") $("themeBtn").click();
    else if (ev.key === "n" || ev.key === "N") setView("builder");
    else if (ev.key === "/") { ev.preventDefault(); setView("tasks"); $("searchInput").focus(); }
  });

  // ====================================================================
  //  Boot
  // ====================================================================
  loadSettings();
  syncJsonPreview();
  renderBuilder();

  function startPolling() {
    clearInterval(state.timer);
    state.timer = setInterval(() => loadAll().catch(() => {}), state.pollMs);
  }
  loadAll().then(() => { startPolling(); renderDashboard(); }).catch(err => toast(err.message, "error"));
})();
</script>
</body>
</html>
"""
