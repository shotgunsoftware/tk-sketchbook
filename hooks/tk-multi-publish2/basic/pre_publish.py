# Copyright (c) 2020 Autodesk Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Autodesk Software Inc.

import sgtk
from sgtk.platform.qt import QtGui

import sketchbook_api

HookBaseClass = sgtk.get_hook_baseclass()


class SketchBookPrePublishHook(HookBaseClass):
    """
    This hook defines logic to be executed before showing the publish
    dialog. There may be conditions that need to be checked before allowing
    the user to proceed to publishing.
    """

    def validate(self):
        """
        Returns True if the user can proceed to publish.
        """

        engine = self.parent.engine
        result = True

        if engine.get_setting("require_save_before_publish", False):
            try:
                path = sketchbook_api.get_current_path()
                if not path:
                    answer = QtGui.QMessageBox.question(
                        None,
                        "Save Work",
                        "Do you want to save your work to continue to publish?",
                        defaultButton=QtGui.QMessageBox.Yes,
                    )

                    if answer == QtGui.QMessageBox.Yes:
                        engine.show_save_dialog()
                        path = sketchbook_api.get_current_path()

                    result = bool(path)

            except AttributeError as error:
                error_msg = "Error: '%s'" % error
                self.logger.error(error_msg)
                QtGui.QMessageBox.critical(
                    QtGui.QApplication.activeWindow(), "File Save Error", error_msg
                )
                result = False

        return result
