// Team › Skills, pure: `skills list --json` as the card shows it. A skill with no icon in the kit's catalog gets the
// puzzle piece; a pack's summary in the app's language, English when the catalog has no line in it.
export const NO_ICON = '🧩'
const ORIGIN = { kit: 'tm.skKit', team: 'tm.skTeam', 'team-only': 'tm.skTeamOnly' }

export function skillsView(data, lang = 'es') {
  const rows = (data?.skills || []).map((s) => ({
    name: s.name,
    icon: s.icon || NO_ICON,
    description: s.description || '',
    origin: s.pack ? 'tm.skPack' : (ORIGIN[s.origin] || 'tm.skTeamOnly'),
    pack: s.pack || null,
    project: s.project !== 'off',
    machine: s.machine !== 'off',
    waiting: !!s.needs_trust,
  }))
  const packs = (data?.available || []).map((p) => ({
    name: p.name,
    title: p.title || p.name,
    icon: p.icon || NO_ICON,
    summary: (p.summary && (p.summary[lang] || p.summary.en)) || '',
    license: p.license || '',
    runsCode: !!p.runs_code,
    skills: p.skills || [],
  }))
  return { rows, packs }
}

// The command each switch runs: the project's writes workspace.yaml for the team, this machine's only this machine.
export function switchArgs(row, scope) {
  const on = scope === 'machine' ? row.machine : row.project
  return { action: on ? 'disable' : 'enable', args: [row.name], ...(scope === 'machine' ? { machine: true } : {}) }
}
