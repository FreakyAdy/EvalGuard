"""Container and microVM sandboxing backends."""

from evalguard.sandbox.backends.base import CommandResult, SandboxBackend
from evalguard.sandbox.backends.detector import (
    BACKEND_REGISTRY,
    detect_available_backend,
    get_backend,
)
from evalguard.sandbox.backends.docker import DockerBackend
from evalguard.sandbox.backends.firecracker import FirecrackerBackend
from evalguard.sandbox.backends.gvisor import GVisorBackend
from evalguard.sandbox.backends.host import HostProcessBackend
from evalguard.sandbox.backends.podman import PodmanBackend

__all__ = [
    "BACKEND_REGISTRY",
    "CommandResult",
    "DockerBackend",
    "FirecrackerBackend",
    "GVisorBackend",
    "HostProcessBackend",
    "PodmanBackend",
    "SandboxBackend",
    "detect_available_backend",
    "get_backend",
]
