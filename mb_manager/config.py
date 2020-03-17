from __future__ import annotations

import os
import sys
import logging

from typing import Any, Dict

from ruamel.yaml import YAML

log = logging.getLogger(__name__)

DEFAULT_FILENAME = "config.yaml"

CONFIG_FORMAT = {
    "manager": {"host": str, "port": int},
    "supervisor": {"healthcheck_url": str, "worker_container_name": str},
    "docker": {
        "socket": str,
        "registry": {
            "address": str,
            "manager": {"username": str, "password": str},
            "worker": {"username": str, "password": str},
        },
    },
    "edgedb": {
        "host": str,
        "port": int,
        "user": str,
        "database": str,
        "password": str,
    },
    "sentry": {"enabled": bool, "debug": bool, "dsn": str},
    "webhooks": {"gitlab": {"secret": str}},
}

ENV_PREFIX = "MODBAY_"

_EMPTY = object()


class EnvTag:
    yaml_tag = "!env"

    def from_yaml(constructor: EnvTag, node: Any) -> str:
        if node.value not in os.environ:
            log.warn(f"{node.value} env variable is missing, using ''")

        return os.environ.get(node.value, "")


class Config:
    def __init__(self) -> None:
        config = self._read_file()

        self._data = self.validate(config)

    @staticmethod
    def _read_file() -> Any:
        path = DEFAULT_FILENAME

        if not os.path.exists(path):
            log.fatal(
                f"Config file {os.path.relpath(path)} is missing. "
                f"Example config file is located at {os.path.join(os.path.relpath('.'), 'config.example.yaml')}"
            )

            sys.exit(1)

        yaml = YAML(typ="safe")
        yaml.register_class(EnvTag)

        with open(path, "r") as f:
            return yaml.load(f)

    @staticmethod
    def validate(config: Any) -> Any:
        """Validate config."""

        Config._detect_missing(config, CONFIG_FORMAT)

        return Config._validate(config, CONFIG_FORMAT)

    @staticmethod
    def _detect_missing(cfg: Any, fmt: Any, *path: str) -> Any:
        """Check for missing config keys."""

        # node
        if isinstance(fmt, dict):
            filled_node: Dict[str, Any] = {}
            for name, node in fmt.items():
                # entire node is missing
                if cfg is _EMPTY:
                    cfg = {}

                filled_node[name] = Config._detect_missing(
                    cfg.get(name, _EMPTY), node, *path, name
                )

            return filled_node

        # leaf
        if cfg is not _EMPTY:
            return cfg

        log.fatal(f"{'.'.join(path)} key is missing from config/env")

        sys.exit(1)

    @staticmethod
    def _validate(cfg: Any, fmt: Any, *path: str) -> Any:
        """Validate config using format."""

        # leaf
        if not isinstance(cfg, dict):
            try:
                return fmt(cfg)
            except Exception as e:
                log.fatal(f"Failed to convert {'.'.join(path)} to type {cfg}: {e}")

                sys.exit(1)

        # node
        validated_node = {}
        for name, node in cfg.items():
            if name not in fmt:
                log.warn(f"Unknown config key: {'.'.join([*path, name])}")

                continue

            validated_node[name] = Config._validate(node, fmt[name], *path, name)

        return validated_node

    def __getitem__(self, key: str) -> Any:
        return self._data[key]
