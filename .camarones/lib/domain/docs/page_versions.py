"""Which version of a page a writer started from. A page's `sha` is the hash of its whole text as read (front matter
included: a confirmation landing meanwhile is a change too); a confirmation vouches for the body, so it compares
`frontmatter.body_sha` instead. A writer whose version is not the file's any more gets a `PageConflict`. Pure."""
from __future__ import annotations

import hashlib


def text_sha(text: str) -> str:
    """The version of a page's text as read (universal newlines, so the same on every OS); "" for a missing file."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class PageConflict(Exception):
    """The page changed since the writer read it: nothing was written. `field` names the version compared (`sha` or
    `body_sha`) and `now` is the one the file has, so the writer can reload or choose to write over it."""

    def __init__(self, path: str, field: str, now: str):
        self.path, self.field, self.now = path, field, now
        super().__init__(f"{path} changed since you opened it (another tab, a person or an agent saved it): "
                         "reload it to see the change")
