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

        # The engine style sheet to help set global styles for the Sketchbook apps, since
        # the engine does not apply any styles to the QApplication object.
        self._style_sheet = None

        # The style sheet data and palette to apply to any app run by the engine.
        self._app_style_sheet = None
        self._app_palette = None

        # List of all available QPalette brushes used for style sheets.
        self._palette_brushes = [
            "dark",
            "base",
            "mid",
            "midlight",
            "light",
            "text",
            "alternateBase",
            "brightText",
            "button",
            "buttonText",
            "highlight",
            "link",
            "linkVisited",
            "shadow",
            "toolTipBase",
            "toolTipText",
            "window",
            "windowText",
        ]

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
        self._init_app_style_sheet()
        self._init_app_font()

        # Temporarily monkey patch QToolButton and QMenu to resolve a Qt 5.15.0 bug (seems that it will fixed in 5.15.1)
        # where QToolButton menu will open only on primary screen.
        self._monkey_patch_qtoolbutton()
        self._monkey_patch_qmenu()

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
        self.menu.do_command(commandName)

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

    def do_log(self, message):
        self.logger.debug(message)

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

    def _init_app_style_sheet(self):
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

    def _apply_widget_style(self, widget, style, append_global_styles=False):
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

        # Search and replace any palette(BRUSH_NAME) with the palette values defined by this engine.
        # This ensures any widget style sheet set with "palette(BRUSH_NAME)" will resovle to the
        # palette defined by this engine (e.g. if style sheet applied to widget before we call
        # set palette above, the widget style sheet will resolve to the incorrect palette).
        widget_style_sheet = self._resolve_palette_stylesheet_tokens(
            widget.styleSheet()
        )

        if append_global_styles:
            # Make sure not to override any existing widget style sheet data by appending the style
            # sheet data from the engine.
            widget_style_sheet += "\n\n{}".format(self._app_style_sheet)

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

        widget.setStyleSheet(widget_style_sheet)
        widget.update()

        self.logger.debug(
            "{engine}: Applied style sheet to widget '{widget}'\n\n{style}".format(
                engine=self, widget=widget.objectName(), style=widget_style_sheet
            )
        )

    def _resolve_palette_stylesheet_tokens(self, style_sheet):
        """
        Search and replace all palette(BRUSH_NAME) strings with the corresponding palette
        brush value matching the BRUSH_NAME. This ensures that all style sheets using
        "palette(BRUSH_NAME)" will resovle to the palette defined by this engine
        (e.g. if style sheet applied to widget before the engine sets the palette,
        the widget style sheet will resolve to an incorrect palette.
        :param style_sheet: The QT style sheet to resolve.
        """

        processed_style_sheet = style_sheet

        for brush in self._palette_brushes:
            try:
                processed_style_sheet = processed_style_sheet.replace(
                    "palette(%s)" % brush,
                    getattr(self._app_palette, brush)().color().name(),
                )

            except AttributeError:
                # Log the error, but don't cause the engine to fail.
                self.logger.error(
                    "{engine}: Invalid palette brush {brush}".format(
                        engine=self, brush=brush
                    )
                )

        return processed_style_sheet

    def _resolve_sg_stylesheet_tokens(self, style_sheet):
        """
        Override the :class:`sgtk.platform.Engine` :meth:`show_dialog`.
        First call the overriden method, then further process the style sheet to resolve
        any palette specific tokens.
        For example, palette(base) is converted to the engine's palette base brush color.
        :param style_sheet: Stylesheet string to process
        :returns: Stylesheet string with replacements applied
        """

        processed_style_sheet = super(
            SketchBookEngine, self
        )._resolve_sg_stylesheet_tokens(style_sheet)

        processed_style_sheet = self._resolve_palette_stylesheet_tokens(
            processed_style_sheet
        )

        return processed_style_sheet

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

        # Append global styles defined in tk-sketchbook/style.qss to the most top-level
        # widget (the dialog), and these styles will be propogated to all children, but not
        # override any styles applied directly to the widget.
        append_global_styles = True
        app_style = self._get_qt_style()
        widgets = [dialog]

        while widgets:
            widget = widgets.pop()

            # We can only apply style to style aware widgets.
            if isinstance(widget, QtGui.QWidget) or hasattr(widget, "setStyle"):
                self._apply_widget_style(widget, app_style, append_global_styles)
                append_global_styles = False

            # Apply style to each child widget.
            widgets.extend(widget.children())

        return dialog

    def _monkey_patch_qtoolbutton(self):
        """
        Temporary method to monkey patch the QToolButton to fix opening a QToolButton
        menu on the correct screen (Qt 5.15.0 bug QTBUG-84462).
        """

        from sgtk.platform.qt import QtGui

        class QToolButtonPatch(QtGui.QToolButton):
            """
            A QToolButton object with the exception of modifying the setMenu and
            addAction methods.
            """

            # Define QToolButtonPatch class field for menu that will be created to
            # hold any actions added to the QToolButtonPatch, without a menu object.
            _patch_menu = None

            def setMenu(self, menu):
                """
                Override the setMenu method to link the QToolButton to the menu. The menu
                will need to know which QToolButton it is being opened from on the showEvent
                inorder to repositiong itself correctly to the button.

                :param menu: A QMenu object to set for this button.
                """
                menu.patch_toolbutton = self
                super(QToolButtonPatch, self).setMenu(menu)

            def addAction(self, action):
                """
                Override the addAction method to create a QMenu object here, that will hold
                any button menu actions. Normally, the QMenu object would be created on show,
                in the C++ source QToolButton::popupTimerDone(), but since we've monkey patched
                the QMenu object, we need to create it on the Python side to make sure we use our
                QMenuPatch object instead of QMenu.

                :param action: The QAction object to add to our QToolButton menu.
                """

                if self.menu() is None:
                    self._patch_menu = QtGui.QMenu()
                    self.setMenu(self._patch_menu)

                self.menu().addAction(action)

        # All QToolButtons will now be a QToolButtonPatch.
        QtGui.QToolButton = QToolButtonPatch

    def _monkey_patch_qmenu(self):
        """
        Temporary method to monkey patch the QMenu to fix opening a QToolButton menu on
        the correct screen (Qt 5.15.0 bug QTBUG-84462).
        """

        from sgtk.platform.qt import QtCore, QtGui

        class QMenuPatch(QtGui.QMenu):
            """
            A QMenu object with the exception of modifying the showEvent method.
            """

            def showEvent(self, event):
                """
                Override the showEvent method in order to reposition the menu correctly.
                """

                # Only apply menu position patch for menus that are shown from QToolButtons.
                fix_menu_pos = hasattr(self, "patch_toolbutton") and isinstance(
                    self.patch_toolbutton, QtGui.QToolButton
                )

                if fix_menu_pos:
                    # Get the orientation for the menu.
                    horizontal = True
                    if isinstance(self.patch_toolbutton.parentWidget(), QtGui.QToolBar):
                        if (
                            self.patch_toolbutton.parentWidget().orientation()
                            == QtCore.Qt.Vertical
                        ):
                            horizontal = False

                    # Get the correct position for the menu.
                    initial_pos = self.position_menu(
                        horizontal, self.sizeHint(), self.patch_toolbutton
                    )

                    # Save the geometry of the menu, we will need to re-set the geometry after
                    # the menu is shown to make sure the menu size is correct.
                    rect = QtCore.QRect(initial_pos, self.size())

                    # Move the menu to the correct position before the show event.
                    self.move(initial_pos)

                super(QMenuPatch, self).showEvent(event)

                if fix_menu_pos:
                    # Help correct the size of the menu.
                    self.setGeometry(rect)

            def position_menu(self, horizontal, size_hint, toolbutton):
                """
                This method is copied from the C++ source qtoolbutton.cpp in Qt 5.15.1 fix version.

                :param horizontal: The orientation of the QToolBar that the menu is shown for. This
                should be True if the menu is not in a QToolBar.
                :param size_hint: The QSize size hint for this menu.
                :param toolbutton: The QToolButtonPatch object that this menu is shown for. Used to
                positiong the menu correctly.
                """

                point = QtCore.QPoint()

                rect = toolbutton.rect()
                desktop = QtGui.QApplication.desktop()
                screen = desktop.availableGeometry(
                    toolbutton.mapToGlobal(rect.center())
                )

                if horizontal:
                    if toolbutton.isRightToLeft():
                        if (
                            toolbutton.mapToGlobal(QtCore.QPoint(0, rect.bottom())).y()
                            + size_hint.height()
                            <= screen.bottom()
                        ):
                            point = toolbutton.mapToGlobal(rect.bottomRight())

                        else:
                            point = toolbutton.mapToGlobal(
                                rect.topRight() - QtCore.QPoint(0, size_hint.height())
                            )

                        point.setX(point.x() - size_hint.width())

                    else:
                        if (
                            toolbutton.mapToGlobal(QtCore.QPoint(0, rect.bottom())).y()
                            + size_hint.height()
                            <= screen.bottom()
                        ):
                            point = toolbutton.mapToGlobal(rect.bottomLeft())

                        else:
                            point = toolbutton.mapToGlobal(
                                rect.topLeft() - QtCore.QPoint(0, size_hint.height())
                            )

                else:
                    if toolbutton.isRightToLeft():

                        if (
                            toolbutton.mapToGlobal(QtCore.QPoint(rect.left(), 0)).x()
                            - size_hint.width()
                            <= screen.x()
                        ):
                            point = toolbutton.mapToGlobal(rect.topRight())

                        else:
                            point = toolbutton.mapToGlobal(rect.topLeft())
                            point.setX(point.x() - size_hint.width())

                    else:
                        if (
                            toolbutton.mapToGlobal(QtCore.QPoint(rect.right(), 0)).x()
                            + size_hint.width()
                            <= screen.right()
                        ):
                            point = toolbutton.mapToGlobal(rect.topRight())

                        else:
                            point = toolbutton.mapToGlobal(
                                rect.topLeft() - QtCore.QPoint(size_hint.width(), 0)
                            )

                point.setX(
                    max(
                        screen.left(),
                        min(point.x(), screen.right() - size_hint.width()),
                    )
                )
                point.setY(point.y() + 1)
                return point

        # All QMenus will now be a QMenuPatch
        QtGui.QMenu = QMenuPatch
