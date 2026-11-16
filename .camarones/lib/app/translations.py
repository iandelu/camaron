"""Translations of pages: mark a translation as made from today's version of its page (`camaron translated`)."""
from __future__ import annotations

from pathlib import Path

from lib.app import services
from lib.common import DOCS
from lib.domain.docs import frontmatter, logical_paths


def translated(files: list[str]) -> list[str]:
    canon = dict(services.current().docs.iter_docs())
    done = []
    for p in files:
        f = services.current().docs.resolve(p)
        rel = f.relative_to(DOCS / "i18n")
        lang, logical = rel.parts[0], Path(*rel.parts[1:]).as_posix()
        if logical not in canon and (alias := logical_paths.old_wiki_path(logical)) in canon \
                and services.current().docs.translation_file(alias, lang).resolve() == f.resolve():
            logical = alias                       # a wiki page's translation kept at its pre-4.81 path
        if logical not in canon:
            raise RuntimeError(f"{p}: no canonical doc at {logical}")
        _, cbody = frontmatter.split_fm(canon[logical].read_text(encoding="utf-8"))
        fm, body = frontmatter.split_fm(f.read_text(encoding="utf-8"))
        fm["x-translation-of"] = {"path": logical, "lang": lang, "body_sha": frontmatter.body_sha(cbody)}
        f.write_text(frontmatter.join_fm(fm, body), encoding="utf-8", newline="\n")
        done.append(f"{p} <- {logical}")
    return done
