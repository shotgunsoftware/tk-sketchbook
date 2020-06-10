# Copyright (c) 2020 Autodesk
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Menu handling for SketchBook
"""

from collections import OrderedDict
import os
import sys

from sgtk.platform.qt import QtGui
from sgtk.platform.qt import QtCore


class SketchBookMenu(object):
    ABOUT_MENU_TEXT = "About Shotgun Pipeline Toolkit"
    JUMP_TO_SG_TEXT = "Jump to Shotgun"
    JUMP_TO_FS_TEXT = "Jump to File System"
    SEPARATOR_ITEM = "_SEPARATOR_"

    def __init__(self, engine):
        self._engine = engine
        self.logger = self._engine.logger

    def create(self):
        self.logger.info("Creating Shotgun Menu")
        menuItems = [self.createContextSubmenu(), [self.SEPARATOR_ITEM, []]]
        menuItems.extend(self.createAppsEntries())
        self.logger.debug("Setting menu items to %s.", menuItems)
        return menuItems
        # sketchbook_api.refresh_menu ([["ItemOne", ["Sub1", "Sub2"]], ["ItemTwo", []], ["ItemThree", []]])

    def createContextSubmenu(self):
        names = [self.JUMP_TO_SG_TEXT, self.JUMP_TO_FS_TEXT, self.SEPARATOR_ITEM]
        names.extend ([name for name, data in self._engine.commands.items()
                if data.get("properties").get("type") == "context_menu"])
        return [self.context_name, names]

    def createAppsEntries(self):
        return [[name, []] for name, data in self._engine.commands.items()
                if data.get("properties").get("type") != "context_menu"]

    def doCommand(self, commandName):
        self.logger.debug("Running command %s.", commandName)

        if commandName == self.JUMP_TO_SG_TEXT:
            self.jump_to_sg()
        elif commandName == self.JUMP_TO_FS_TEXT:
            self.jump_to_fs()
        elif self._engine.commands[commandName]:
            if self._engine.commands[commandName]['callback']:
                self._engine.commands[commandName]['callback']();

    @property
    def context_name(self):
        self.logger.info("Considering project %s", self._engine.context.project)

        return self._engine.context.project['name']

    def jump_to_sg(self):
        """
        Jump to shotgun, launch web browser
        """
        url = self._engine.context.shotgun_url
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def jump_to_fs(self):
        """
        Jump from context to File System
        """
        # launch one window for each location on disk
        paths = self._engine.context.filesystem_locations

        for disk_location in paths:
            # get the setting
            system = sys.platform

            # run the app
            if system == "linux2":
                cmd = 'xdg-open "%s"' % disk_location
            elif system == "darwin":
                cmd = 'open "%s"' % disk_location
            elif system == "win32":
                cmd = 'cmd.exe /C start "Folder" "%s"' % disk_location
            else:
                raise Exception("Platform '%s' is not supported." % system)

            self._engine.logger.debug("Jump to filesystem command: {}".format(cmd))

            exit_code = os.system(cmd)

            if exit_code != 0:
                self.logger.error("Failed to launch '%s'!", cmd)
