import { useState } from 'react'
import { Button } from '@camaron/ui'
import { Page } from '../parts.jsx'
import { Repo } from './TeamStrip.jsx'
import Commands from './Commands.jsx'
import { t } from '../i18n.js'
import { Plugins, Skills, Trust } from './SettingsTeam.jsx'

// The team by task: the team's cam-docs repo and sharing with it (where it stands, share now), the agent config and
// hooks that came with it and this machine has not approved, the agents' skills and the plugins. The board and CI are
// the portal's.
export default function Team({ srv, jobs }) {
  const [tick, setTick] = useState(0)          // a pack added below arrives in the Trust card to approve
  return (
    <Page title={t('nav.team')}>
      <Repo srv={srv} jobs={jobs} />
      <Trust srv={srv} jobs={jobs} tick={tick} />
      <Skills srv={srv} jobs={jobs} onChange={() => setTick((n) => n + 1)} />
      <Plugins srv={srv} jobs={jobs} />
      <div className="row">
        <Button size="sm" variant="ghost" href="../#/kanban">{t('tm.board')}</Button>
        <Button size="sm" variant="ghost" href="../#/ci">{t('tm.ci')}</Button>
      </div>
      <Commands srv={srv} jobs={jobs} section="team" />
    </Page>
  )
}

