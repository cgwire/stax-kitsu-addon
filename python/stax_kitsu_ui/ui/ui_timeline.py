"""Every ui functions relative to timeline, only overrides."""

import bpy
import stax


@staticmethod
def draw_author(layout):
    """Override from Stax draw_author."""
    context = bpy.context
    scene = context.scene
    user_preferences = scene.user_preferences

    # Log-in Button
    row = layout.row(align=True)
    if not scene.session_logged_in:
        row.operator(
            "wm.kitsu_authentication",
            text="Please log-in to Kitsu",
            icon="USER",
        )
    else:
        row.operator(
            "wm.kitsu_authentication",
            text="user : " + user_preferences.author_name,
            icon="USER",
        )

        # UI displayed if user logging is successful
        if scene is bpy.data.scenes["Scene"]:
            # [] Load timeline
            row.separator()

            prod_name = "Caminandes"  # TODO

            row.operator(
                "sequencer.load_timeline",
                text=f"Load {prod_name} Timeline",
                icon="ASSET_MANAGER",
            )

    # Update timeline
    if scene.timeline_name and scene is bpy.data.scenes["Scene"]:
        row = layout.row()

        row.operator("sequencer.update_timeline", text="Update", icon="FILE_REFRESH")


kept_draw_author = stax.ui.ui_time.TIME_HT_editor_buttons.draw_author
# ======


def register():
    stax.ui.ui_time.TIME_HT_editor_buttons.draw_author = draw_author


def unregister():
    stax.ui.ui_time.TIME_HT_editor_buttons.draw_author = kept_draw_author
