"""The Docs chat (`/api/app/`, app token only): the runners installed on this machine with their models, and the choice
the panel opens with."""
from __future__ import annotations

from lib.interfaces.http.messages import Request, Response, json_response
from lib.interfaces.http.router import Access, route


@route("GET", "/api/app/chat/models", access=Access.APP)
def get_models(req: Request) -> Response:
    from lib import chat
    offered = chat.models()                    # once: listing the Ollama tags runs a process
    return json_response({"runners": offered, "choice": chat.default_choice(offered), "ai": chat.ai_enabled()})
