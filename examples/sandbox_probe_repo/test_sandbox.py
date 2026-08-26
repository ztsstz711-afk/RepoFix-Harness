import os
import socket
from pathlib import Path

import pytest


def test_repository_mount_is_read_only():
    with pytest.raises(OSError):
        Path("forbidden-write.txt").write_text("should fail", encoding="utf-8")


def test_external_network_is_disabled():
    connection = socket.socket()
    connection.settimeout(0.5)
    with pytest.raises(OSError):
        connection.connect(("1.1.1.1", 53))
    connection.close()


def test_provider_secret_is_not_in_container_environment():
    assert "REPOFIX_API_KEY" not in os.environ


def test_temporary_directory_remains_writable(tmp_path):
    target = tmp_path / "allowed.txt"
    target.write_text("ok", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "ok"
