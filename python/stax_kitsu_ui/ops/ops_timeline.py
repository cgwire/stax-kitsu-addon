"""Every operator relevant to timeline."""

from datetime import datetime, timezone
import functools
from pathlib import Path

import bpy
from bpy.app.handlers import persistent
from bpy.utils import register_class, unregister_class
from blender_kitsu_utils.sequencer import (
    build_reviews,
    create_shot_stack,
    create_version_sequence,
    get_channel_names_list,
    get_timeline_names_list,
    update_shots_timeline,
)
import stax
import stax.utils.utils_config as utils_config
from stax.utils.utils_core import get_context
from stax.utils.utils_reviews import (
    build_media_reviews,
)
from stax.utils.utils_timeline import (
    get_media_sequence,
)

from stax_kitsu_ui.utils import (
    get_session_dir,
    get_selected_channels_list,
)


counter = 0
frame_offset = 0
shots_total = 0


class AvailableItem(bpy.types.PropertyGroup):
    """Item available from Kitsu."""

    name: bpy.props.StringProperty(name="Name")
    description: bpy.props.StringProperty(name="Description")
    selected: bpy.props.BoolProperty(name="Selected", default=True)


@persistent
def update_user_timelines_list(self, context):
    """Update the list of available timelines for the user.

    Also get the tasks is they are some linked.

    :param self: Current operator running this function
    :param context: Blender context
    """
    scene = context.scene

    # Set available timelines
    scene.available_timelines.clear()
    timelines_names = get_timeline_names_list(scene.project_name, scene.timeline_type)
    for t in timelines_names:
        tl = scene.available_timelines.add()
        if type(t) is tuple and len(t) > 1:
            tl.name, tl.description = t
        else:
            tl.name = str(t)

    # Set default timeline if field empty or doesn't exist in valid timelines
    if timelines_names and (
        not scene.timeline_name or scene.timeline_name not in timelines_names
    ):
        scene.timeline_name = scene.available_timelines[0].name

    # Set available shots
    update_available_shots(self, context)

    # Load tasks
    user_config = utils_config.read_user_config()

    # Create channels
    scene.channels_list.clear()

    channels = get_channel_names_list(scene.project_name)

    for channel in channels:
        new_channel = scene.channels_list.add()
        new_channel.name = channel

        # Set synchronization state from user config
        if (
            user_config.get(scene.project_name)
            and channel in user_config.get(scene.project_name).keys()
        ):
            new_channel.selected = user_config.get(scene.project_name).get(channel)


@persistent
def update_available_shots(self, context):
    """Update the list of available shots for the user.

    :param self: Current operator running this function
    :param context: Blender context
    """
    scene = context.scene

    # Sentinel for Playlist which don't have shots but only versions
    # TODO is it the case for Kitsu?
    if scene.timeline_type == "Playlist":
        return

    scene.available_shots.clear()
    kitsu_shots = []  # TODO get_kitsu_shots()
    for shot in kitsu_shots:
        sh = scene.available_shots.add()
        sh.name = shot.name  # TODO


@persistent
def update_toggle_all_tasks(self, context):
    """Update the toggle all tasks bool.

    :param self: Current operator running this function
    :param context: Blender context
    """
    scene = context.scene
    for task in scene.channels_list:
        task.selected = self.toggle_all_tasks


class LoadTimelineBase(bpy.types.Operator):
    """Load timeline from Kitsu"""

    bl_idname = "sequencer.load_timeline"
    bl_label = "Load Timeline"

    toggle_all_tasks: bpy.props.BoolProperty(
        name="Toggle all tasks", update=update_toggle_all_tasks
    )

    # This parameter is the only required one to target the timeline to load
    filepath: bpy.props.StringProperty()

    def invoke(self, context, event):
        """Call when clicking on the Operator through the UI (a.k.a button).

        Native Blender Operator function.

        :param context: Current Blender context
        :param event: Event that triggered the Operator, can access user inputs (Mouse, keys...)
        """
        # Waiting cursor
        context.window.cursor_set("WAIT")

        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        """Display the operator's UI after the invoke.

        Native Blender Operator function.

        :param context: Current Blender context
        """
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "timeline_type")

        if scene.timeline_type == "Episode":
            # Select timeline
            layout.prop_search(
                scene, "timeline_name", scene, "available_timelines", text="Episode"
            )

            # Display description if provided
            user_timeline = scene.available_timelines.get(scene.timeline_name)
            if hasattr(user_timeline, "description"):
                timeline_description = user_timeline.description
                if timeline_description:
                    layout.label(text=timeline_description)

            # Select shot to load
            row = layout.row(align=True)
            row.prop_search(scene, "shot_to_load", scene, "available_shots")
            if scene.shot_to_load and scene.shot_to_load != "All":
                row.prop(scene, "context_shots")

            # Draw project tasks into popup dialog
            layout.prop(self, "toggle_all_tasks", text="All")
            for task in reversed(scene.channels_list):
                layout.prop(task, "selected", text=task.name)

        elif scene.timeline_type == "Asset":
            layout.label(text="Every asset waiting for your review will be loaded.")

        elif scene.timeline_type == "Playlist":
            # Select timeline
            layout.prop_search(
                scene, "timeline_name", scene, "available_timelines", text="Episode"
            )

            layout.label(text="All versions from this playlist will be loaded.")

        # Previous versions to load
        if scene.timeline_type not in ["Playlist"]:
            layout.prop(scene, "versions_amount")

    def execute(self, context):  # noqa C902
        """Actual operator execution.

        Native Blender Operator function.

        :param context: Current Blender context
        """
        scene = context.scene
        seq_ed = scene.sequence_editor

        # Keep update date
        current_update_date = datetime.now(timezone.utc).isoformat()

        # Get timeline cache dir
        session_dir = get_session_dir()
        if not session_dir.is_dir():
            session_dir.mkdir(parents=True)

        global counter
        global frame_offset

        # Reset timeline if remaining sequences
        if len(seq_ed.sequences) > 0:
            scene.sequence_editor_clear()
            scene.sequence_editor_create()

            counter = 0
            frame_offset = 0

        # Remove tracks
        if len(scene.tracks) > 0:
            scene.tracks.clear()

        # Start Timeline and reviews creation in parallel

        # Get Kitsu shots
        # TODO Filter shots if only some are asked using scene.shot_to_load and scene.context_shots
        kitsu_shots = []  # TODO

        # Create channels
        selected_channels = get_selected_channels_list()
        for channel in selected_channels:
            scene.tracks.add().name = channel

        # Get Kitsu versions
        kitsu_versions = []  # TODO

        # Generate and fill mapping
        # TODO this part is a bit tricky because designed to have a progressive loading and not freeze the whole UI too long.
        #       The user can keep an eye on what's going on.
        tasks_total = len(selected_channels)
        shots_total = len(kitsu_shots)
        editing_versions_mapping = [(None, None, None)] * tasks_total * shots_total
        last_versions = [{}] * tasks_total * shots_total
        scene_frame_end = 0
        version_index = 0

        # Create reversed channels to create most recent items channel first
        for i, channel in reversed(selected_channels):
            for j, shot in enumerate(kitsu_shots):
                # Get scene duration, calculate for first loop
                if i == 0:
                    scene_frame_end += shot.duration  # TODO

                # Match last version
                last_version = None  # TODO

                editing_versions_mapping[version_index] = (i, j, last_version)
                last_versions[version_index] = last_version

                version_index += 1

        # TODO we might want to keep versions python objects for update to avoid downloading them too often.
        # TODO this case use shelf python module

        # Set range
        scene.frame_end = scene_frame_end

        # Frame timeline
        bpy.ops.sequencer.view_all(get_context("Main", "SEQUENCER"))

        # Create timeline
        bpy.app.timers.register(
            functools.partial(
                build_progressive,
                context,
                selected_channels,
                kitsu_shots,
                editing_versions_mapping,
                scene.shot_to_load,
            )
        )

        # Set fps, remove trailing .0 of floats
        project = None  # TODO
        fps = project.fps  # TODO
        preset_script_path = Path(
            f"{bpy.utils.preset_paths('framerate')[0]}/{int(fps) if fps % 1 == 0 else fps}.py"
        )
        if preset_script_path.is_file():
            exec(compile(preset_script_path.open().read(), preset_script_path, "exec"))
        else:
            self.report(
                {"WARNING"},
                f"The preset: '{fps} fps' doesn't exist. Default framerate kept: {scene.render.fps/scene.render.fps_base}.",
            )

        # Save data
        scene.stax_info.session_last_update = current_update_date

        # Force color space
        scene.view_settings.view_transform = "Standard"

        # Set prefetch
        scene.sequence_editor.use_prefetch = True

        # Enable audio scrubbing
        scene.use_audio_scrub = True

        # Save session file
        session_file = session_dir.joinpath(f"{scene.timeline_name}_local").with_suffix(
            ".blend"
        )

        # Save session
        bpy.ops.wm.save_mainfile(filepath=session_file.as_posix())

        return {"FINISHED"}


def build_progressive(
    context, selected_tasks, kitsu_shots, versions_and_reviews, shot_to_load=""
) -> int:
    """Build timeline progressively by chunks of shots.

    :param context: Blender Context
    :param selected_tasks: Tasks to load
    :param kitsu_shots: Kitsu shots to build
    :param versions_and_reviews: (versions, reviews) to create
    :param shot_to_load: Selected shot to load, defaults to ""
    :return: Next chunk processing delay
    """
    if context.screen.is_animation_playing:  # Wait 1 sec if animation playing
        return 1

    global counter
    global frame_offset

    scene = context.scene
    seq_ed = scene.sequence_editor

    # How many versions are added at a time. Enough to keep it fast, not too much to keep reactivity
    for _ in range(5):
        # Stopper
        if counter >= len(versions_and_reviews):
            # Frame timeline
            bpy.ops.sequencer.view_all(get_context("Main", "SEQUENCER"))

            # Refresh to empty memory
            bpy.ops.sequencer.refresh_all()

            bpy.ops.sequencer.select_all(action="DESELECT")

            # Move playhead to selected shot
            if shot_to_load:
                for s in scene.sequence_editor.sequences:
                    if shot_to_load == s.name:
                        scene.frame_set(s.frame_final_start)
                        break

            # Set current frame for update
            scene.frame_set(scene.frame_current)

            return

        # Refresh every 85 versions
        if counter % 85 == 0:
            bpy.ops.sequencer.refresh_all()

        # Get version
        task_index, shot_index, version = versions_and_reviews[counter]

        task_name = selected_tasks[task_index]
        shot_duration = kitsu_shots[shot_index].duration  # TODO

        # Create version in meta
        if version:

            # Create shot meta
            shot_seq = create_shot_stack(
                task_name,
                seq_ed,
                kitsu_shots[shot_index],
                task_index + 1,
                frame_offset if shot_index != 0 else 0,
            )

            # Create version seq
            version_seq = create_version_sequence(
                shot_seq,
                version,
            )

            if version_seq:
                # Review is enabled
                version_seq.lock = (
                    is_user_authorized_to_review()
                )  # TODO from gazu directly?

                # Say to build note later when playhead will stop over
                version_seq["to_build_notes"] = True

            shot_seq.update()
            shot_seq.frame_final_duration = shot_duration

        # Offset shots
        if shot_index == 0:  # Reset shot offset
            frame_offset = shot_duration
        else:
            frame_offset += shot_duration

        counter += 1

    return 0


class SEQUENCER_OT_update_timeline(bpy.types.Operator):
    """Update timeline"""

    bl_idname = "sequencer.update_timeline"
    bl_label = "Update Timeline"

    @classmethod
    def poll(cls, context):
        sequence_editor = context.scene.sequence_editor
        return sequence_editor.sequences and not context.scene.review_session_active

    def execute(self, context):
        scene = context.scene
        seq_ed = scene.sequence_editor

        # Keep update date
        current_update_date = datetime.now(timezone.utc).isoformat()
        if scene.stax_info.session_last_update:
            last_update_date = datetime.fromisoformat(
                scene.stax_info.session_last_update
            )
        else:
            last_update_date = None

        selected_channels_list = get_selected_channels_list()

        # Get timeline cache dir
        timeline_dir = Path(bpy.data.filepath).parent

        # Get Kitsu shots
        # TODO Filter shots if only some are asked using scene.shot_to_load and scene.context_shots
        kitsu_shots = []  # TODO

        # Get updated Kitsu versions from selected_channels_list and kitsu_shots
        # We might want to get them from cache shelf?
        kitsu_versions = []  # TODO

        # Get notes of all versions (existing and updated)
        kitsu_notes = []  # TODO get notes for versions

        if not kitsu_versions and not kitsu_notes:
            self.report({"INFO"}, "Everything is up-to-date!")
            return {"CANCELLED"}

        # Create new versions in shots
        update_shots_timeline(kitsu_versions, kitsu_shots)

        # Create reviews

        created_reviews = build_reviews(
            available_kitsu_statuses,  # TODO
            kitsu_versions,
            kitsu_notes,
            timeline_dir,
        )

        # Match sequences and created reviews
        sequences_and_reviews = []
        for rev in created_reviews:
            sequence = seq_ed.sequences_all.get(rev.metadata.get("kitsu_version"))
            if sequence and (
                rev.notes or sequence.get("current_status") != rev.status.state
            ):
                sequences_and_reviews.append((sequence, rev))

        # Build media reviews in timeline
        build_media_reviews(sequences_and_reviews)

        scene.stax_info.session_last_update = current_update_date

        # Refresh to empty memory
        bpy.ops.sequencer.refresh_all()

        self.report({"INFO"}, "Session has been updated!")

        return {"FINISHED"}


class SEQUENCER_OT_toggle_meta(bpy.types.Operator):
    """This operator substitutes sequencer.meta_toggle to exit the active meta if it's a substitute"""

    # TODO Use API when available to override sequencer.meta_toggle directly.

    bl_idname = "sequencer.toggle_meta"
    bl_label = "Toggle Versions"

    @classmethod
    def poll(cls, context):
        sequence_editor = context.scene.sequence_editor
        return (
            sequence_editor.active_strip
            and sequence_editor.active_strip.type == "META"
            or sequence_editor.meta_stack
        )

    def execute(self, context):
        scene = context.scene
        seq_ed = scene.sequence_editor
        current_meta = seq_ed.active_strip

        # Exit current meta if active meta is substitute
        if (
            not current_meta
            or current_meta.type != "META"
            or current_meta.get("stax_kind")
        ):
            seq_ed.active_strip = None
            target_channel = seq_ed.meta_stack[-1].channel
        else:
            versions_count = len(current_meta.sequences)
            if versions_count < scene.versions_amount:
                # Get kitsu versions TODO make a cache on the meta if it appears too slow
                kitsu_versions = []  # TODO

                # Build only previous versions from current and with the correct amount
                missing_versions = []
                for v in kitsu_versions:
                    version_name = ""  # TODO

                    if versions_count < scene.versions_amount and (
                        version_name not in current_meta.sequences
                        and f"stax.{version_name}" not in current_meta.sequences
                    ):
                        missing_versions.append(v)

                        # Move existing versions
                        for seq in current_meta.sequences:
                            seq.channel += 1

                        versions_count += 1

                # Update shots
                update_shots_timeline(missing_versions, is_new_versions=False)

                # Get notes
                kitsu_notes = []  # TODO

                # Create reviews
                timeline_dir = Path(bpy.data.filepath).parent

                created_reviews = build_reviews(
                    available_kitsu_statuses,  # TODO
                    missing_versions,
                    kitsu_notes,
                    timeline_dir,
                )

                # Match sequences and created reviews
                sequences_and_reviews = [
                    (current_meta.sequences.get(related_version_name), rev)  # TODO
                    for rev in created_reviews
                    if rev.notes
                ]

                # Build media reviews in timeline
                build_media_reviews(sequences_and_reviews)

            # Set target channel
            seq_ed.active_strip = current_meta
            target_channel = current_meta.sequences[0].channel

        bpy.ops.sequencer.meta_toggle()

        # Display correct track
        scene.current_track = str(target_channel)

        return {"FINISHED"}


# ======== Handlers ===========


@persistent
def frame_build_review(scene):
    """Run everytime a frame is changed but the animation is not playing."""
    if not bpy.context.screen.is_animation_playing:
        version_seq = get_media_sequence(scene.sequence_editor.active_strip)

        # Flag sentinel
        if not version_seq or not version_seq.get("to_build_notes"):
            return

        kitsu_version = version_seq[
            "kitsu_version"
        ].to_dict()  # TODO to match kitsu version and its sequence
        # Get notes
        last_versions = [kitsu_version]
        kitsu_notes = []  # TODO

        # Build reviews
        timeline_dir = Path(bpy.data.filepath).parent
        created_reviews = build_reviews(
            available_kitsu_statuses,  # TODO
            last_versions,
            kitsu_notes,
            timeline_dir,
        )

        # Build media reviews in timeline
        build_media_reviews([(version_seq, created_reviews[0])])

        # Disable flag
        version_seq["to_build_notes"] = False


classes = [AvailableItem, SEQUENCER_OT_update_timeline, SEQUENCER_OT_toggle_meta]


def register():
    """Register classes to Blender."""
    # Unregister native operators for custom behavior
    unregister_class(stax.ops.ops_sequencer.SEQUENCER_OT_toggle_meta)

    # Set Custom UI and operators
    for cls in classes:
        register_class(cls)

    # Custom Properties
    bpy.types.Scene.project_name = bpy.props.StringProperty(
        name="Project",
        description="Project Name",
    )
    bpy.types.Scene.timeline_type = bpy.props.EnumProperty(
        name="Entity type",
        description="What kind of entity do you want to review?",
        default="Episode",
        items=[
            ("Episode", "Episode", "Episode"),
            ("Asset", "Asset", "Asset"),
            ("Sequence", "Sequence", "Sequence"),
            ("Playlist", "Playlist", "Playlist"),
        ],
        update=update_user_timelines_list,
    )
    bpy.types.Scene.timeline_name = bpy.props.StringProperty(
        name="Timeline name",
        description="Choose timeline to load",
        update=update_available_shots,
    )
    bpy.types.Scene.versions_amount = bpy.props.IntProperty(
        name="Versions to load",
    )

    bpy.types.Scene.available_timelines = bpy.props.CollectionProperty(
        type=AvailableItem
    )

    # Select shots to load
    # -----
    bpy.types.Scene.available_shots = bpy.props.CollectionProperty(type=AvailableItem)

    bpy.types.Scene.shot_to_load = bpy.props.StringProperty(
        name="Shot to load",
        description="Select one shot to load",
        default="All",
    )

    bpy.types.Scene.context_shots = bpy.props.IntProperty(
        name="Context Shots",
        description="How many shots before and after",
        default=1,
        min=0,
    )
    # -----

    bpy.types.Scene.channels_list = bpy.props.CollectionProperty(
        type=AvailableItem
    )  # TODO should it be called tasks_list?

    # Set handler
    bpy.app.handlers.frame_change_post.insert(0, frame_build_review)


def unregister():
    """Unregister classes to Blender."""
    # Set back native classes
    # Unregister Custom Operators
    for cls in classes:
        unregister_class(cls)

    del bpy.types.Scene.project_name
    del bpy.types.Scene.timeline_type
    del bpy.types.Scene.timeline_name
    del bpy.types.Scene.versions_amount
    del bpy.types.Scene.available_timelines
    del bpy.types.Scene.available_shots
    del bpy.types.Scene.shot_to_load
    del bpy.types.Scene.context_shots
    del bpy.types.Scene.channels_list
