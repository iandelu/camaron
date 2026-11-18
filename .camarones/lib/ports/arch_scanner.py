"""ArchScanner: what the app asks of the first-look scan (quickarch): the repos, datastores, brokers, identity providers
and relations found in the code, each with the `repo:path#Ln` anchors it was read from."""
from __future__ import annotations

from typing import Protocol


class ArchScanner(Protocol):
    def scan(self) -> dict: ...
