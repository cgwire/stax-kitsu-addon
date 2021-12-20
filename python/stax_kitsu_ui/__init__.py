"""Initialization for the addon."""

# Import to override Stax UI functions
from .ops import ops_reviews, ops_session, ops_timeline
from .ui import ui_timeline


def register():
    """Register classes to Blender."""
    # Set Custom UI and operators
    ops_reviews.register()
    ops_session.register()
    ops_timeline.register()

    ui_timeline.register()

    print(f"Registered Kitsu UI")


def unregister():
    """Unregister classes to Blender."""
    # Set Custom UI and operators
    ops_reviews.unregister()
    ops_session.unregister()
    ops_timeline.unregister()

    ui_timeline.unregister()

    print(f"Unregistered Kitsu UI")


if __name__ == "__main__":
    register()
