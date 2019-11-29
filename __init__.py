# -*- coding:utf-8 -*-
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version; http://www.gnu.org/copyleft/gpl.html.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

__version__ = "0.1"
__license__ = "GNU Affero General Public License, version 3 or later"

import logging
import sys

from anki.hooks import addHook

from .logging_handlers import TimedRotatingFileHandler
from .utils import get_path
from .main import setup_preview_slideshow


logger = logging.getLogger(__name__)
f_handler = TimedRotatingFileHandler(
    get_path("addon_log"), when='D', interval=7, backupCount=1, encoding="utf-8")
f_handler.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d-%(module)20s-%(levelname)5s>> %(message)s",
                                         "%y%m%d %H%M%S"))
f_handler.setLevel(logging.INFO)
logger.addHandler(f_handler)
logger.setLevel(logging.INFO)

# runHook('browser.setupMenus', self)
addHook('browser.setupMenus', setup_preview_slideshow)

