# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name": "Stax Kitsu Addon",
    "author": "Félix David",
    "description": "Kitsu interface for Stax.",
    "blender": (2, 93, 0),
    "version": (0, 0, 0),
}

from pathlib import Path
import sys


# Reference ./python dir into path to consider subfolders as modules
sys.path.append(str(Path(__file__).parent.joinpath("python")))


from .python import stax_kitsu_ui


def register():
    stax_kitsu_ui.register()


def unregister():
    stax_kitsu_ui.unregister()


if __name__ == "__main__":
    register()
