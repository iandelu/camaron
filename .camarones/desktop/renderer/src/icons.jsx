const SHAPES = {
  language: <><polyline points="8 7 3 12 8 17" /><polyline points="16 7 21 12 16 17" /></>,
  framework: <><path d="M12 3 3 8l9 5 9-5z" /><path d="m3 13 9 5 9-5" /><path d="m3 17.5 9 5 9-5" /></>,
  build: <><path d="M21 8 12 3 3 8v8l9 5 9-5z" /><path d="m3 8 9 5 9-5" /><path d="M12 13v8" /></>,
  data: <><ellipse cx="12" cy="5.5" rx="8" ry="2.5" /><path d="M4 5.5v13c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5v-13" /><path d="M4 12c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5" /></>,
  container: <><rect x="3" y="6" width="18" height="12" rx="2" /><path d="M8 6v12M12 6v12M16 6v12" /></>,
  ci: <><circle cx="6" cy="5" r="2" /><circle cx="6" cy="19" r="2" /><circle cx="18" cy="9" r="2" /><path d="M6 7v10" /><path d="M18 11c0 4-6 3-12 6" /></>,
  sonar: <><path d="M4 18a8 8 0 1 1 16 0" /><path d="m12 18 4-5" /><circle cx="12" cy="18" r="1" /></>,
  activity: <polyline points="3 12 7 12 10 5 14 19 17 12 21 12" />,
  libs: <><path d="M12 3 4 6v6c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V6z" /><path d="m9 12 2 2 4-4" /></>,
  docs: <><path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z" /><path d="M4 19V5" /><path d="M9 8h6" /></>,
  arch: <><rect x="3" y="3" width="7" height="6" rx="1" /><rect x="14" y="3" width="7" height="6" rx="1" /><rect x="8.5" y="15" width="7" height="6" rx="1" /><path d="M6.5 9v3h11V9M12 12v3" /></>,
  work: <><rect x="3" y="4" width="5" height="16" rx="1" /><rect x="9.5" y="4" width="5" height="10" rx="1" /><rect x="16" y="4" width="5" height="13" rx="1" /></>,
}

export function Icon({ name }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true" focusable="false">{SHAPES[name]}</svg>
  )
}
