import os
import logging

from typing import Any, Mapping

import uvloop
import sentry_sdk

from sentry_sdk.integrations.aiohttp import AioHttpIntegration

from .app import run_app
from .cli import args
from .config import Config
from .logger import setup as setup_logger

uvloop.install()

log = logging.getLogger(__name__)


if __name__ == "__main__":
    setup_logger()

    log.info(f"running on version {os.environ.get('GIT_COMMIT', 'UNSET')}")

    config_format: Mapping[str, Any]

    config = Config()

    if config["sentry"]["enabled"]:
        log.info("initializing sentry")
        sentry_sdk.init(
            dsn=config["sentry"]["dsn"],
            debug=config["sentry"]["debug"],
            integrations=[AioHttpIntegration()],
            send_default_pii=True,
        )
    else:
        log.info("skipping sentry initialization")

    if args.populate_db:
        # from .utils.populate_db import populate_db
        #
        # populate_db(config)
        pass
    else:
        run_app(config)
