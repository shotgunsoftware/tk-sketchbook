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


HookBaseClass = sgtk.get_hook_baseclass()


class SketchBookUnsavedFilePlugin(HookBaseClass):
    """
    Plugin for informing the user to save their file before Publishing
    """

    @property
    def icon(self):
        """
        Path to an png icon on disk
        """

        # ensure icon is there
        return os.path.join(self.disk_location, "icons", "file.png")

    @property
    def name(self):
        """
        One line display name describing the plugin
        """
        return "Unsaved file, Please save your file and re-launch Shotgun Publish"

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """
        embed_image = os.path.join(
            self.disk_location, "docs", "sketchbook-publisher-screenshot.png"
        )

        help_url = "https://github.com/shotgunsoftware/tk-sketchbook/wiki/Publishing"

        return """
        Your file has not been saved.<br>
        Please save your file and re-launch the Shotgun Publisher.

        <h3>Publishing</h3>

        Once your file is saved you should see Publish Plugins for your file like this image shows:<br>

        <a href=%s>
        <img width="270" height="240" src=%s ismap>
        </a>

        <br>Selecting a Publish Plugin allows you to read its' description.
        """ % (
            help_url,
            embed_image,
        )

    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to recieve
        through the settings parameter in the accept, validate, publish and
        finalize methods.

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
        return {}

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.

        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for example
        ["maya.*", "file.maya"]
        """

        # we use our value here
        return ["sketchbook.session"]

    def accept(self, settings, item):
        """
        Method called by the publisher to determine if an item is of any
        interest to this plugin. Only items matching the filters defined via the
        item_filters property will be presented to this method.

        A publish task will be generated for each item accepted here. Returns a
        dictionary with the following booleans:

            - accepted: Indicates if the plugin is interested in this value at
                all. Required.
            - enabled: If True, the plugin will be enabled in the UI, otherwise
                it will be disabled. Optional, True by default.
            - visible: If True, the plugin will be visible in the UI, otherwise
                it will be hidden. Optional, True by default.
            - checked: If True, the plugin will be checked in the UI, otherwise
                it will be unchecked. Optional, True by default.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: dictionary with boolean keys accepted, required and enabled
        """
        file_path = item.properties["path"]

        # Let's declare this here to have a more logical UX for when a file is
        # not saved before the Publish is called
        acceptance = {"accepted": True, "checked": False, "disabled": True}

        if not file_path:
            return acceptance
        else:
            acceptance = {"accepted": False, "visible": False}
            return acceptance

    def validate(self, settings, item):
        return True

    def publish(self, settings, item):
        return True

    def finalize(self, settings, item):
        return True
