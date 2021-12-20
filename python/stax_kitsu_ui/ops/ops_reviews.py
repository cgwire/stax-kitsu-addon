"""Every operator relevant to reviews."""

from multiprocessing import Process
from pathlib import Path

import bpy
from bpy.props import StringProperty
from bpy.utils import register_class, unregister_class
import stax
from stax.utils.utils_cache import (
    get_temp_directory,
    save_session,
)
from stax.utils.utils_core import get_context
from stax.utils.utils_reviews import (
    build_media_reviews,
    build_pending_notes,
    clear_media_reviews,
)


class STAX_OT_publish_reviews(
    stax.ops.ops_reviews.STAX_OT_publish_reviews, bpy.types.Operator
):
    """Publish reviews of the current session"""

    bl_idname = "scene.publish_reviews"
    bl_label = "Publish Reviews"

    filter_glob: StringProperty(
        default="",
        options={"HIDDEN"},
    )

    filename_ext = ""

    directory: bpy.props.StringProperty(
        name="Outdir Path",
        description="Where reviews will be written",
        subtype="DIR_PATH",
    )

    def execute(self, context):
        """Execute."""
        scene = context.scene
        scene.reviews_linked_directory = self.directory

        # Build pending notes

        edited_notes = build_pending_notes()

        #####################
        # Publishing
        #####################

        # Export reviews
        # --------------

        # Run publish reviews
        # Overriden part
        p = Process(
            target=publish_reviews,  # TODO
            args=(
                [
                    # TODO edited_notes is [(media_sequence, linked_orio_review, created_orio_note)]
                ],
                Path(get_temp_directory(), "annotations"),
            ),
        )
        p.start()

        #####################
        # Cleaning
        #####################

        # Clear review of related media sequences, first element of edited_notes tuple
        clear_media_reviews([e[0] for e in edited_notes], pending_note_only=True)

        # Close review session
        context.scene.review_session_active = False

        # Update for new reviews

        # Add notes to review
        for _media_seq, review, note in edited_notes:
            review.add_note(note)
        # Build media reviews in timeline
        build_media_reviews(
            [(media_seq, review) for media_seq, review, _note in edited_notes]
        )

        # Set the picker as default tool back
        override = get_context("Main", "PREVIEW")
        bpy.ops.wm.tool_set_by_id(override, name="builtin.sample")

        # Save session and keep this new state as default
        save_session()

        # Watch any action considered to start the review session
        bpy.ops.wm.watch_review_start()

        return {"FINISHED"}


classes = [STAX_OT_publish_reviews]


def register():
    """Register classes to Blender."""
    # Unregister native operators for custom behavior
    unregister_class(stax.ops.ops_reviews.STAX_OT_publish_reviews)

    # Set Custom UI and operators
    for cls in classes:
        register_class(cls)


def unregister():
    """Unregister classes to Blender."""
    # Set back native classes
    # Unregister Custom Operators
    for cls in classes:
        unregister_class(cls)

    # Register Default Operators
    register_class(stax.ops.ops_reviews.STAX_OT_publish_reviews)
