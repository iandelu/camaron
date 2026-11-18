import { Place } from '../Place.jsx'
import { useHash } from '../hooks.js'
import { viewOf } from '../nav.js'
import Plan from './Plan.jsx'
import Summary from './Summary.jsx'

export default function Flow(props) {
  const view = viewOf(useHash(), 'flow')
  return (
    <Place section="flow" view={view} wide={view === 'plan'}>
      {view === 'plan' ? <Plan {...props} /> : <Summary {...props} />}
    </Place>
  )
}
