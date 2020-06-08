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
        menuItems = []
        
        names = list (self._engine.commands.keys ())
        menuItems.append (self.createContextSubmenu (names))
        menuItems.append ([self.SEPARATOR_ITEM, []])
        menuItems.extend ([[name, []] for name in names])
        self.logger.debug ("Setting menu data to %s.", menuItems)
        return menuItems
        # sketchbook_api.refresh_menu ([["ItemOne", ["Sub1", "Sub2"]], ["ItemTwo", []], ["ItemThree", []]])
    
    def createContextSubmenu (self, names):
    	return [self.context_name, [self.JUMP_TO_SG_TEXT, self.SEPARATOR_ITEM, self.JUMP_TO_FS_TEXT]]
    
    
    
    
    def other(self):
        # Get all options and sort them
        options = [(caption, data) for caption, data in self._engine.commands.items()]
        if options:
            options.sort(key=lambda option: option[0])

        # Context submenu
        root_menu.addMenu(self._create_context_submenu(options))
        root_menu.addSeparator()

        # Favourites
        favourites = self._create_favourites(options)
        [root_menu.addAction(caption, callback) for caption, callback in favourites]
        if favourites:
            root_menu.addSeparator()

        # Apps
        apps = self._create_apps(options)
        for label, is_submenu, data in apps:
            if is_submenu:
                root_menu.addMenu(data)
            else:
                caption, callback = data
                root_menu.addAction(caption, callback)

        actions = menubar.actions()
        menubar.insertMenu(actions[-1], root_menu)

    def _create_context_submenu(self, options):
        submenu = QtGui.QMenu()
        submenu.setTitle(self.context_name)

        submenu.addAction(self.JUMP_TO_SG_TEXT, self.jump_to_sg)
        submenu.addAction(self.JUMP_TO_FS_TEXT, self.jump_to_fs)
        submenu.addSeparator()

        filtered_options = [(caption, data) for caption, data in options
                            if data.get("properties").get("type") == "context_menu"]

        for caption, data in filtered_options:
            callback = data.get("callback")
            submenu.addAction(caption, callback)

        return submenu

    def _create_favourites(self, options):
        favourites = []

        for favourite in self._engine.get_setting("menu_favourites"):
            app_instance = favourite["app_instance"]
            name = favourite["name"]

            for caption, data in options:
                if data.get("properties").get("type") == "context_menu":
                    continue

                if 'app' in data.get("properties"):
                    app_name = data.get("properties").get("app").name

                    if caption == name and app_name == app_instance:
                        callback = data.get("callback")
                        favourites.append((caption, callback))

        return favourites

    def _create_apps(self, options):
        # Apps to display in the bottom of the menu
        # i.e.: bottom_apps[('tk-multi-autoabout', self.ABOUT_MENU_TEXT)] = []
        bottom_apps = OrderedDict()

        favourites = [(favourite["app_instance"], favourite["name"])
                      for favourite in self._engine.get_setting("menu_favourites")]

        filtered_options = [(caption, data) for caption, data in options
                            if data.get("properties").get("type") != "context_menu"]

        # group filtered options per app
        options_x_app = {}
        for caption, data in filtered_options:
            callback = data.get("callback")
            app_name = None
            app_display_name = None
            if 'app' in data.get("properties"):
                app_name = data.get("properties").get("app").name
                app_display_name = data.get("properties").get("app").display_name

            key = (app_name, app_display_name)

            if key in bottom_apps:
                bottom_apps[key].append((caption, callback))
                continue

            if key not in options_x_app:
                options_x_app[key] = []

            options_x_app[key].append((caption, callback))

        apps = []

        if options_x_app:
            apps += self._parse_options_x_app(options_x_app, favourites)

        if bottom_apps:
            apps += self._parse_options_x_app(bottom_apps, favourites, sort_options=False)

        return apps

    def _parse_options_x_app(self, groups, favourites, sort_options=True):
        parsed_options = []

        for (app_name, app_display_name), options in groups.items():
            first_option = options[0]
            caption = first_option[0]
            callback = first_option[1]
            options_number = len(options)

            if options_number <= 0:
                continue

            if options_number == 1 and (app_name, caption) not in favourites:
                is_submenu = False
                data = caption, callback
                label = caption
            else:
                is_submenu = True
                label = app_display_name

                data = QtGui.QMenu()
                data.setTitle(app_display_name)
                for caption, callback in options:
                    data.addAction(caption, callback)

            parsed_options.append((label, is_submenu, data))

        if sort_options:
            parsed_options.sort(key=lambda option: option[0])

        return parsed_options

    @property
    def context_name(self):
        self.logger.info("Considering project %s", self._engine.context.project)

        return self._engine.context.project ['name']

    def jump_to_sg(self):
        """
        Jump to shotgun, launch web browser
        """
        url = self._engine.context.shotgun_url
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def jump_to_fs(self):
        """
        Jump from context to FS
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

