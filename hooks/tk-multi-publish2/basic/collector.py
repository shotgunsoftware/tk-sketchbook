# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sgtk
import sketchbook_api

HookBaseClass = sgtk.get_hook_baseclass()

class SketchBookSessionCollector(HookBaseClass):
    @property
    def settings(self):
        collector_settings = super(SketchBookSessionCollector, self).settings or {}
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

        collector_settings.update(sketchbook_session_settings)

        return collector_settings


    def process_current_session (self, settings, parent_item):
        publisher = self.parent

        path = sketchbook_api.get_current_path ()

        if path:
            file_info = publisher.util.get_file_path_components (path)
            display_name = file_info ["filename"]
        else:
            display_name = "Current SketchBook Document"

        # create the session item for the publish hierarchy
        session_item = parent_item.create_item (
            "sketchbook.session",
            "SketchBook Session",
            display_name
        )

        icon_path = os.path.join (self.disk_location, os.pardir, os.pardir, os.pardir, "SketchBook.png")
        session_item.set_icon_from_path (icon_path)

        session_item.set_thumbnail_from_path (path)

        self.logger.debug ("About to try path " + path)

        item = super (SketchBookSessionCollector, self)._collect_file (
            session_item,
            path,
            frame_sequence=True
        )

        self.logger.info ("Collected current SketchBook session")
        return session_item
