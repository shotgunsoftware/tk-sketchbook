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
import sgtk

import sketchbook_api

HookBaseClass = sgtk.get_hook_baseclass()


class SketchBookSessionCollector(HookBaseClass):
    @property
    def settings(self):
        """
        Dictionary defining the settings that this collector expects to receive
        through the settings parameter in the process_current_session and
        process_file methods.
        A dictionary on the following form::
            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }
        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """

        # grab any base class settings
        collector_settings = super(SketchBookSessionCollector, self).settings or {}

        # settings specific to this collector
        sketchbook_session_settings = {
            "Work Template": {
                "type": "template",
                "default": None,
                "description": "Template path for artist work files. Should "
                "correspond to a template defined in "
                "templates.yml. If configured, is made available"
                "to publish plugins via the collected item's "
                "properties. ",
            },
        }

        # update the base settings with these settings
        collector_settings.update(sketchbook_session_settings)

        return collector_settings

    def process_current_session(self, settings, parent_item):
        """
        Analyzes the open document in SketchBook and creates publish items
        parented under the supplied item.
        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        """

        publisher = self.parent

        path = sketchbook_api.get_current_path()

        if path:
            file_info = publisher.util.get_file_path_components(path)
            display_name = file_info["filename"]
        else:
            display_name = "Current SketchBook Session"

        # create the session item for the publish hierarchy
        session_item = parent_item.create_item(
            "sketchbook.session", "SketchBook Session", display_name
        )

        icon_path = os.path.join(self.disk_location, "icons", "SketchBook.png")

        session_item.set_icon_from_path(icon_path)
        session_item.thumbnail_enabled = False
        session_item.properties["path"] = path

        self.logger.info("Collected current SketchBook session")

        return session_item
