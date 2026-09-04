"""Backend auto-detection and instantiation logic with graceful degradation."""

from __future__ import annotations

import logging

from evalguard.sandbox.backends.base import SandboxBackend
from evalguard.sandbox.backends.docker import DockerBackend
from evalguard.sandbox.backends.firecracker import FirecrackerBackend
from evalguard.sandbox.backends.gvisor import GVisorBackend
from evalguard.sandbox.backends.host import HostProcessBackend
from evalguard.sandbox.backends.podman import PodmanBackend
from evalguard.sandbox.profiles import SandboxProfile

logger = logging.getLogger(__name__)

BACKEND_REGISTRY: dict[str, type[SandboxBackend]] = {
    "gvisor": GVisorBackend,
    "firecracker": FirecrackerBackend,
    "docker": DockerBackend,
    "podman": PodmanBackend,
    "host": HostProcessBackend,
}


def detect_available_backend() -> type[SandboxBackend]:
    """Detect the most secure isolation backend available on the current host.

    Order of preference:
    1. gVisor (application kernel virtualization)
    2. Firecracker (hardware microVM isolation)
    3. Docker (container isolation)
    4. Podman (daemonless container isolation)
    5. Host (process-level monitoring fallback)
    """
    for name, backend_cls in BACKEND_REGISTRY.items():
        if name != "host" and backend_cls.is_available():
            logger.info("Auto-detected sandboxing backend: %s", name)
            return backend_cls

    logger.warning(
        "No container/VM runtime detected. Falling back to host process isolation with watcher."
    )
    return HostProcessBackend


def get_backend(
    backend_name: str | None,
    task_id: str,
    profile: SandboxProfile,
) -> SandboxBackend:
    """Instantiate requested or auto-detected backend."""
    if not backend_name or backend_name == "auto":
        backend_cls = detect_available_backend()
    elif backend_name in BACKEND_REGISTRY:
        backend_cls = BACKEND_REGISTRY[backend_name]
        if not backend_cls.is_available() and backend_name != "host":
            logger.warning(
                "Requested backend '%s' is not available. Falling back to auto-detection.",
                backend_name,
            )
            backend_cls = detect_available_backend()
    else:
        raise ValueError(
            f"Unknown sandbox backend: '{backend_name}'. Available: {list(BACKEND_REGISTRY.keys())}"
        )

    return backend_cls(task_id, profile)
