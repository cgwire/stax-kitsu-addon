"""Utils for all the module."""

from pathlib import Path
from typing import List

import bpy
from stax.utils.utils_cache import (
    get_cache_directory,
)


def get_session_dir() -> Path:
    """Get session directory.

    :return: Path of session directory
    """
    scene = bpy.context.scene
    return get_cache_directory().joinpath("Sessions", scene.project_name)


def get_shots_list() -> List[str]:
    """Get shots list depending on shots to load if any, with context.

    :return: List of shots asked to be loaded
    """
    scene = bpy.context.scene

    # If shots to load, load only shots, else get all shots
    shots_to_load = scene.available_shots
    if scene.shot_to_load and scene.shot_to_load != "All":
        selected_shot_index = scene.available_shots.find(scene.shot_to_load)
        shots_to_load = scene.available_shots[
            max(0, selected_shot_index - scene.context_shots) : min(
                len(scene.available_shots),
                selected_shot_index + scene.context_shots + 1,
            )
        ]

    return [shot.name for shot in shots_to_load if shot.name != "All"]


def get_selected_channels_list() -> List[str]:
    """Get selected channels list to be loaded.

    :return: Channels list
    """
    scene = bpy.context.scene

    return [channel.name for channel in scene.channels_list if channel.selected]
