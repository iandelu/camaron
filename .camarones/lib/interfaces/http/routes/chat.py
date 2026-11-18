"""The Docs chat (`/api/app/`, app token only): the runners installed on this machine with their models, the choice
the panel opens with, and one turn as a job the app follows."""
from __future__ import annotations

from lib.interfaces.http.jobs import start_job
from lib.interfaces.http.messages import Request, Response, json_response
from lib.interfaces.http.router import Access, route


@route("GET", "/api/app/chat/models", access=Access.APP)
def get_models(req: Request) -> Response:
    from lib import chat
    offered = chat.models()                    # once: listing the Ollama tags runs a process
    return json_response({"runners": offered, "choice": chat.default_choice(offered), "ai": chat.ai_enabled()})


@route("POST", "/api/app/chat", access=Access.APP, by=False)
def post_chat(req: Request) -> Response:                # writes nothing, so no `by`: any JSON body reaches check
    from lib import chat
    try:
        runner, model, q, history = chat.check(req.body)        # refused here, before a job exists
    except (ValueError, RuntimeError) as e:
        return json_response({"error": str(e)}, 400)
    return json_response(start_job("chat", "chat", lambda log: chat.turn(runner, model, q, history, log), quiet=True))
