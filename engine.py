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
from tank.platform import Engine

import SketchBookLogger 
import sketchbook_api

# Although the engine has logging already, this logger is needed for callback based logging
# where an engine may not be present.
logger = sgtk.LogManager.get_logger(__name__)

class SketchBookEngine (Engine):
    @property
    def host_info (self):
        return { "name": "SketchBook", "version": "2020" }

    def __init__(self, tk, context, engine_instance_name, env):
        super (SketchBookEngine, self).__init__(tk, context, engine_instance_name, env)
        self.logger.debug ("%s: Initializing...", self)
        self._menu_name = "Shotgun"
        self._tk_sketchbook = None
        self._qt_app = None
        self._dialog_parent = None
        self.menu = None
        self.operations = None

    def destroy_engine (self):
        self.logger.debug ("%s: Destroying...", self)

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

        # import python/tk_alias module
        self._tk_sketchbook = self.import_module ("tk_sketchbook")

        # init menu
        self.menu = self._tk_sketchbook.SketchBookMenu (engine=self)

        # init operations
        self.operations = self._tk_sketchbook
        
        self.logger.debug ("Installed commands are %s.", self.commands)

        QtGui.QApplication.setStyle ("cleanlooks")
        qt_application = QtGui.QApplication ([])
        qt_application.setStyleSheet (self._get_standard_qt_stylesheet ())
    
    def fetch_command_names (self):
        self.logger.debug ("Returning command list %s.", self.commands.keys ())
        sketchbook_api.set_commands (self.commands.keys ())

    def _get_standard_qt_stylesheet(self):
        with open (os.path.join (self.disk_location, "sketchbook_lighter.css")) as f:
            return f.read ()

    def run_command (self, commandName):
        self.logger.debug ("Running command %s.", commandName)

        if self.commands [commandName]:
            if self.commands [commandName] ['callback']:
                self.commands [commandName] ['callback'] ();
        
    def on_plugin_init (self):
        self.logger.debug("Plugin initialized signal received")

        # Create menu
        self._create_menu()

        path = os.environ.get ("SGTK_FILE_TO_OPEN", None)
        if path:
            self.operations.open_file (path)

    def on_plugin_exit (self):
        self.operations.current_file_closed ()


    def post_context_change (self, old_context, new_context):
        self.logger.debug ("%s: Post context change...", self)
        if self.context_change_allowed:
            self._create_menu ()

    def _create_menu (self):
        # self.logger.debug ("Creating menu")
        # self.menu.create ()
        
        # self.logger.debug ("Raw menu options: {}".format (self.menu.raw_options))
        # self.logger.debug ("Menu options: {}".format (self.menu.options))
        # sketchbook_api.create_menu (self.menu.options)
        pass


    def _emit_log_message (self, handler, record):
        if record.levelno < logging.INFO:
            formatter = logging.Formatter ("Debug: Shotgun %(basename)s: %(message)s")
        else:
            formatter = logging.Formatter ("Shotgun %(basename)s: %(message)s")

        msg = formatter.format (record)
        SketchBookLogger.logMessage (msg)



