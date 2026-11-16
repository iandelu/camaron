// Pure pieces of the Architecture view's element panel.

// Elements still to review (an AI draft, or never confirmed) come first; confirmed ones go to a folded section. One
// tagged both ways (#ai-draft left on a confirmed element) is still to review.
export function splitElements(elements) {
  const done = (e) => e.confirmed && !e.draft
  return { pending: elements.filter((e) => !done(e)), confirmed: elements.filter(done) }
}

// Where a view's file is, as a person reads it: under docs/architecture, or in the service repo folder workspace.yaml
// names for the model (`c4Source` in the docs tree, `<repo>:<path>`; lib/domain/architecture.py).
export function viewFile(tree, file) {
  const src = tree?.c4Source
  if (!src) return `architecture/${file}`
  return src.endsWith(':.') ? `${src.slice(0, -1)}${file}` : `${src}/${file}`
}
