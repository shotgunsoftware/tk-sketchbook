# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk
import sys
import traceback
import re
import time
import os
import logging
import PySide2
from tank.platform import Engine

import SketchBookLogger
import sketchbook_api

# Although the engine has logging already, this logger is needed for callback based logging
# where an engine may not be present.
logger = sgtk.LogManager.get_logger(__name__)

class SketchBookEngine (Engine):
    @property
    def host_info (self):
        self.logger.debug ("%s: Fetching host info...", self)
        return sketchbook_api.host_info ()

    def __init__(self, tk, context, engine_instance_name, env):
        super (SketchBookEngine, self).__init__(tk, context, engine_instance_name, env)

    def destroy_engine (self):
        self.logger.debug ("%s: Destroying...", self)

        # Close all Shotgun app dialogs that are still opened since
        # some apps do threads cleanup in their onClose event handler
        # Note that this function is called when the engine is restarted (through "Reload Engine and Apps")

        # Important: Copy the list of dialogs still opened since the call to close() will modify created_qt_dialogs
        dialogs_still_opened = self.created_qt_dialogs[:]

        for dialog in dialogs_still_opened:
            dialog.close ()

    def pre_app_init (self):
        self.logger.debug ("%s: Pre app init..." % (self,))

        # unicode characters returned by the shotgun api need to be converted
        # to display correctly in all of the app windows
        # tell QT to interpret C strings as utf-8
        from sgtk.platform.qt import QtCore

        utf8 = QtCore.QTextCodec.codecForName ("utf-8")
        QtCore.QTextCodec.setCodecForCStrings (utf8)
        self.logger.debug ("set utf-8 codec for widget text")

    def post_app_init (self):
        self.logger.debug("%s: Post app init...", self)

        self.logger.debug ("%s: Initializing QtApp", self)
        from sgtk.platform.qt import QtGui
        self._qt_app = QtGui.QApplication.instance ()

        # import python/tk_sketchbook module
        self._tk_sketchbook = self.import_module ("tk_sketchbook")

        # init menu
        self.menu = self._tk_sketchbook.SketchBookMenu (engine=self)
        self.refresh_menu()
        self.logger.debug ("Got menu %s", self.menu)

        self.logger.debug ("Installed commands are %s.", self.commands)

        path = os.environ.get ("SGTK_FILE_TO_OPEN", None)
        if path:
            self.operations.open_file (path)

    def refresh_menu(self):
        self.logger.debug("Refreshing with menu object %s.", self.menu)
        sketchbook_api.refresh_menu(self.menu.create())

    # def _get_standard_qt_stylesheet(self):
    #    with open (os.path.join (self.disk_location, "sketchbook_lighter.css")) as f:
    #        return f.read ()

    def run_command (self, commandName):
        self.menu.doCommand (commandName)

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


    def _emit_log_message (self, handler, record):
        if record.levelno < logging.INFO:
            formatter = logging.Formatter ("Debug: Shotgun %(basename)s: %(message)s")
        else:
            formatter = logging.Formatter ("Shotgun %(basename)s: %(message)s")

        msg = formatter.format (record)
        SketchBookLogger.logMessage (msg)

    @property
    def context_change_allowed(self):
        """
        Specifies that context changes are allowed by the engine.
        """
        return True

    def refresh_context():
        logger.debug("Refreshing the context")

        # Get the path of the current open Maya scene file.
        new_path = sketchbook_api.current_file_path()

        if new_path is None:
            # This is a File->New call, so we just leave the engine in the current
            # context and move on.
            logger.debug("New file call, aborting the refresh of the engine.")
            return

        # this file could be in another project altogether, so create a new
        # API instance.
        try:
            tk = sgtk.sgtk_from_path(new_path)
            logger.debug("Extracted sgtk instance: '%r' from path: '%r'", tk, new_path)

        except sgtk.TankError as e:
            logger.exception("Could not execute sgtk_from_path('%s')" % new_path)
            return

        # Construct a new context for this path:
        ctx = tk.context_from_path(new_path, self.context)
        logger.debug("Context for path %s is %r", new_path, ctx)

        if ctx != self.context:
            logger.debug("Changing the context to '%r", ctx)
            self.change_context(ctx)
