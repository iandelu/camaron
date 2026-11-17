import { useEffect, useRef, useState } from 'react'
import { Aviso, Button } from '@camaron/ui'
import { postJSON } from '../api.js'
import { confirmedMeanwhile, newPagePath, pageConflict } from './docpage.js'
import { drawMermaid, render } from '../content/doc.js'
import { core } from '../core.js'


// Edit a page in its Markdown with a live preview; saving can commit it (cam-docs is a git repo). The save names the
// version the editor opened (`d.sha`): if the page changed meanwhile (another tab, an agent), the server refuses it
// and the text stays here, to save over the change or to copy and cancel. A confirmation that landed meanwhile is
// named, since saving over it drops it.
export default function Editor({ d, onDone }) {
  const t = core.t
  const lang = core.lang()
  const [src, setSrc] = useState(d.raw || `---\ntitle: ${d.title}\n---\n\n# ${d.title}\n`)
  const [msg, setMsg] = useState('')
  const [commit, setCommit] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [conflict, setConflict] = useState(null)        // when a save was refused: { sha the page has now, confirmedBy }
  const preview = useRef(null)

  useEffect(() => {                                     // the preview follows the text after a short pause
    const h = setTimeout(() => {
      const el = render(src, d.path)
      preview.current.replaceChildren(el)
      drawMermaid(el)
    }, 250)
    return () => clearTimeout(h)
  }, [src])

  const save = async (sha = d.sha) => {
    setBusy(true)
    setError('')
    setConflict(null)
    try {
      try {
        await postJSON('doc', { path: d.path, lang, raw: src, sha })
      } catch (e) {
        const now = pageConflict(e)
        if (now) { setConflict({ sha: now, confirmedBy: confirmedMeanwhile(d, e.data) }); setBusy(false); return }
        throw e.status === 409 ? new Error(t('pageBusy')) : e
      }
      if (commit) {
        const c = await postJSON('commit', { message: msg || `edit ${d.path}` })
        core.toast(c.committed ? `${t('savedCommitted')}: ${c.head}` : t('nothingToCommit'))
      } else core.toast(t('saved'))
      await core.reload()
      const href = core.hrefFor(d.path)
      if (location.hash === href) window.CamaronShell.go(); else location.hash = href
    } catch (e) { setError(e.message); setBusy(false) }
  }
  return (
    <div className="page wide editing">
      <h1>{t('editing')}: {d.title}</h1>
      <div className="meta"><code>{d.file}</code>{lang && <span className="small muted"> · {t('translation')} {lang}</span>}</div>
      {d.trust === 'confirmed' && <Aviso tone="warn" title={t('confirmedWarn')} />}
      {error && <Aviso tone="error" title={t('error')} detail={error} />}
      {conflict && <Aviso tone="warn" title={t('editConflict')}
        action={<Button disabled={busy} onClick={() => save(conflict.sha)}>{t('saveOver')}</Button>}>
        {t('editConflictHelp')}
        {conflict.confirmedBy !== null && <> {t('editConflictConfirmed', { by: conflict.confirmedBy || '?' })}</>}
      </Aviso>}
      <div className="editor">
        <textarea value={src} onChange={(e) => setSrc(e.target.value)} spellCheck="true" aria-label={t('editing')} />
        <div className="preview" ref={preview}></div>
      </div>
      <div className="row">
        <input className="cu-input" value={msg} onChange={(e) => setMsg(e.target.value)} placeholder={t('commitMsg')}
          aria-label={t('commitMsg')} style={{ flex: 1, minWidth: '14rem' }} />
        <label><input type="checkbox" checked={commit} onChange={(e) => setCommit(e.target.checked)} /> {t('commitBox')}</label>
        <Button variant="primary" disabled={busy} onClick={() => save()}>{t('save')}</Button>
        <Button variant="ghost" onClick={onDone}>{t('cancel')}</Button>
      </div>
    </div>
  )
}

// #/new: a page's title and where it goes; once created it opens in the editor.
export function NewPage() {
  const t = core.t
  const [title, setTitle] = useState('')
  const [path, setPath] = useState('')
  const [created, setCreated] = useState(null)
  const [error, setError] = useState('')
  if (created) return <Editor d={created} onDone={() => { location.hash = core.hrefFor(created.path) }} />
  const create = async () => {
    try {
      const d = await postJSON('new', { path, title })
      await core.reload()
      history.replaceState(null, '', core.hrefFor(d.path))
      setCreated(d)
    } catch (e) { setError(e.message) }
  }
  return (
    <div className="page">
      <h1>{t('newPage').replace('+ ', '')}</h1>
      {error && <Aviso tone="error" title={t('error')} detail={error} />}
      <div className="box doc-panel">
        <input className="cu-input" value={title} placeholder={t('newTitle')} aria-label={t('newTitle')}
          onChange={(e) => { setTitle(e.target.value); setPath(newPagePath(e.target.value)) }} />
        <input className="cu-input" value={path} placeholder={t('newPath')} aria-label={t('newPath')} onChange={(e) => setPath(e.target.value)} />
        <div className="row"><Button variant="primary" disabled={!title.trim() || !path.trim()} onClick={create}>{t('create')}</Button></div>
      </div>
    </div>
  )
}
