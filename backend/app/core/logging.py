from __future__ import annotations

import logging


APP_LOGGER_NAME = "app"
APP_LOG_FORMAT = "%(levelname)s:%(name)s:%(message)s"


def configure_app_logging() -> None:
    app_logger = logging.getLogger(APP_LOGGER_NAME)
    app_logger.setLevel(logging.INFO)

    if any(getattr(handler, "_pvqa_app_handler", False) for handler in app_logger.handlers):
        return

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(APP_LOG_FORMAT))
    handler._pvqa_app_handler = True  # type: ignore[attr-defined]
    app_logger.addHandler(handler)

