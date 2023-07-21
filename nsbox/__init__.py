import os
from importlib import metadata

DEBUG = os.environ.get("nsbox_DEBUG", False)

try:
    __version__ = metadata.version("nsbox")
except metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0.0+unknown"

from nsbox.api import NsAPI  # noqa: E402
from nsbox.nsjail import NsJail  # noqa: E402
from nsbox.utils.logging import init_logger, init_sentry  # noqa: E402

__all__ = ("NsJail", "NsAPI", "DEBUG")

init_sentry(__version__)
init_logger(DEBUG)
