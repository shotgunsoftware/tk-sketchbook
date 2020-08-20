# Copyright (c) 2020 Autodesk
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Autodesk, Inc.

"""
Menu handling for SketchBook
"""

import os

from sgtk.platform.qt import QtGui
from sgtk.platform.qt import QtCore
from sgtk.util import is_windows, is_macos, is_linux


class SketchBookMenu(object):
    ABOUT_MENU_TEXT = "About Shotgun Pipeline Toolkit"
    JUMP_TO_SG_TEXT = "Jump to Shotgun"
    JUMP_TO_FS_TEXT = "Jump to File System"
    SEPARATOR_ITEM = "_SEPARATOR_"

    def __init__(self, engine):
        self._engine = engine
        self.logger = self._engine.logger

    @property
    def context_name(self):
        return str(self._engine.context)

    def create(self):
        """
        Render the entire Shotgun menu.
        """

        self.logger.debug("Creating Shotgun Menu")

        menuItems = [self.createContextSubmenu(), [self.SEPARATOR_ITEM, []]]
        menuItems.extend(self.createAppsEntries())
        self.logger.debug("Setting menu items to %s.", menuItems)
        return menuItems
        # sketchbook_api.refresh_menu ([["ItemOne", ["Sub1", "Sub2"]], ["ItemTwo", []], ["ItemThree", []]])

    def createContextSubmenu(self):
        if self._engine.context.filesystem_locations:
            names = [self.JUMP_TO_SG_TEXT, self.JUMP_TO_FS_TEXT, self.SEPARATOR_ITEM]
        else:
            names = [self.JUMP_TO_SG_TEXT, self.SEPARATOR_ITEM]

        names.extend(
            [
                name
                for name, data in self._engine.commands.items()
                if data.get("properties").get("type") == "context_menu"
            ]
        )
        return [self.context_name, names]

    def createAppsEntries(self):
        return [
            [name, []]
            for name, data in self._engine.commands.items()
            if data.get("properties").get("type") != "context_menu"
        ]

    def doCommand(self, commandName):
        if not self.alreadyRunning(commandName):
            self.logger.debug("Running command %s.", commandName)

            if commandName == self.JUMP_TO_SG_TEXT:
                self.jump_to_sg()
            elif commandName == self.JUMP_TO_FS_TEXT:
                self.jump_to_fs()
            elif self._engine.commands[commandName]:
                if self._engine.commands[commandName]["callback"]:
                    self._engine.commands[commandName]["callback"]()

            self.logger.debug("Ran command %s.", commandName)
        else:
            self.bringToFront(commandName)

    def alreadyRunning(self, commandName):
        return self.dialogForCommand(commandName) is not None

    def bringToFront(self, commandName):
        dialog = self.dialogForCommand(commandName)
        if dialog:
            dialog.show()
            dialog.activateWindow()
            dialog.raise_()

    def dialogForCommand(self, commandName):
        for dialog in self._engine.created_qt_dialogs:
            if {
                "Shotgun Panel...": "Shotgun: Shotgun",
                "Publish...": "Shotgun: Publish",
                "Load...": "Shotgun: Loader",
                "Work Area Info...": "Shotgun: Your Current Work Area",
                "Shotgun Python Console": "Shotgun: Shotgun Python Console",
                "File Open...": "Shotgun: File Open",
                "File Save...": "Shotgun: File Save",
            }.get(commandName) == dialog.windowTitle():
                return dialog

        self.logger.debug("Don't have a dialog for command %s", commandName)
        return None

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
            # run the app
            if is_linux():
                cmd = 'xdg-open "%s"' % disk_location
            elif is_macos():
                cmd = 'open "%s"' % disk_location
            elif is_windows():
                cmd = 'cmd.exe /C start "Folder" "%s"' % disk_location
            else:
                raise Exception("Platform is not supported.")

            self._engine.logger.debug("Jump to filesystem command: {}".format(cmd))

            exit_code = os.system(cmd)

            if exit_code != 0:
                self.logger.error("Failed to launch '%s'!", cmd)
