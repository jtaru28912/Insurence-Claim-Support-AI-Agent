"""
Uvicorn entrypoint.

Run with:
    uvicorn customer_support_agent.main:app --reload

or simply:
    python -m customer_support_agent.main
"""

from __future__ import annotations

import uvicorn

from customer_support_agent.api.app_factory import create_app
from customer_support_agent.core.settings import get_settings

app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "customer_support_agent.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.app_env == "development",
    )


if __name__ == "__main__":
    run()
