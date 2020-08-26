# Copyright (c) 2020 Autodesk, Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE. By
# accessing, using, copying or modifying this work you indicate your agreement
# to the Shotgun Pipeline Toolkit Source Code License. All rights not expressly
# granted therein are reserved by Autodesk, Inc.

import os
import logging

import sgtk
from tank.platform import Engine

import SketchBookLogger
import sketchbook_api

# Although the engine has logging already, this logger is needed for callback
# based logging where an engine may not be present.
logger = sgtk.LogManager.get_logger(__name__)


class SketchBookEngine(Engine):
    """
    SketchBook Engine
    """

    def __init__(self, tk, context, engine_instance_name, env):
        """
        Initialize the engine.
        """

        self._style_sheet = None
        self._app_style_sheet = None
        self._app_palette = None
        self._palette_brushes = {}

        super(SketchBookEngine, self).__init__(tk, context, engine_instance_name, env)

    def destroy_engine(self):
        """
        Called when the engine should tear down itself and all its apps.
        """

        self.logger.debug("%s: Destroying...", self)

        # Close all Shotgun app dialogs that are still opened since some apps
        # do threads cleanup in their onClose event handler Note that this
        # function is called when the engine is restarted (through "Reload
        # Engine and Apps")

        # Important: Copy the list of dialogs still opened since the call to
        # close() will modify created_qt_dialogs
        dialogs_still_opened = self.created_qt_dialogs[:]

        for dialog in dialogs_still_opened:
            dialog.close()

    def pre_app_init(self):
        """
        Sets up the engine into an operational state. This method called before
        any apps are loaded.
        """
        from sgtk.platform.qt import QtCore

        self.logger.debug("%s: Pre app init..." % (self,))

        # unicode characters returned by the shotgun api need to be converted
        # to display correctly in all of the app windows tell QT to interpret C
        # strings as utf-8
        utf8 = QtCore.QTextCodec.codecForName("utf-8")
        QtCore.QTextCodec.setCodecForCStrings(utf8)
        self.logger.debug("set utf-8 codec for widget text")

        # Set the Qt flag to propogate widget styles applied through style sheets to
        # the child widgets.
        QtCore.QCoreApplication.setAttribute(
            QtCore.Qt.AA_UseStyleSheetPropagationInWidgetStyles, True
        )
        # Initialize a Qt palette, font and stylesheet that will be applied to each
        # engine app, on show.
        self._init_app_palette()
        self._init_style_sheet()
        self._init_app_font()

    def post_app_init(self):
        """
        Executed by the system and typically implemented by deriving classes.
        """

        self.logger.debug("%s: Post app init...", self)

        self.logger.debug("%s: Initializing QtApp", self)
        from sgtk.platform.qt import QtGui

        self._qt_app = QtGui.QApplication.instance()

        # import python/tk_sketchbook module
        self._tk_sketchbook = self.import_module("tk_sketchbook")

        # init menu
        self.menu = self._tk_sketchbook.SketchBookMenu(engine=self)
        self.refresh_menu()
        self.logger.debug("Got menu %s", self.menu)

        self.logger.debug("Installed commands are %s.", self.commands)

        path = os.environ.get("SGTK_FILE_TO_OPEN", None)
        if path:
            self.operations.open_file(path)

        # Run apps configured for launch at startup
        # In basic config, Shotgun Panel
        # In advanced config, Workfiles
        self._run_app_instance_commands()

    def post_context_change(self, old_context, new_context):
        """
        Runs after a context change has occurred.

        :param old_context: The previous context.
        :param new_context: The current context.
        """

        self.logger.debug("%s: Post context change...", self)
        if self.context_change_allowed:
            self.logger.debug("Refreshing with menu object %s.", self.menu)
            sketchbook_api.refresh_menu(self.menu.create())

    def refresh_menu(self):
        self.logger.debug("Refreshing with menu object %s.", self.menu)
        sketchbook_api.refresh_menu(self.menu.create())

    def run_command(self, commandName):
        self.menu.doCommand(commandName)

    def refresh_context(self):
        logger.debug("Refreshing the context")

        # Get the path of the current open Maya scene file.
        new_path = sketchbook_api.current_file_path()

        if new_path is None:
            # This is a File->New call, so we just leave the engine in the
            # current context and move on.
            logger.debug("New file call, aborting the refresh of the engine.")
            return

        # this file could be in another project altogether, so create a new API
        # instance.
        try:
            tk = sgtk.sgtk_from_path(new_path)
            logger.debug("Extracted sgtk instance: '%r' from path: '%r'", tk, new_path)

        except sgtk.TankError as e:
            logger.exception("Could not execute sgtk_from_path('%s')" % e)
            return

        # Construct a new context for this path:
        ctx = tk.context_from_path(new_path, self.context)
        logger.debug("Context for path %s is %r", new_path, ctx)

        if ctx != self.context:
            logger.debug("Changing the context to '%r", ctx)
            self.change_context(ctx)

    @property
    def host_info(self):
        self.logger.debug("%s: Fetching host info...", self)
        return sketchbook_api.host_info()

    @property
    def context_change_allowed(self):
        """
        Specifies that context changes are allowed by the engine.
        """
        return True

    @property
    def style_sheet(self):
        """
        The Qt style sheet file (.qss) the engine applies to all its apps.
        """

        if self._style_sheet is None:
            from sgtk.platform import constants

            return os.path.join(self.disk_location, constants.BUNDLE_STYLESHEET_FILE)

        return self._style_sheet

    def _emit_log_message(self, handler, record):
        """
        Called by the engine whenever a new log message is available.
        All log messages from the toolkit logging namespace will be passed to this method.

        :param handler: Log handler that this message was dispatched from
        :type handler: :class:`~python.logging.LogHandler`
        :param record: Std python logging record
        :type record: :class:`~python.logging.LogRecord`
        """

        if record.levelno < logging.INFO:
            formatter = logging.Formatter("Debug: Shotgun %(basename)s: %(message)s")
        else:
            formatter = logging.Formatter("Shotgun %(basename)s: %(message)s")

        msg = formatter.format(record)
        SketchBookLogger.logMessage(msg)

    def _run_app_instance_commands(self):
        """
        Runs the series of app instance commands listed in the 'run_at_startup'
        setting of the environment configuration yaml file.
        """

        # Build a dictionary mapping app instance names to dictionaries of
        # commands they registered with the engine.
        app_instance_commands = {}
        for (command_name, value) in self.commands.items():
            app_instance = value["properties"].get("app")
            if app_instance:
                # Add entry 'command name: command function' to the command
                # dictionary of this app instance.
                command_dict = app_instance_commands.setdefault(
                    app_instance.instance_name, {}
                )
                command_dict[command_name] = value["callback"]

        commands_to_run = []
        # Run the series of app instance commands listed in the
        # 'run_at_startup' setting.
        for app_setting_dict in self.get_setting("run_at_startup", []):

            app_instance_name = app_setting_dict["app_instance"]
            # Menu name of the command to run or '' to run all commands of the
            # given app instance.
            setting_command_name = app_setting_dict["name"]

            # Retrieve the command dictionary of the given app instance.
            command_dict = app_instance_commands.get(app_instance_name)

            if command_dict is None:
                self.logger.warning(
                    "%s configuration setting 'run_at_startup' requests app '%s' that is not installed.",
                    self.name,
                    app_instance_name,
                )
            else:
                if not setting_command_name:
                    # Run all commands of the given app instance.
                    for (command_name, command_function) in command_dict.items():
                        self.logger.debug(
                            "%s startup running app '%s' command '%s'.",
                            self.name,
                            app_instance_name,
                            command_name,
                        )
                        commands_to_run.append(command_function)
                else:
                    # Run the command whose name is listed in the
                    # 'run_at_startup' setting.
                    command_function = command_dict.get(setting_command_name)
                    if command_function:
                        self.logger.debug(
                            "%s startup running app '%s' command '%s'.",
                            self.name,
                            app_instance_name,
                            setting_command_name,
                        )
                        commands_to_run.append(command_function)
                    else:
                        known_commands = ", ".join(
                            "'%s'" % name for name in command_dict
                        )
                        self.logger.warning(
                            "%s configuration setting 'run_at_startup' requests app '%s' unknown command '%s'. "
                            "Known commands: %s",
                            self.name,
                            app_instance_name,
                            setting_command_name,
                            known_commands,
                        )

        # no commands to run. just bail
        if not commands_to_run:
            return

        # finally, run the commands
        for command in commands_to_run:
            command()

    def _get_qt_style(self):
        """
        Convenience method to create the Qt style to be used by the engine. This is
        to help keep styles consistent. The style object will be destroyed with the
        widget that it is set to, which means this style object is created each time
        we call _create_dialog.
        """
        from sgtk.platform.qt import QtGui

        return QtGui.QStyleFactory.create("fusion")

    def _init_style_sheet(self):
        """
        Read the engine style sheet and initialize the style sheet data that will
        be used by any app run by the engine.
        """

        with open(self.style_sheet, "rt") as style_sheet_file:
            self._app_style_sheet = style_sheet_file.read()
            self._app_style_sheet = self._resolve_sg_stylesheet_tokens(
                self._app_style_sheet
            )

    def _init_app_font(self):
        """
        Initialize a QFont object to be used by any app run by the engine.
        """
        from sgtk.platform.qt import QtGui

        self._app_font = QtGui.QFont()
        self._app_font.setPixelSize(11)

    def _init_app_palette(self):
        """
        Initialize a QPalette object and the dictionary mapping for style sheet
        constants to palette brush colors, to be used by any app run by the engine.

        NOTE: this uses the same palette as in :class:`sgtk.platform.Engine`
        :meth:`__initialize_dark_look_and_feel_qt5`, it would be ideal if this
        method was refactored to into two methods, one to initialize the QApplication
        with the QPalette, and one to create and return the QPalette -- this way
        we do not have to duplicate this code, and remain consistent with the
        rest of Toolkit.
        """
        from sgtk.platform.qt import QtGui

        app_style = self._get_qt_style()
        self._app_palette = app_style.standardPalette()

        # Disabled Brushes
        self._app_palette.setBrush(
            QtGui.QPalette.Disabled, QtGui.QPalette.Button, QtGui.QColor(80, 80, 80)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Disabled, QtGui.QPalette.Light, QtGui.QColor(97, 97, 97)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Disabled, QtGui.QPalette.Midlight, QtGui.QColor(59, 59, 59)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Disabled, QtGui.QPalette.Dark, QtGui.QColor(37, 37, 37)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Disabled, QtGui.QPalette.Mid, QtGui.QColor(45, 45, 45)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Disabled, QtGui.QPalette.Base, QtGui.QColor(42, 42, 42)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Disabled, QtGui.QPalette.Window, QtGui.QColor(68, 68, 68)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Disabled, QtGui.QPalette.Shadow, QtGui.QColor(0, 0, 0)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Disabled,
            QtGui.QPalette.AlternateBase,
            self._app_palette.color(
                QtGui.QPalette.Disabled, QtGui.QPalette.Base
            ).lighter(110),
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Disabled,
            QtGui.QPalette.Text,
            self._app_palette.color(
                QtGui.QPalette.Disabled, QtGui.QPalette.Base
            ).lighter(250),
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Disabled,
            QtGui.QPalette.Link,
            self._app_palette.color(
                QtGui.QPalette.Disabled, QtGui.QPalette.Base
            ).lighter(250),
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Disabled,
            QtGui.QPalette.LinkVisited,
            self._app_palette.color(
                QtGui.QPalette.Disabled, QtGui.QPalette.Base
            ).lighter(110),
        )

        # Active Brushes
        self._app_palette.setBrush(
            QtGui.QPalette.Active,
            QtGui.QPalette.WindowText,
            QtGui.QColor(200, 200, 200),
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Button, QtGui.QColor(75, 75, 75)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Active,
            QtGui.QPalette.ButtonText,
            QtGui.QColor(200, 200, 200),
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Light, QtGui.QColor(97, 97, 97)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Midlight, QtGui.QColor(59, 59, 59)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Dark, QtGui.QColor(37, 37, 37)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Mid, QtGui.QColor(45, 45, 45)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Text, QtGui.QColor(200, 200, 200)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Link, QtGui.QColor(200, 200, 200)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.LinkVisited, QtGui.QColor(97, 97, 97)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.BrightText, QtGui.QColor(37, 37, 37)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Base, QtGui.QColor(42, 42, 42)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Window, QtGui.QColor(68, 68, 68)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Shadow, QtGui.QColor(0, 0, 0)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Active,
            QtGui.QPalette.AlternateBase,
            self._app_palette.color(QtGui.QPalette.Active, QtGui.QPalette.Base).lighter(
                110
            ),
        )

        # Inactive Brushes
        self._app_palette.setBrush(
            QtGui.QPalette.Inactive,
            QtGui.QPalette.WindowText,
            QtGui.QColor(200, 200, 200),
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Button, QtGui.QColor(75, 75, 75)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Inactive,
            QtGui.QPalette.ButtonText,
            QtGui.QColor(200, 200, 200),
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Light, QtGui.QColor(97, 97, 97)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Midlight, QtGui.QColor(59, 59, 59)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Dark, QtGui.QColor(37, 37, 37)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Mid, QtGui.QColor(45, 45, 45)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Text, QtGui.QColor(200, 200, 200)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Link, QtGui.QColor(200, 200, 200)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Inactive,
            QtGui.QPalette.LinkVisited,
            QtGui.QColor(97, 97, 97),
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.BrightText, QtGui.QColor(37, 37, 37)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Base, QtGui.QColor(42, 42, 42)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Window, QtGui.QColor(68, 68, 68)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Shadow, QtGui.QColor(0, 0, 0)
        )
        self._app_palette.setBrush(
            QtGui.QPalette.Inactive,
            QtGui.QPalette.AlternateBase,
            self._app_palette.color(
                QtGui.QPalette.Inactive, QtGui.QPalette.Base
            ).lighter(110),
        )

        # Initialize the mapping of style sheet constants to palette brush colors.
        self._palette_brushes = {
            "SG_PAL_DARK": self._app_palette.dark().color().name(),
            "SG_PAL_BASE": self._app_palette.base().color().name(),
            "SG_PAL_MID": self._app_palette.mid().color().name(),
            "SG_PAL_MIDLIGHT": self._app_palette.midlight().color().name(),
            "SG_PAL_LIGHT": self._app_palette.light().color().name(),
            "SG_PAL_TEXT": self._app_palette.text().color().name(),
            "SG_PAL_ALTERNATE_BASE": self._app_palette.alternateBase().color().name(),
            "SG_PAL_BRIGHT_TEXT": self._app_palette.brightText().color().name(),
            "SG_PAL_BUTTON": self._app_palette.button().color().name(),
            "SG_PAL_BUTTON_TEXT": self._app_palette.buttonText().color().name(),
            "SG_PAL_HIGHLIGHT": self._app_palette.highlight().color().name(),
            "SG_PAL_HIGHLIGHTED_TEXT": self._app_palette.highlightedText()
            .color()
            .name(),
            "SG_PAL_LINK": self._app_palette.link().color().name(),
            "SG_PAL_LINK_VISITED": self._app_palette.linkVisited().color().name(),
            "SG_PAL_PLACEHOLDER_TEXT": self._app_palette.placeholderText()
            .color()
            .name(),
            "SG_PAL_SHADOW": self._app_palette.shadow().color().name(),
            "SG_PAL_TOOLTIP_BASE": self._app_palette.toolTipBase().color().name(),
            "SG_PAL_TOOLTIP_TEXT": self._app_palette.toolTipText().color().name(),
            "SG_PAL_WINDOW": self._app_palette.window().color().name(),
            "SG_PAL_WINDOW_TEXT": self._app_palette.windowText().color().name(),
        }

    def _apply_widget_style(self, widget, style, set_style_sheet=False):
        """
        Apply widget style, palette, and font defined by the engine. Styles are applied to each widget,
        instead of the QApplication since Sketchbook shares the application object and does not use
        the same dark theme as Shotgun Toolkit.

        :param widget: The QWidget to set the style to.
        :param style: The QCommonStyle to apply to the widget.
        :param set_style_sheet: True will set the style sheet on the widget. This is only needed
        for top-level widgets, since style sheets propogate to child widgets.
        """

        widget.setStyle(style)
        widget.setPalette(self._app_palette)
        widget.setFont(self._app_font)

        if set_style_sheet:
            # Make sure not to overrite any existing widget style sheet data by appending the style
            # sheet data from the engine.
            style_sheet = "{current_style_sheet}\n\n{append_style_sheet}".format(
                current_style_sheet=widget.styleSheet(),
                append_style_sheet=self._app_style_sheet,
            )
            widget.setStyleSheet(style_sheet)
            widget.update()

            self.logger.debug(
                "{engine}: Applied style sheet to widget '{widget}'\n\n{style}".format(
                    engine=self, widget=widget.objectName(), style=style_sheet
                )
            )

            # Add a file watcher to the engine .qss file. This should only be turned on
            # for debugging, else it will slow down production performance.
            if os.getenv("SHOTGUN_QSS_FILE_WATCHER", None) == "1":
                try:
                    self._add_stylesheet_file_watcher(self.style_sheet, widget)
                except Exception as e:
                    # We don't want the watcher to cause any problem, so we catch
                    # errors but issue a warning so the developer knows that interactive
                    # styling is off.
                    self.log_warning("Unable to set qss file watcher: {}".format(e))

    def _create_dialog(self, title, bundle, widget, parent):
        """
        Override the :class:`sgtk.platform.Engine` :meth:`_create_dialog`.

        First call the overriden method to create the dialog, then apply the app style
        defined by the engine to the dialog widget. Qt style is applied on a per app
        basis since Sketchbook's light themed style conflicts with Shotgun Toolkit's
        dark theme, and we cannot simply call :class:`sgtk.platform.Engine`
        :meth:`_initialize_dark_look_and_feel` which sets the style and palette on the
        shared QtGui.QApplication (e.g. Sketchbook will then be affected with the dark
        style applied).

        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget: A QWidget instance to be embedded in the newly created dialog.
        :type widget: :class:`PySide.QtGui.QWidget`
        """
        from sgtk.platform.qt import QtGui

        dialog = super(SketchBookEngine, self)._create_dialog(
            title, bundle, widget, parent
        )

        # Set the style sheet on the most top-level widget (the dialog), and the style
        # sheet will be propogated to all children.
        set_style_sheet = True
        app_style = self._get_qt_style()
        widgets = [dialog]

        while widgets:
            widget = widgets.pop()

            # We can only apply style to QWidget objects.
            if isinstance(widget, QtGui.QWidget):
                self._apply_widget_style(widget, app_style, set_style_sheet)
                set_style_sheet = False

            # Apply style to each child widget.
            widgets.extend(widget.children())

        return dialog

    def _resolve_sg_stylesheet_tokens(self, style_sheet):
        """
        Override the :class:`sgtk.platform.Engine` :meth:`show_dialog`.

        First call the overriden method, then further process the style sheet to resolve
        any palette specific tokens.

        For example, "{{SG_PAL_BASE}}" is converted to the engine's palette base brush color.

        :param style_sheet: Stylesheet string to process
        :returns: Stylesheet string with replacements applied
        """

        processed_style_sheet = super(
            SketchBookEngine, self
        )._resolve_sg_stylesheet_tokens(style_sheet)

        for (token, value) in self._palette_brushes.items():
            processed_style_sheet = processed_style_sheet.replace(
                "{{%s}}" % token, value
            )

        return processed_style_sheet
