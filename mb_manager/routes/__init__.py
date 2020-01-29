from aiohttp import web

from .webhooks import routes as webhook_routes


def setup(app: web.Application) -> None:
    app.add_routes(webhook_routes)
