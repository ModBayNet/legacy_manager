import logging

from aiohttp import web
from aiohttp.abc import AbstractAccessLogger

from .tasks import setup as setup_tasks
from .config import Config
from .docker import setup as setup_docker
from .routes import setup as setup_routes
from .migrator import migrate
from .db.edgedb import setup as setup_edgedb

log = logging.getLogger(__name__)

SHUTDOWN_DELAY = 5


class AccessLogger(AbstractAccessLogger):
    def log(self, req: web.BaseRequest, resp: web.StreamResponse, time: float) -> None:
        # For some reason req.remote does not point to X-Forwarded-For ip. It does in
        # handlers though
        ip = req.headers.get("X-Forwarded-For", req.remote)

        self.logger.info(
            f"{ip} '{req.headers.get('Referer', '-')}' "
            f"'{req.headers.get('User-Agent', '-')}' {req.method} {req.path} "
            f"{resp.status} {round(time * 1000)}ms"
        )


async def on_startup(app: web.Application) -> None:
    # since aiohttp runs handlers sequentially, edgedb connection should be created
    # before running migrations
    await migrate(app)


def init_app(app: web.Application) -> None:
    log.debug("registering routes")

    setup_routes(app)

    setup_docker(app)
    setup_edgedb(app)

    setup_tasks(app)

    app.on_startup.append(on_startup)


async def stop_app(app: web.Application) -> None:
    # await req.app.shutdown() is broken since aiohttp 3.4 it seems:
    # https://github.com/aio-libs/aiohttp/pull/3662
    # this won't stop app
    await app.shutdown()
    # NOTE: this causes cleanup to be called twice, but in case app was not fully loaded
    # KeyboardInterrupt won't call it at all so this is just a safety measure
    await app.cleanup()

    # wait for cleanup because above functions are partially broken
    #
    # It looks like using asyncio.sleep is not safe here, app just hangs, context never
    # swithes back after this line
    # log.info(f"stopping in {SHUTDOWN_DELAY} seconds")
    # await asyncio.sleep(SHUTDOWN_DELAY)

    # since we run as PID 1, os.kill(os.getpid(), signal.SIGKILL) will not work.
    # os.kill(os.getpid(), signal.SIGTERM) will work, but this is dirty exit
    # without cleanup.
    # KeyboardInterrupt hack triggers cleanup in aiohttp and terminates app
    #
    # NOTE: this still triggers exception handling for some reason and it gets printed
    # to logs and reported to Sentry
    raise KeyboardInterrupt


def run_app(config: Config) -> None:
    app = web.Application()

    app["config"] = config

    # avoid import loop
    app["shutdown_handler"] = lambda: stop_app(app)

    init_app(app)

    app_config = app["config"]["manager"]

    web.run_app(
        app,
        host=app_config["host"],
        port=app_config["port"],
        access_log_class=AccessLogger,
        # access_log_format="%{X-Forwarded-For}i '%{Referer}i' '%{User-Agent}i' %r %s %Tf",
    )
