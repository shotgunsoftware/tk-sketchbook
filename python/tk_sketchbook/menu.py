# Copyright (c) 2020 Autodesk, Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Autodesk, Inc.

import os

from sgtk.platform.qt import QtGui
from sgtk.platform.qt import QtCore
from sgtk.util import is_windows, is_macos, is_linux


class SketchBookMenu(object):
    """
    Menu handling for SketchBook
    """

    ABOUT_MENU_TEXT = "About Shotgun Pipeline Toolkit"
    JUMP_TO_SG_TEXT = "Jump to Shotgun"
    JUMP_TO_FS_TEXT = "Jump to File System"
    SEPARATOR_ITEM = "_SEPARATOR_"

    def __init__(self, engine):
        """
        Initializes a new menu generator.

        :param engine: The currently-running engine.
        :type engine: :class:`tank.platform.Engine`
        """
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

        menu_items = [self.create_context_submenu(), [self.SEPARATOR_ITEM, []]]
        # TODO: have PR #792 in SKB repo merged before uncommenting below
        # menu_items.extend(self.create_favourites_entries())
        menu_items.extend([[self.SEPARATOR_ITEM, []]])
        menu_items.extend(self.create_apps_entries())
        self.logger.debug("Setting menu items to %s.", menu_items)
        return menu_items
        # sketchbook_api.refresh_menu ([["ItemOne", ["Sub1", "Sub2"]], ["ItemTwo", []], ["ItemThree", []]])

    def create_context_submenu(self):
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

    def create_apps_entries(self):
        return [
            [name, []]
            for name, data in self._engine.commands.items()
            if data.get("properties").get("type") != "context_menu"
        ]

    def create_favourites_entries(self):
        # Add favourites
        favourites = []
        for fav in self._engine.get_setting("menu_favourites"):
            menu_name = fav["name"]
            favourites.append([menu_name, []])
        self.logger.debug("favourites is: %s" % favourites)
        return favourites

    def do_command(self, command_name):
        if not self.already_running(command_name):
            self.logger.debug("Running command %s.", command_name)

            if command_name == self.JUMP_TO_SG_TEXT:
                self.jump_to_sg()
            elif command_name == self.JUMP_TO_FS_TEXT:
                self.jump_to_fs()
            elif self._engine.commands[command_name]:
                if self._engine.commands[command_name]["callback"]:
                    self._engine.commands[command_name]["callback"]()

            self.logger.debug("Ran command %s.", command_name)
        else:
            self.bring_to_front(command_name)

    def already_running(self, command_name):
        return self.dialog_for_command(command_name) is not None

    def bring_to_front(self, command_name):
        dialog = self.dialog_for_command(command_name)
        if dialog:
            dialog.show()
            dialog.activateWindow()
            dialog.raise_()

    def dialog_for_command(self, command_name):
        for dialog in self._engine.created_qt_dialogs:
            if {
                "Shotgun Panel...": "Shotgun: Shotgun",
                "Publish...": "Shotgun: Publish",
                "Load...": "Shotgun: Loader",
                "Work Area Info...": "Shotgun: Your Current Work Area",
                "Shotgun Python Console": "Shotgun: Shotgun Python Console",
                "File Open...": "Shotgun: File Open",
                "File Save...": "Shotgun: File Save",
            }.get(command_name) == dialog.windowTitle():
                return dialog

        self.logger.debug("Don't have a dialog for command %s", command_name)
        return None

    def jump_to_sg(self):
        """
        Jump to Shotgun, launch web browser
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
