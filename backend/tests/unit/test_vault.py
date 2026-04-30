"""Unit tests for app/core/vault.py — no real Vault server required."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_hvac(secrets: dict[str, str]) -> MagicMock:
    mock_hvac = MagicMock()
    mock_client = MagicMock()
    mock_hvac.Client.return_value = mock_client
    mock_client.secrets.kv.v2.read_secret_version.return_value = {
        "data": {"data": secrets}
    }
    return mock_hvac


class TestLoadVaultSecrets:
    def test_injects_secrets_into_os_environ(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Vault secrets are written into os.environ."""
        mock_hvac = _make_mock_hvac(
            {"POSTGRES_PASSWORD": "secret123", "JWT_SECRET": "jwt-val"}
        )
        for key in ("POSTGRES_PASSWORD", "JWT_SECRET"):
            monkeypatch.delenv(key, raising=False)

        import app.core.vault as vault_mod

        with patch.object(vault_mod, "hvac", mock_hvac):
            vault_mod.load_vault_secrets("http://vault:8200", "dev-root-token")

        assert os.environ["POSTGRES_PASSWORD"] == "secret123"
        assert os.environ["JWT_SECRET"] == "jwt-val"

    def test_calls_correct_vault_path(self) -> None:
        """Uses mount 'secret' and path 'travel-planner'."""
        mock_hvac = _make_mock_hvac({})

        import app.core.vault as vault_mod

        with patch.object(vault_mod, "hvac", mock_hvac):
            vault_mod.load_vault_secrets("http://vault:8200", "token")

        mock_hvac.Client.return_value.secrets.kv.v2.read_secret_version.assert_called_once_with(
            path="travel-planner",
            mount_point="secret",
            raise_on_deleted_version=True,
        )

    def test_vault_error_propagates(self) -> None:
        """VaultError bubbles up so startup fails loudly."""
        mock_hvac = _make_mock_hvac({})
        mock_hvac.Client.return_value.secrets.kv.v2.read_secret_version.side_effect = (
            Exception("403 permission denied")
        )

        import app.core.vault as vault_mod

        with patch.object(vault_mod, "hvac", mock_hvac):
            with pytest.raises(Exception, match="403"):
                vault_mod.load_vault_secrets("http://vault:8200", "bad-token")

    def test_does_not_log_secret_values(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Log output contains key names but NOT secret values."""
        import logging

        mock_hvac = _make_mock_hvac({"JWT_SECRET": "super-sensitive-value"})

        import app.core.vault as vault_mod

        with caplog.at_level(logging.INFO, logger="app.core.vault"):
            with patch.object(vault_mod, "hvac", mock_hvac):
                vault_mod.load_vault_secrets("http://vault:8200", "token")

        log_text = " ".join(caplog.messages)
        assert "super-sensitive-value" not in log_text
        assert "JWT_SECRET" in log_text

    def test_empty_secrets_dict_does_not_raise(self) -> None:
        """Empty secret path (all optional) must not crash."""
        mock_hvac = _make_mock_hvac({})

        import app.core.vault as vault_mod

        with patch.object(vault_mod, "hvac", mock_hvac):
            vault_mod.load_vault_secrets("http://vault:8200", "token")
