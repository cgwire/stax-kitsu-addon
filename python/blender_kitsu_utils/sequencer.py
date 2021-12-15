from operator import attrgetter
from pathlib import Path
from typing import List, Tuple, Union

import bpy
from bpy.types import MetaSequence, MovieSequence, SoundSequence
import openreviewio as orio


image_files_extensions = frozenset(  # TODO try to make it cross with Stax
    [
        ".bmp",
        ".cin",
        ".dds",
        ".dpx",
        ".exr",
        ".hdr",
        ".j2c",
        ".jp2",
        ".jpeg",
        ".jpg",
        ".pdd",
        ".png",
        ".psb",
        ".psd",
        ".rgb",
        ".rgba",
        ".sgi",
        ".tga",
        ".tif",
        ".tiff",
        ".tx",
    ]
)

sound_files_extensions = frozenset(
    [
        ".wav",
        ".ogg",
        ".oga",
        ".mp3",
        ".mp2",
        ".ac3",
        ".aac",
        ".flac",
        ".wma",
        ".eac3",
        ".aif",
        ".aiff",
        ".m4a",
        ".mka",
    ]
)


def get_timeline_names_list(project_name: str, timeline_type: str) -> List[str]:
    """List of available timelines editing to load into sequencer.

    :param project_name: Source project
    :param timeline_type: Timeline editing type (Assets, Episode, Playlist...)
    :return: List of timeline names
    """
    # TODO
    # Maybe not needed in this shared module
    pass


def get_channel_names_list(project: str, timeline_name: str) -> List[str]:
    """List of channels to load into sequencer.

    :param project_name: Source project name
    :param timeline_name: Timeline name
    :return: List of timeline names
    """
    # TODO
    # Maybe not needed in this shared module
    pass


def create_shot_stack(
    channel_name: str,
    sequences_stack: MetaSequence,
    kitsu_shot,  # TODO correct typing
    channel_index=1,
    frame_start=0,
) -> MetaSequence:
    """Create shot stack as metasequence.

    Versions of the shot are appended to this stack.

    :param Channel_name: Channel name
    :param kitsu_shot: Kitsu shot
    :param channel_index: Channel to build composable, defaults to 1
    :param frame_start: First frame of clip's sequence, defaults to 1
    :return: Created shot stack metasequence
    """
    # Stop process if no cut duration for the shot
    duration = kitsu_shot.duration  # TODO
    if not duration:
        raise ValueError(
            f"Shot {kitsu_shot.get('code')}: 'duration' is None. Fix it in Kitsu before retrying to load."
        )

    # Build into VSE
    meta = sequences_stack.sequences.new_meta(
        get_shot_seq_name(channel_name, kitsu_shot),
        channel_index,
        frame_start,
    )

    meta["stax_meta_usage"] = "Versions"
    meta[
        "kitsu_shot"
    ] = kitsu_shot  # TODO might need to convert into dict, made to keep the reference for publishing and update correct entity
    meta.frame_final_duration = duration

    # Create empty frames at start and end for annotate drawing
    for layer in bpy.data.grease_pencils["Annotations"].layers:
        layer_frames = [frame.frame_number for frame in layer.frames]
        if meta.frame_final_start not in layer_frames:  # Start
            layer.frames.new(meta.frame_final_start)
        if meta.frame_final_end not in layer_frames:  # End
            layer.frames.new(meta.frame_final_end)

    return meta


def create_version_sequence(
    self,
    shot_stack: MetaSequence,
    kitsu_version,  # TODO typing
    channel_index=None,
    try_download=False,
) -> Union[MovieSequence, SoundSequence]:
    """Create sequence for a given version.

    :param shot_stack: Shot stack to create version into
    :param kitsu_version: Kitsu version to build
    :param channel_index: Channel to build composable, defaults to first shot_stack available channel
    :param try_download: Try to download movie from server
    """
    # Build version name
    version_name = get_version_seq_name(kitsu_version)

    # Sentinel if version already exists
    existing_versions = [seq.name for seq in shot_stack.sequences]
    if version_name in existing_versions or f"stax.{version_name}" in existing_versions:
        return

    version_clip_path = kitsu_version.movie_path  # TODO

    if try_download:
        if not version_clip_path or (
            version_clip_path and not Path(version_clip_path).is_file()
        ):
            version_clip_path = download_movie_from_kitsu(kitsu_version)  # TODO

    if version_clip_path:
        version_clip_path = Path(version_clip_path)
    else:  # Sentinel
        return

    # Create shot version
    # ===================
    if not channel_index:
        channel_index = len(shot_stack.sequences) + 1
    frame_start = shot_stack.frame_final_start

    # Set clip time
    # -----
    if version_clip_path.suffix.lower() in image_files_extensions:
        # Image file
        sequence = shot_stack.sequences.new_image(
            name=version_name,
            filepath=str(version_clip_path),
            channel=channel_index,
            frame_start=frame_start,
            fit_method="FIT",
        )
    elif version_clip_path.suffix.lower() in sound_files_extensions:
        # Sound file
        sequence = shot_stack.sequences.new_sound(
            name=version_name,
            filepath=str(version_clip_path),
            channel=channel_index,
            frame_start=frame_start,
        )
    else:
        # Create movie sequence, place holder if file doesn't exist
        sequence = shot_stack.sequences.new_movie(
            name=version_name,
            filepath=str(version_clip_path),
            channel=channel_index,
            frame_start=frame_start,
            fit_method="FIT",
        )

    # -----
    if not sequence:  # Sentinel
        return

    # Add media info data to be displayed into UI (optional)
    sequence["stax_media_info"] = {}  # TODO

    # Add status
    sequence["current_status"] = build_orio_status(
        get_kitsu_statuses(),  # TODO
        kitsu_version.status,  # TODO
    ).state

    sequence["kitsu_version"] = kitsu_version  # TODO as dict?

    return sequence


def update_shots_timeline(
    kitsu_versions: List[dict], kitsu_shots: List[dict] = None, is_new_versions=True
):
    """Update Blender Timeline from existing timeline and with versions.

    Ancient versions to recent versions from bottom to top.

    :param kitsu_versions: Versions of shots from Kitsu
    :param kitsu_shots: Shots from Kitsu, create non existing shots for versions if provided, else skip version creation
    :param is_new_versions: Create version above or below the current one. Default as above.
    :return: Updated OTIO timeline.
    """

    scene = bpy.context.scene
    seq_ed = scene.sequence_editor
    creation_direction = 1 if is_new_versions else -1

    if not kitsu_shots:  # Sentinel
        kitsu_shots = []

    # Update shots
    created_sequences = [None] * len(kitsu_versions)
    for i, version in enumerate(kitsu_versions):

        task_name = ""  # TODO
        shot_seq_name = get_shot_seq_name(task_name, shot)

        # Find shot
        shot_seq = seq_ed.sequences.get(shot_seq_name)
        if not shot_seq:  # Create shot

            shot_offset = 0
            for shot in kitsu_shots:
                shot_seq = create_shot_stack(
                    task_name,
                    seq_ed,
                    shot,
                    scene.tracks.find(task_name) + 1,
                    shot_offset,
                )
                break

            shot_offset += shot.duration  # TODO

        # Sort existing sequences and move down if too many of them
        previous_versions_count = len(shot_seq.sequences)

        # Build new version track on top of last one
        if previous_versions_count:
            sorted_seqs = sorted(
                shot_seq.sequences, key=attrgetter("channel", "frame_final_start")
            )
            reference_sequence = (
                sorted_seqs[-1] if creation_direction == 1 else sorted_seqs[0]
            )

        created_sequences[i] = create_version_sequence(
            shot_seq,
            version,
            reference_sequence.channel + creation_direction
            if previous_versions_count
            else 1,
        )
        # TODO sound for playlists

    return created_sequences


def get_shot_seq_name(task_name: str, kitsu_shot) -> str:
    """Get shot name from task and shot.

    :param task_name: Task name
    :param kitsu_shot: Kitsu Shot
    :return: Shot sequence name
    """
    return f"{kitsu_shot.name}_{task_name}"


def build_orio_status(available_statuses, version_status: dict) -> orio.Status:
    """Convert production statuses to review statuses, no history, based on current status.

    # TODO this must be discussed more precisely

    :param version_status: Version status to build ORIO status from
    :return: ORIO status
    """

    approved_statuses = available_statuses.get("approved")
    rejected_statuses = available_statuses.get("rejected")

    if version_status in rejected_statuses:
        orio_status = orio.Status(
            state="rejected",
            author="",
        )
    elif version_status in approved_statuses:
        orio_status = orio.Status(
            state="approved",
            author="",
        )
    else:
        orio_status = orio.Status(
            state="waiting review",
            author="",
        )

    return orio_status


def build_reviews(
    available_statuses,
    kitsu_versions,
    kitsu_notes,
    cache_dir: Path,
) -> List[orio.MediaReview]:
    """Build reviews from versions.

    :param kitsu_versions: Versions to create reviews from.
    :param kitsu_notes: Notes to create reviews with.
    :param cache_dir: Directory to build reviews in.
    :param build_duration: Duration of the process.
    :return: Created reviews
    """

    # Create reviews dir
    if not cache_dir.is_dir():
        cache_dir.mkdir(parents=True)
    downloads_dir = Path(cache_dir, "downloads")
    if not downloads_dir.is_dir():
        downloads_dir.mkdir(parents=True)

    # Build reviews
    # =============
    # Associate notes to related version
    attachs_to_download = []
    created_reviews = [None] * len(kitsu_versions)
    for i, version in enumerate(kitsu_versions):

        if not version:  # Sentinel
            continue

        for kitsu_note in kitsu_notes:
            # TODO
            # If attachment keep the file for later DL
            attachs_to_download.append(attach_to_dl)

        # Create or Update review
        # =============
        created_reviews[i] = edit_review(
            available_statuses,
            version,
        )

        # Start process to download attachments, use subprocess
        p = Process(
            target=download_attachements,
            args=(attachs_to_download),
        )
        p.start()

    return created_reviews


def edit_review(
    available_statuses,
    version,
) -> orio.MediaReview:
    """Create or Update review from version data.

    :param version: Version to create the related review
    :return: Created review
    """
    # ===================
    # Create media review
    # ===================
    version_clip_path = version.movie_path  # TODO
    if not version_clip_path:  # Sentinel
        return

    orio_review = orio.MediaReview(version_clip_path)

    # Review metadata
    orio_review.metadata = {}  # Useful to keep needed data

    # Create status
    # -------------
    kitsu_status = version.status  # TODO
    if kitsu_status is None:
        # TODO raise an error message
        pass
    else:
        orio_review.status = build_orio_status(available_statuses, kitsu_status)

    # Create the contents
    # ===================
    kitsu_notes = []  # TODO
    for note in kitsu_notes:

        # Create image annotations
        # ------------------------
        contents_list = []
        contents_list.append(  # TODO
            orio.Content.ImageAnnotation(
                path_to_image=drawing_on_transparent_bg,
                frame=annot_start_frame,
                duration=annot_duration,
            )
        )

        # TODO Add text contents from comments
        # -----------------
        # Single frame
        if False and one_frame_duration:  # TODO
            content = orio.Content.TextAnnotation(
                body=body, frame=match_frames[0], duration=1
            )
        # Several frames annotations
        elif False and several_frames_duration:  # TODO
            content = orio.Content.TextAnnotation(
                body=body,
                frame=match_frames[0],
                duration=int(match_frames[-1]) - int(match_frames[0]),
            )
        else:
            content = orio.Content.TextComment(body=body)  # TODO

        # Add content to list
        contents_list.append(content)

        # Create Note if has contents
        if contents_list:
            orio_note = orio.Note(
                author=note.user_name,  # TODO
                date=note.creation_date.isoformat(),  # TODO
                contents=contents_list,
                metadata={},
                parent_note=previously_created_orio_note,  # TODO if a note is a reply in a thread
            )

            # Add note to ORIO review
            orio_review.add_note(orio_note)

    return orio_review
