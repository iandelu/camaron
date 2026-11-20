"""The desktop app's repo page and the Summary's repo cards (GET /api/app/repo, GET /api/app/repos, app token only)."""
from __future__ import annotations

from lib.app import repo_dashboard
from lib.interfaces.http.messages import Request, Response, json_response
from lib.interfaces.http.router import Access, route


@route("GET", "/api/app/repo", access=Access.APP)
def get_repo(req: Request) -> Response:
    found = repo_dashboard.repo(req.query.get("name", ""))
    return json_response(found) if found else json_response({"error": "unknown repo"}, 404)


@route("GET", "/api/app/repos", access=Access.APP)
def get_repos(req: Request) -> Response:
    return json_response(repo_dashboard.repos())
