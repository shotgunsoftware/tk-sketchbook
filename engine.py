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

import sgtk
from tank.platform import Engine

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

        # SketchBook's palette differs from Toolkit, so the engine will let SketchBook
        # use the QApplication palette and will maintain its own style sheet and palette
        # to apply to only Toolkit Qt widgets and override any necessary styles.
        self._style_sheet = None
        self._style_sheet_data = None
        self._palette = None

        # List of all available QPalette brushes used for style sheets.
        # Reference: https://doc.qt.io/qt-5/stylesheet-reference.html#paletterole
        self._palette_brushes = [
            "alternate-base",
            "base",
            "bright-text",
            "button",
            "button-text",
            "dark",
            "highlight",
            "highlighted-text",
            "light",
            "link",
            "link-visited",
            "mid",
            "midlight",
            "shadow",
            "text",
            "window",
            "window-text",
        ]

        super(SketchBookEngine, self).__init__(tk, context, engine_instance_name, env)

    @property
    def host_info(self):
        """
        Return information about host DCC, SketchBook.
        """

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
        The file path to the engine's Qt style sheet.
        """

        if self._style_sheet is None:
            from sgtk.platform import constants

            self._style_sheet = os.path.join(
                self.disk_location, constants.BUNDLE_STYLESHEET_FILE
            )

        return self._style_sheet

    @property
    def style_sheet_data(self):
        """
        Return the style sheet data loaded from the engine's style.qss file.
        """

        if self._style_sheet_data is None:
            self._style_sheet_data = self._load_style_sheet()

        return self._style_sheet_data

    @staticmethod
    def get_current_engine():
        """
        Return the engine that is currently running. This is used by the SketchBook
        C++/Python API to determine if the engine it holds a reference to is the stale
        or up to date.
        """

        return sgtk.platform.current_engine()

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

        self._init_qt_style()

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
        """
        Call the SketchBook API to refresh the Shotgun menu.
        """

        self.logger.debug("Refreshing with menu object %s.", self.menu)
        sketchbook_api.refresh_menu(self.menu.create())

    def run_command(self, commandName):
        """
        Request the menu to run the given command, by name.
        """

        self.menu.do_command(commandName)

    def refresh_context(self):
        """
        Refresh the Shotgun context.
        """

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

    def do_log(self, message):
        """
        Log a debug message.
        """

        self.logger.debug(message)

    def palette(self):
        """
        Return the custom QPalette defiend by the engine. We cannot use the QApplication
        palette since SketchBook's style and palette is different than Toolkit's.
        """

        return self._palette

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

    def _init_qt_style(self):
        """
        Initialize the necessary attributes and properties to allow the engine to
        manage a separate Qt style than SketchBook itself.
        """
        from sgtk.platform.qt import QtCore, QtGui

        # Set the Qt flag to propogate widget styles applied through style sheets to
        # the child widgets.
        QtCore.QCoreApplication.setAttribute(
            QtCore.Qt.AA_UseStyleSheetPropagationInWidgetStyles, True
        )

        # Initialize the engine's QPalette and then load in the engine's style.qss
        # Must be done in this order since the style sheet will use the engine's palette
        self._init_palette()
        self._load_style_sheet()

        # Monkey patch the QWidget palette method to ensure all Toolkit QWidgets use the
        # palette defined by the SketchBook engine, instead of the QApplication.
        QtGui.QWidget.palette = self.palette

        # Monkey patch the QWidget setStyleSheet method to ensure that the style sheet
        # 'palette' token resolution uses the palette set up by this engine. For an
        # example, see tk-framework-qtwidgets shotgun_menu.py.
        qt_widget_set_style_sheet = QtGui.QWidget.setStyleSheet

        def patch_set_style_sheet(qt_widget, style_sheet):
            qss_data = self._resolve_palette_stylesheet_tokens(style_sheet)
            qt_widget_set_style_sheet(qt_widget, qss_data)

        QtGui.QWidget.setStyleSheet = patch_set_style_sheet

    def _load_style_sheet(self):
        """
        Read the engine style sheet and initialize the style sheet data that will
        be applied to any dialog created.
        """

        qss_data = ""
        with open(self.style_sheet, "rt") as style_sheet_file:
            qss_data = style_sheet_file.read()
            qss_data = self._resolve_palette_stylesheet_tokens(qss_data)

        return qss_data

    def _init_palette(self):
        """
        Initialize the engine's QPalette. This palette set up is copied from
        :class:`sgtk.platform.Engine` :meth:`__initialize_dark_look_and_feel_qt5`,
        and tweaked as necessary.

        It would be nice if tk-core split this method up so that we could get
        the QPalette it uses, without applying it to the QApplication.
        """

        from sgtk.platform.qt import QtGui

        # Use the QApplication style to get the base palette.
        app_style = QtGui.QApplication.instance().style()
        self._palette = app_style.standardPalette()

        # Disabled Brushes
        self._palette.setBrush(
            QtGui.QPalette.Disabled, QtGui.QPalette.Button, QtGui.QColor(80, 80, 80)
        )
        self._palette.setBrush(
            QtGui.QPalette.Disabled, QtGui.QPalette.Light, QtGui.QColor(97, 97, 97)
        )
        self._palette.setBrush(
            QtGui.QPalette.Disabled, QtGui.QPalette.Midlight, QtGui.QColor(59, 59, 59)
        )
        self._palette.setBrush(
            QtGui.QPalette.Disabled, QtGui.QPalette.Dark, QtGui.QColor(37, 37, 37)
        )
        self._palette.setBrush(
            QtGui.QPalette.Disabled, QtGui.QPalette.Mid, QtGui.QColor(45, 45, 45)
        )
        self._palette.setBrush(
            QtGui.QPalette.Disabled, QtGui.QPalette.Base, QtGui.QColor(42, 42, 42)
        )
        self._palette.setBrush(
            QtGui.QPalette.Disabled, QtGui.QPalette.Window, QtGui.QColor(68, 68, 68)
        )
        self._palette.setBrush(
            QtGui.QPalette.Disabled, QtGui.QPalette.Shadow, QtGui.QColor(0, 0, 0)
        )
        self._palette.setBrush(
            QtGui.QPalette.Disabled,
            QtGui.QPalette.AlternateBase,
            self._palette.color(QtGui.QPalette.Disabled, QtGui.QPalette.Base).lighter(
                110
            ),
        )
        self._palette.setBrush(
            QtGui.QPalette.Disabled,
            QtGui.QPalette.Text,
            self._palette.color(QtGui.QPalette.Disabled, QtGui.QPalette.Base).lighter(
                250
            ),
        )
        self._palette.setBrush(
            QtGui.QPalette.Disabled,
            QtGui.QPalette.Link,
            self._palette.color(QtGui.QPalette.Disabled, QtGui.QPalette.Base).lighter(
                250
            ),
        )
        self._palette.setBrush(
            QtGui.QPalette.Disabled,
            QtGui.QPalette.LinkVisited,
            self._palette.color(QtGui.QPalette.Disabled, QtGui.QPalette.Base).lighter(
                110
            ),
        )

        # Active Brushes
        self._palette.setBrush(
            QtGui.QPalette.Active,
            QtGui.QPalette.WindowText,
            QtGui.QColor(200, 200, 200),
        )
        self._palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Button, QtGui.QColor(75, 75, 75)
        )
        self._palette.setBrush(
            QtGui.QPalette.Active,
            QtGui.QPalette.ButtonText,
            QtGui.QColor(200, 200, 200),
        )
        self._palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Light, QtGui.QColor(97, 97, 97)
        )
        self._palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Midlight, QtGui.QColor(59, 59, 59)
        )
        self._palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Dark, QtGui.QColor(37, 37, 37)
        )
        self._palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Mid, QtGui.QColor(45, 45, 45)
        )
        self._palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Text, QtGui.QColor(200, 200, 200)
        )
        self._palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Link, QtGui.QColor(200, 200, 200)
        )
        self._palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.LinkVisited, QtGui.QColor(97, 97, 97)
        )
        self._palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.BrightText, QtGui.QColor(37, 37, 37)
        )
        self._palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Base, QtGui.QColor(42, 42, 42)
        )
        self._palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Window, QtGui.QColor(68, 68, 68)
        )
        self._palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Shadow, QtGui.QColor(0, 0, 0)
        )
        self._palette.setBrush(
            QtGui.QPalette.Active,
            QtGui.QPalette.AlternateBase,
            self._palette.color(QtGui.QPalette.Active, QtGui.QPalette.Base).lighter(
                110
            ),
        )
        self._palette.setBrush(
            QtGui.QPalette.Active, QtGui.QPalette.Highlight, QtGui.QColor(24, 166, 227)
        )
        self._palette.setBrush(
            QtGui.QPalette.Active,
            QtGui.QPalette.HighlightedText,
            QtGui.QColor(240, 240, 240),
        )

        # Inactive Brushes
        self._palette.setBrush(
            QtGui.QPalette.Inactive,
            QtGui.QPalette.WindowText,
            QtGui.QColor(200, 200, 200),
        )
        self._palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Button, QtGui.QColor(75, 75, 75)
        )
        self._palette.setBrush(
            QtGui.QPalette.Inactive,
            QtGui.QPalette.ButtonText,
            QtGui.QColor(200, 200, 200),
        )
        self._palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Light, QtGui.QColor(97, 97, 97)
        )
        self._palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Midlight, QtGui.QColor(59, 59, 59)
        )
        self._palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Dark, QtGui.QColor(37, 37, 37)
        )
        self._palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Mid, QtGui.QColor(45, 45, 45)
        )
        self._palette.setBrush(
            QtGui.QPalette.Inactive,
            QtGui.QPalette.Text,
            QtGui.QColor(200, 200, 200),
        )
        self._palette.setBrush(
            QtGui.QPalette.Inactive,
            QtGui.QPalette.Link,
            QtGui.QColor(200, 200, 200),
        )
        self._palette.setBrush(
            QtGui.QPalette.Inactive,
            QtGui.QPalette.LinkVisited,
            QtGui.QColor(97, 97, 97),
        )
        self._palette.setBrush(
            QtGui.QPalette.Inactive,
            QtGui.QPalette.BrightText,
            QtGui.QColor(37, 37, 37),
        )
        self._palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Base, QtGui.QColor(42, 42, 42)
        )
        self._palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Window, QtGui.QColor(68, 68, 68)
        )
        self._palette.setBrush(
            QtGui.QPalette.Inactive, QtGui.QPalette.Shadow, QtGui.QColor(0, 0, 0)
        )
        self._palette.setBrush(
            QtGui.QPalette.Inactive,
            QtGui.QPalette.AlternateBase,
            self._palette.color(QtGui.QPalette.Inactive, QtGui.QPalette.Base).lighter(
                110
            ),
        )

    def _resolve_palette_stylesheet_tokens(self, style_sheet):
        """
        Search and replace all palette(BRUSH_NAME) tokens with the corresponding engine's
        palette brush value matching the BRUSH_NAME.

        :param style_sheet: The Qt style sheet to resolve.
        :return: The resolved Qt style sheet
        """

        processed_style_sheet = style_sheet

        for brush in self._palette_brushes:
            qt_brush = "".join(word.title() for word in brush.split("-"))
            qt_brush = qt_brush[0].lower() + qt_brush[1:]
            try:
                processed_style_sheet = processed_style_sheet.replace(
                    "palette(%s)" % brush,
                    getattr(self._palette, qt_brush)().color().name(),
                )

            except AttributeError:
                # Log the error, but don't cause the engine to fail.
                self.logger.error(
                    "{engine}: Invalid palette brush {brush}".format(
                        engine=self, brush=brush
                    )
                )

        return processed_style_sheet

    def _create_dialog(self, title, bundle, widget, parent):
        """
        Override the :class:`sgtk.platform.Engine` :meth:`_create_dialog`.

        First call the overriden method to create the dialog. Then append the
        engine's style sheet data to the created dialogs style sheet to
        override any necessary styles to the dialog and all decendent widgets.

        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget: A QWidget instance to be embedded in the newly created dialog.
        :type widget: :class:`PySide.QtGui.QWidget`
        """
        from sgtk.platform.qt import QtGui

        dialog = super(SketchBookEngine, self)._create_dialog(
            title, bundle, widget, parent
        )

        # Search and replace any palette(BRUSH_NAME) with the palette values defined by this engine.
        # This ensures any widget style sheet set with "palette(BRUSH_NAME)" will resovle to the
        # palette defined by this engine (e.g. if style sheet applied to widget before we call
        # set palette above, the widget style sheet will resolve to the incorrect palette).
        dialog_style_sheet = self._resolve_palette_stylesheet_tokens(
            dialog.styleSheet()
        )
        # Append the engine's style sheet data
        dialog_style_sheet += "\n\n{}".format(self.style_sheet_data)
        dialog.setStyleSheet(dialog_style_sheet)

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

        return dialog
