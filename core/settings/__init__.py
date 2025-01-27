import logging

from core.settings.base import *


logger = logging.getLogger(__name__)

try:
    from core.settings.local import *
except ModuleNotFoundError:
    logger.warning('Local settings file not initialized yet.')
