# Copyright (c) 2020 Autodesk, Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Autodesk, Inc.
#

import sketchbook_api

import sgtk
from sgtk.platform.qt import QtGui

HookClass = sgtk.get_hook_baseclass()


class SceneOperation(HookClass):
    """
    Hook called to perform an operation with the
    current scene
    """

    def execute(
        self,
        operation,
        file_path,
        context,
        parent_action,
        file_version,
        read_only,
        **kwargs
    ):
        """
        Main hook entry point

        :param operation:       String
                                Scene operation to perform

        :param file_path:       String
                                File path to use if the operation
                                requires it (e.g. open)

        :param context:         Context
                                The context the file operation is being
                                performed in.

        :param parent_action:   This is the action that this scene operation is
                                being executed for.  This can be one of:
                                - open_file
                                - new_file
                                - save_file_as
                                - version_up

        :param file_version:    The version/revision of the file to be opened.  If this is 'None'
                                then the latest version should be opened.

        :param read_only:       Specifies if the file should be opened read-only or not

        :returns:               Depends on operation:
                                'current_path' - Return the current scene
                                                 file path as a String
                                'reset'        - True if scene was reset to an empty
                                                 state, otherwise False
                                all others     - None
        """

        if operation == "current_path":
            # return the current scene path
            return sketchbook_api(get_current_path)
        elif operation == "open":
            # do new scene as Maya doesn't like opening
            pass
        elif operation == "save":
            # save the current scene:
            #
            pass
        elif operation == "save_as":
            # first rename the scene as file_path:
            #
            # Maya example preserved as reference below
            # # Maya can choose the wrong file type so
            # # we should set it here explicitely based
            # # on the extension
            # maya_file_type = None
            # if file_path.lower().endswith(".ma"):
            #     maya_file_type = "mayaAscii"
            # elif file_path.lower().endswith(".mb"):
            #     maya_file_type = "mayaBinary"

            # # save the scene:
            # if maya_file_type:
            #     cmds.file(save=True, force=True, type=maya_file_type)
            # else:
            #     cmds.file(save=True, force=True)
            pass
        elif operation == "reset":
            """
            Reset the scene to an empty state
            """
            #
            # Maya example preserved as reference below
            # while cmds.file(query=True, modified=True):
            #     # changes have been made to the scene
            #     res = QtGui.QMessageBox.question(
            #         None,
            #         "Save your scene?",
            #         "Your scene has unsaved changes. Save before proceeding?",
            #         QtGui.QMessageBox.Yes
            #         | QtGui.QMessageBox.No
            #         | QtGui.QMessageBox.Cancel,
            #     )

            #     if res == QtGui.QMessageBox.Cancel:
            #         return False
            #     elif res == QtGui.QMessageBox.No:
            #         break
            #     else:
            #         scene_name = cmds.file(query=True, sn=True)
            #         if not scene_name:
            #             cmds.SaveSceneAs()
            #         else:
            #             cmds.file(save=True)

            # # do new file:
            # cmds.file(newFile=True, force=True)
            # return True
            pass
