import asyncio
import logging

from aiohttp import web

from ..docker import Docker

log = logging.getLogger(__name__)

routes = web.RouteTableDef()

# TODO: avoid hardcoding these
MANAGER_DOCKER_IMAGE = "registry.gitlab.com/modbay1/manager"
WORKER_DOCKER_IMAGE = "registry.gitlab.com/modbay1/backend"

MANAGER_CONTAINER_NAME = "modbay-manager.service"
WORKER_CONTAINER_NAME = "modbay-backend.service"


def _validate_request(req: web.Request) -> None:
    remote_token = req.headers.get("X-Gitlab-Token")
    if remote_token is None:
        raise web.HTTPBadRequest(text="X-Gitlab-Token header is missing")

    local_token = req.app["config"]["webhooks"]["gitlab"]["secret"]

    if local_token != remote_token:
        raise web.HTTPUnauthorized(text="Tokens do not match")

    event_type = req.headers.get("X-Gitlab-Event")
    log.info(f"gitlab event: {event_type}")

    if event_type != "Pipeline Hook":
        raise web.HTTPSuccessful()


@routes.post("/wh/gitlab/manager")
async def gitlab_manager_wh(req: web.Request) -> web.Response:
    asyncio.create_task(update_self(req))
    _validate_request(req)

    hook_data = await req.json()

    if hook_data["object_attributes"]["status"] == "success":
        asyncio.create_task(update_self(req))

    return web.Response()


@routes.post("/wh/gitlab/backend")
async def gitlab_backend_wh(req: web.Request) -> web.Response:
    asyncio.create_task(update_worker(req))
    _validate_request(req)

    hook_data = await req.json()

    if hook_data["object_attributes"]["status"] == "success":
        asyncio.create_task(update_worker(req))

    return web.Response()


async def update_self(req: web.Request) -> None:
    log.info("updating self")

    docker = req.config_dict["docker"]

    await docker.pull(MANAGER_DOCKER_IMAGE)
    await req.config_dict["shutdown_handler"]()


async def update_worker(req: web.Request) -> None:
    log.info("updating worker")

    docker = req.config_dict["docker"]

    await docker.pull(WORKER_DOCKER_IMAGE)
    await docker.restart(MANAGER_CONTAINER_NAME)
