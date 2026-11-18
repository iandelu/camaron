"""The Docs chat (`/api/app/`, app token only): the runners installed on this machine with their models, the choice
the panel opens with, and one turn as a job the app follows."""
from __future__ import annotations

from lib.interfaces.http.jobs import JOB_LOCK, JOBS, claim_job, run_job
from lib.interfaces.http.messages import Request, Response, json_response
from lib.interfaces.http.router import Access, route


@route("GET", "/api/app/chat/models", access=Access.APP)
def get_models(req: Request) -> Response:
    from lib import chat
    offered = chat.models()                    # once: listing the Ollama tags runs a process
    return json_response({"runners": offered, "choice": chat.default_choice(offered), "ai": chat.ai_enabled()})


@route("POST", "/api/app/chat", access=Access.APP, by=False)
def post_chat(req: Request) -> Response:                # writes no `by`-attributed data, so any JSON body reaches check
    """One turn at a time: a turn sent while another runs is refused, never attached to it, or it would be handed that
    turn's answer (the app's Clear drops a turn the server still runs)."""
    from lib import chat
    try:
        runner, model, q, history = chat.check(req.body)        # refused here, before a job exists
    except (ValueError, RuntimeError) as e:
        return json_response({"error": str(e)}, 400)
    with JOB_LOCK:
        if any(j["kind"] == "chat" and j["status"] == "running" for j in JOBS.values()):
            return json_response({"error": "busy: a chat turn is still running"}, 409)
        job = claim_job("chat", "chat", quiet=True)
    return json_response(run_job(job, lambda log: chat.turn(runner, model, q, history, log)))
