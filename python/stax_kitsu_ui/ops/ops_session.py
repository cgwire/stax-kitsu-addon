"""Every operator relevant to session."""
import base64

import bpy
from bpy.app.handlers import persistent
from bpy.utils import register_class, unregister_class
from stax.utils.utils_config import read_user_config, write_user_config


def encode_password(password: str) -> str:
    """Hash a password for storing.

    :param password: String to hash
    :return: Hashed string
    """

    return base64.b64encode(password.encode("utf-8")).decode("utf-8")


def decode_password(password: str) -> str:
    """Verify a stored password against one provided by user.

    :param password: String to decode
    :return: Decoded string
    """

    return base64.b64decode(password).decode("utf-8") if password else ""


def switch_save_credentials(self, _):
    """Set auto_login to False if save_credentials is False."""

    if not self.save_credentials:
        self.auto_login = False

    # Save config
    write_user_config(
        additional_data={
            "auto_login": self.auto_login,
            "save_credentials": self.save_credentials,
        }
    )


def switch_auto_login(self, _):
    """Set save_credentials to True if auto_login is True."""

    if self.auto_login:
        self.save_credentials = True

    # Save config
    write_user_config(
        additional_data={
            "auto_login": self.auto_login,
            "save_credentials": self.save_credentials,
        }
    )


class WM_OT_production_manager_authentication(bpy.types.Operator):
    """Log-in to synchronize Stax with Kitsu"""

    bl_idname = "wm.kitsu_authentication"
    bl_label = "Kitsu authentication"

    login: bpy.props.StringProperty(name="User")
    password: bpy.props.StringProperty(
        name="Password",
        subtype="PASSWORD",
    )
    save_credentials: bpy.props.BoolProperty(
        name="Save Credentials", update=switch_save_credentials
    )
    auto_login: bpy.props.BoolProperty(name="Auto Log In", update=switch_auto_login)

    def invoke(self, context, _):
        """UI call."""
        user_prefs = context.scene.user_preferences

        # Read config data
        config_data = read_user_config()

        # Initialization from user preferences
        self.login = user_prefs.author_name
        self.save_credentials = config_data.get("save_credentials", False)

        if self.save_credentials:
            self.password = decode_password(config_data.get("password", ""))
            self.auto_login = config_data.get("auto_login", False)
        else:
            self.password = ""

        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        """Execute."""
        scene = context.scene
        user_preferences = context.scene.user_preferences

        # Display loading for user
        if context.window:
            context.window.cursor_set("WAIT")

        # Update user preferences
        user_preferences.author_name = self.login

        # Authenticate
        # TODO
        if authenticate(self.login, self.password):
            # Write config
            write_user_config(
                additional_data={
                    "auto_login": self.auto_login,
                    "password": encode_password(self.password),
                    "save_credentials": self.save_credentials,
                }
            )

            scene.session_logged_in = True

            self.report({"INFO"}, "Authentication Successful")
        else:
            self.password = ""

            scene.session_logged_in = False

            self.report({"ERROR"}, "Authentication failed")

        return {"FINISHED"}


@persistent
def auto_login(*kwargs):
    """Timer function to be run after addon registering.

    Must contain every SP setup functions.
    """
    scene = bpy.context.scene
    user_prefs = scene.user_preferences

    # Read user config
    config_data = read_user_config()

    # Auto-login
    if config_data.get("auto_login"):
        bpy.ops.wm.kitsu_authentication(
            login=user_prefs.author_name,
            password=decode_password(config_data.get("password", "")),
            save_credentials=config_data.get("save_credentials", False),
            auto_login=True,
        )


classes = [WM_OT_production_manager_authentication]


def register():
    """Register classes to Blender."""
    # Set Custom UI and operators
    for cls in classes:
        register_class(cls)

    # Custom Properties
    bpy.types.Scene.session_logged_in = bpy.props.BoolProperty(
        name="Logged in", default=False
    )

    bpy.app.timers.register(auto_login, first_interval=0)


def unregister():
    """Unregister classes to Blender."""
    # Set back native classes
    # Unregister Custom Operators
    for cls in classes:
        unregister_class(cls)

    del bpy.types.Scene.session_logged_in
