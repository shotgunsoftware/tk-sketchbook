# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
A SketchBook engine for Tank.

"""

import tank
import sys
import traceback
import re
import time
import os
import logging
from tank.platform import Engine

import SketchBookLogger 

# Although the engine has logging already, this logger is needed for callback based logging
# where an engine may not be present.
logger = tank.LogManager.get_logger(__name__)

###############################################################################################
# The Tank SketchBook engine

class SketchBookEngine(Engine):
    """
    Toolkit engine for SketchBook.
    """

    __DIALOG_SIZE_CACHE = dict()

    @property
    def context_change_allowed(self):
        """
        Whether the engine allows a context change without the need for a restart.
        """
        return True

    @property
    def host_info(self):
        return { "name": "SketchBook", "version": "2020" }

    ##########################################################################################
    # init and destroy

    def init_engine(self):
        """
        Initializes the SketchBook engine.
        """
        self.logger.debug ("%s: Initializing...", self)

        # check that we are running an ok version of maya
        current_os = cmds.about(operatingSystem=True)
        if current_os not in ["mac", "win64", "linux64"]:
            raise tank.TankError (
            	"The current platform is not supported! Supported platforms "
                "are Mac, Linux 64 and Windows 64."
            )

        sketchbook_ver = cmds.about (version=True)
        if sketchbook_ver.startswith ("SketchBook "):
            sketchbook_ver = sketchbook_ver [10:]

        # Set the Maya project based on config
        self._set_project ()

        # add qt paths and dlls
        self._init_pyside ()

        # default menu name is Shotgun but this can be overriden
        # in the configuration to be Sgtk in case of conflicts
        self._menu_name = "Shotgun"

    def create_shotgun_menu(self):
        """
        Creates the main shotgun menu in maya.
        Note that this only creates the menu, not the child actions
        :return: bool
        """
        return False

    def post_app_init(self):
        """
        Called when all apps have initialized
        """
        self.create_shotgun_menu()

        # Run a series of app instance commands at startup.
        self._run_app_instance_commands()

    def destroy_engine(self):
        """
        Stops watching scene events and tears down menu.
        """
        self.logger.debug("%s: Destroying...", self)

        # Clear the dictionary of Maya panels to keep the garbage collector happy.
        self._maya_panel_dict = {}

        if self.get_setting("automatic_context_switch", True):
            # stop watching scene events
            self.__watcher.stop_watching()

        # clean up UI:
        if self.has_ui and pm.menu(self._menu_handle, exists=True):
            pm.deleteUI(self._menu_handle)

    def _init_pyside(self):
        """
        Handles the pyside init
        """

        # first see if pyside2 is present
        try:
            from PySide2 import QtGui
        except:
            # fine, we don't expect PySide2 to be present just yet
            self.logger.debug("PySide2 not detected - trying for PySide now...")
        else:
            # looks like pyside2 is already working! No need to do anything
            self.logger.debug("PySide2 detected - the existing version will be used.")
            return

        # then see if pyside is present
        try:
            from PySide import QtGui
        except:
            # must be a very old version of Maya.
            self.logger.debug("PySide not detected - it will be added to the setup now...")
        else:
            # looks like pyside is already working! No need to do anything
            self.logger.debug("PySide detected - the existing version will be used.")
            return

        if sys.platform == "darwin":
            pyside_path = os.path.join(self.disk_location, "resources","pyside112_py26_qt471_mac", "python")
            self.logger.debug("Adding pyside to sys.path: %s", pyside_path)
            sys.path.append(pyside_path)

        elif sys.platform == "win32":
            # default windows version of pyside for 2011 and 2012
            pyside_path = os.path.join(self.disk_location, "resources","pyside111_py26_qt471_win64", "python")
            self.logger.debug("Adding pyside to sys.path: %s", pyside_path)
            sys.path.append(pyside_path)
            dll_path = os.path.join(self.disk_location, "resources","pyside111_py26_qt471_win64", "lib")
            path = os.environ.get("PATH", "")
            path += ";%s" % dll_path
            os.environ["PATH"] = path

        elif sys.platform == "linux2":
            pyside_path = os.path.join(self.disk_location, "resources","pyside112_py26_qt471_linux", "python")
            self.logger.debug("Adding pyside to sys.path: %s", pyside_path)
            sys.path.append(pyside_path)

        else:
            self.logger.error("Unknown platform - cannot initialize PySide!")

        # now try to import it
        try:
            from PySide import QtGui
        except Exception, e:
            self.logger.error("PySide could not be imported! Apps using pyside will not "
                           "operate correctly! Error reported: %s", e)

    def show_dialog(self, title, *args, **kwargs):
        """
        If on Windows or Linux, this method will call through to the base implementation of
        this method without alteration. On OSX, we'll do some additional work to ensure that
        window parenting works properly, which requires some extra logic on that operating
        system beyond setting the dialog's parent.

        :param str title: The title of the dialog.

        :returns: the created widget_class instance
        """
        if sys.platform != "darwin":
            return super(MayaEngine, self).show_dialog(title, *args, **kwargs)
        else:
            if not self.has_ui:
                self.log_error("Sorry, this environment does not support UI display! Cannot show "
                               "the requested window '%s'." % title)
                return None

            from sgtk.platform.qt import QtCore, QtGui
            
            # create the dialog:
            dialog, widget = self._create_dialog_with_widget(title, *args, **kwargs)

            # When using the recipe here to get Z-depth ordering correct we also
            # inherit another feature that results in window size and position being
            # remembered. This size/pos retention happens across app boundaries, so
            # we would end up with one app inheriting the size from a previously
            # launched app, which was weird. To counteract that, we keep track of
            # the dialog's size before Maya gets ahold of it, and then resize it
            # right after it's shown. We'll also move the dialog to the center of
            # the desktop.
            center_screen = QtGui.QApplication.instance().desktop().availableGeometry(dialog).center()
            self.__DIALOG_SIZE_CACHE[title] = dialog.size()

            # TODO: Get an explanation and document why we're having to do this. It appears to be
            # a Maya-only solution, because similar problems in other integrations, namely Nuke,
            # are not resolved in the same way. This fix comes to us from the Maya dev team, but
            # we've not yet spoken with someone that can explain why it fixes the problem.
            dialog.setWindowFlags(QtCore.Qt.Window)
            dialog.setProperty("saveWindowPref", True)
            dialog.show()

            # The resize has to happen after the dialog is shown, and we need
            # to move the dialog after the resize, since center of screen will be
            # relative to the final size of the dialog.
            dialog.resize(self.__DIALOG_SIZE_CACHE[title])
            dialog.move(center_screen - dialog.rect().center())
            
            # lastly, return the instantiated widget
            return widget

    def _get_dialog_parent(self):
        """
        Get the QWidget parent for all dialogs created through
        show_dialog & show_modal.
        """
        # Find a parent for the dialog - this is the Maya mainWindow()
        from tank.platform.qt import QtGui
        import maya.OpenMayaUI as OpenMayaUI

        try:
            import shiboken2 as shiboken
        except ImportError:
            import shiboken

        ptr = OpenMayaUI.MQtUtil.mainWindow()
        parent = shiboken.wrapInstance(long(ptr), QtGui.QMainWindow)

        return parent

    @property
    def has_ui(self):
        """
        Detect and return if maya is running in batch mode
        """
        if cmds.about(batch=True):
            # batch mode or prompt mode
            return False
        else:
            return True

    ##########################################################################################
    # logging

    def _emit_log_message(self, handler, record):
        """
        Called by the engine to log messages in Maya script editor.
        All log messages from the toolkit logging namespace will be passed to this method.

        :param handler: Log handler that this message was dispatched from.
                        Its default format is "[levelname basename] message".
        :type handler: :class:`~python.logging.LogHandler`
        :param record: Standard python logging record.
        :type record: :class:`~python.logging.LogRecord`
        """
        # Give a standard format to the message:
        #     Shotgun <basename>: <message>
        # where "basename" is the leaf part of the logging record name,
        # for example "tk-multi-shotgunpanel" or "qt_importer".
        if record.levelno < logging.INFO:
            formatter = logging.Formatter("Debug: Shotgun %(basename)s: %(message)s")
        else:
            formatter = logging.Formatter("Shotgun %(basename)s: %(message)s")

        msg = formatter.format(record)
        SketchBookLogger.logMessage (msg)

    ##########################################################################################
    # scene and project management

    def _set_project(self):
        """
        Set the maya project
        """
        setting = self.get_setting("template_project")
        if setting is None:
            return

        tmpl = self.tank.templates.get(setting)
        fields = self.context.as_template_fields(tmpl)
        proj_path = tmpl.apply_fields(fields)
        self.logger.info("Setting Maya project to '%s'", proj_path)
        pm.mel.setProject(proj_path)

    ##########################################################################################
    # panel support

    def show_panel(self, panel_id, title, bundle, widget_class, *args, **kwargs):
        """
        Docks an app widget in a maya panel.

        :param panel_id: Unique identifier for the panel, as obtained by register_panel().
        :param title: The title of the panel
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget_class: The class of the UI to be constructed. This must derive from QWidget.

        Additional parameters specified will be passed through to the widget_class constructor.

        :returns: the created widget_class instance
        """
        from tank.platform.qt import QtCore, QtGui

        tk_maya = self.import_module("tk_maya")

        self.logger.debug("Begin showing panel %s", panel_id)

        # The general approach below is as follows:
        #
        # 1. First create our qt tk app widget using QT.
        #    parent it to the Maya main window to give it
        #    a well established parent. If the widget already
        #    exists, don't create it again, just retrieve its
        #    handle.
        #
        # 2. Now dock our QT control in a new panel tab of
        #    Maya Channel Box dock area. We use the
        #    Qt object name property to do the bind.
        #
        # 3. Lastly, since our widgets won't get notified about
        #    when the parent dock is closed (and sometimes when it
        #    needs redrawing), attach some QT event watchers to it
        #
        # Note: It is possible that the close event and some of the
        #       refresh doesn't propagate down to the widget because
        #       of a misaligned parenting: The tk widget exists inside
        #       the pane layout but is still parented to the main
        #       Maya window. It's possible that by setting up the parenting
        #       explicitly, the missing signals we have to compensate for
        #       may start to work. I tried a bunch of stuff but couldn't get
        #       it to work and instead resorted to the event watcher setup.

        # make a unique id for the app widget based off of the panel id
        widget_id = tk_maya.panel_generation.SHOTGUN_APP_PANEL_PREFIX + panel_id

        if pm.control(widget_id, query=1, exists=1):
            self.logger.debug("Reparent existing toolkit widget %s.", widget_id)
            # Find the Shotgun app panel widget for later use.
            for widget in QtGui.QApplication.allWidgets():
                if widget.objectName() == widget_id:
                    widget_instance = widget
                    # Reparent the Shotgun app panel widget under Maya main window
                    # to prevent it from being deleted with the existing Maya panel.
                    self.logger.debug("Reparenting widget %s under Maya main window.", widget_id)
                    parent = self._get_dialog_parent()
                    widget_instance.setParent(parent)
                    # The Shotgun app panel was retrieved from under an existing Maya panel.
                    break
        else:
            self.logger.debug("Create toolkit widget %s", widget_id)
            # parent the UI to the main maya window
            parent = self._get_dialog_parent()
            widget_instance = widget_class(*args, **kwargs)
            widget_instance.setParent(parent)
            # set its name - this means that it can also be found via the maya API
            widget_instance.setObjectName(widget_id)
            self.logger.debug("Created widget %s: %s", widget_id, widget_instance)
            # apply external stylesheet
            self._apply_external_styleshet(bundle, widget_instance)
            # The Shotgun app panel was just created.

        # Dock the Shotgun app panel into a new Maya panel in the active Maya window.
        maya_panel_name = tk_maya.panel_generation.dock_panel(self, widget_instance, title)

        # Add the new panel to the dictionary of Maya panels that have been created by the engine.
        # The panel entry has a Maya panel name key and an app widget instance value.
        # Note that the panel entry will not be removed from the dictionary when the panel is
        # later deleted since the added complexity of updating the dictionary from our panel
        # close callback is outweighed by the limited length of the dictionary that will never
        # be longer than the number of apps configured to be runnable by the engine.
        self._maya_panel_dict[maya_panel_name] = widget_instance

        return widget_instance

    def close_windows(self):
        """
        Closes the various windows (dialogs, panels, etc.) opened by the engine.
        """

        # Make a copy of the list of Tank dialogs that have been created by the engine and
        # are still opened since the original list will be updated when each dialog is closed.
        opened_dialog_list = self.created_qt_dialogs[:]

        # Loop through the list of opened Tank dialogs.
        for dialog in opened_dialog_list:
            dialog_window_title = dialog.windowTitle()
            try:
                # Close the dialog and let its close callback remove it from the original dialog list.
                self.logger.debug("Closing dialog %s.", dialog_window_title)
                dialog.close()
            except Exception, exception:
                self.logger.error("Cannot close dialog %s: %s", dialog_window_title, exception)

        # Loop through the dictionary of Maya panels that have been created by the engine.
        for (maya_panel_name, widget_instance) in self._maya_panel_dict.iteritems():
            # Make sure the Maya panel is still opened.
            if pm.control(maya_panel_name, query=True, exists=True):
                try:
                    # Reparent the Shotgun app panel widget under Maya main window
                    # to prevent it from being deleted with the existing Maya panel.
                    self.logger.debug("Reparenting widget %s under Maya main window.",
                                   widget_instance.objectName())
                    parent = self._get_dialog_parent()
                    widget_instance.setParent(parent)
                    # The Maya panel can now be deleted safely.
                    self.logger.debug("Deleting Maya panel %s.", maya_panel_name)
                    pm.deleteUI(maya_panel_name)
                except Exception, exception:
                    self.logger.error("Cannot delete Maya panel %s: %s", maya_panel_name, exception)

        # Clear the dictionary of Maya panels now that they were deleted.
        self._maya_panel_dict = {}
