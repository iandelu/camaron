import { Place } from '../Place.jsx'
import { useHash } from '../hooks.js'
import { repoPage, viewOf } from '../nav.js'
import Plan from './Plan.jsx'
import RepoPage from './RepoPage.jsx'
import Summary from './Summary.jsx'

// A repo's page is a view of Flow that draws no place (no title, no tabs): a way back and its bento.
export default function Flow(props) {
  const hash = useHash()
  const view = viewOf(hash, 'flow')
  if (view === 'repo') {
    const name = repoPage(hash)
    return <RepoPage key={name ?? ''} srv={props.srv} app={props.app} name={name} />
  }
  return (
    <Place section="flow" view={view} wide={view === 'plan'}>
      {view === 'plan' ? <Plan {...props} /> : <Summary {...props} />}
    </Place>
  )
}
