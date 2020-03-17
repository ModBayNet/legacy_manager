import logging

import aiohttp

from aiohttp import web

from .task import BaseTask
from ..docker import Docker, DockerException

# add class into this list to enable task
__all__ = (
    "HTTPSupervisor",
    "DockerSupervisor",
)

log = logging.getLogger(__name__)

WORKER_IMAGE_NAME = "modbay1/worker"


class HTTPSupervisor(BaseTask):
    interval = 60
    alert_at = 2

    async def setup(self, app: web.Application) -> None:
        await super().setup(app)

        self._streak = 0

        self._session = aiohttp.ClientSession()

        self._healthcheck_url = app["config"]["supervisor"]["healthcheck_url"]

    async def stop(self) -> None:
        await self._session.close()

    async def run_once(self) -> None:
        try:
            async with self._session.get(self._healthcheck_url) as r:
                if r.status == 200:
                    self._streak = 0

                    return

                self.increase_streak()

                if self._streak >= self.alert_at:
                    log.error(f"{r.method} {r.url}: {r.status}")
        except aiohttp.ClientConnectionError:
            self.increase_streak()

            if self._streak >= self.alert_at:
                log.exception("service unreachable")

    def increase_streak(self) -> None:
        """Used for Sentry breadcrumbs."""

        self._streak += 1

        log.warning(f"subsequent {self.__class__.__name__} fail streak: {self._streak}")


class DockerSupervisor(BaseTask):
    interval = 5

    async def setup(self, app: web.Application) -> None:
        await super().setup(app)

        self._app = app
        self._docker: Docker = app["docker"]
        self._container_name = app["config"]["supervisor"]["worker_container_name"]

    async def run_once(self) -> None:
        image_missing = False

        try:
            await self._docker.wait(self._container_name, condition="removed")
        except DockerException as e:
            if e.status == 404:
                if "no such container" in str(e).lower():
                    log.warning(
                        f"container {self._container_name} does not exist, creating"
                    )
                else:
                    image_missing = True
            else:
                log.exception("error waiting container")

        HTTPSupervisor.pause()
        if image_missing:
            log.warning("image does not exist, pulling and creating container")
            await self._docker.pull(
                f"{self._docker.registry_address}/{WORKER_IMAGE_NAME}",
                registry_credentials=self._app["config"]["docker"]["registry"][
                    "worker"
                ],
            )

        await self._create_container()
        HTTPSupervisor.unpause()

    # TODO: move to Docker class
    async def _create_container(self) -> None:
        create_params = {"name": self._container_name}
        create_body = {
            "User": "root",  # TODO: do not use root?
            "Cmd": ("-v", "debug"),
            "Image": "registry.gitlab.com/modbay1/worker",
            "HostConfig": {
                "Binds": ("/home/modbay/worker_config.yaml:/code/config.yaml",),
                "PortBindings": {
                    "8080/tcp": ({"HostIp": "127.0.0.1", "HostPort": "8080"},)
                },
                "AutoRemove": True,
            },
        }

        await self._docker.request(
            "POST", "/containers/create", params=create_params, body=create_body
        )
        await self._docker.request(
            "POST", f"/containers/{self._container_name}/start",
        )
