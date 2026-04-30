"""Vault KV v2 secret loader.

Called at module level in main.py BEFORE build_app() so that os.environ
is populated before get_settings() constructs and lru_cache's Settings.

pydantic-settings priority: os.environ > .env — so vault values win.
Fallback: if VAULT_ADDR is absent, this module is never called and
the backend reads secrets directly from .env as before.
"""

from __future__ import annotations

import logging
import os

import hvac  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

_VAULT_MOUNT = "secret"
_VAULT_PATH = "travel-planner"


def load_vault_secrets(vault_addr: str, vault_token: str) -> None:
    """Fetch secrets from Vault KV v2 and inject into os.environ.

    Args:
        vault_addr:  Vault server URL, e.g. "http://vault:8200".
        vault_token: Token with read access to secret/travel-planner.

    Raises:
        hvac.exceptions.VaultError: Vault unreachable or token invalid.
            Propagated so the process refuses to start rather than running
            with missing secrets.
    """
    client = hvac.Client(url=vault_addr, token=vault_token)

    response = client.secrets.kv.v2.read_secret_version(
        path=_VAULT_PATH,
        mount_point=_VAULT_MOUNT,
        raise_on_deleted_version=True,
    )

    secrets: dict[str, str] = response["data"]["data"]
    injected: list[str] = []

    for key, value in secrets.items():
        os.environ[key] = str(value)
        injected.append(key)

    # Log key names only — never values.
    logger.info(
        "vault.secrets_loaded path=%s keys=%s",
        f"{_VAULT_MOUNT}/{_VAULT_PATH}",
        sorted(injected),
    )
