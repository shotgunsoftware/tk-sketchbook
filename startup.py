# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys
import subprocess

import sgtk
from sgtk.platform import SoftwareLauncher, SoftwareVersion, LaunchInformation


class SketchbookLauncher(SoftwareLauncher):
    """
    Handles launching Sketchbook executables.

    Automatically starts up a tk-Sketchbook engine with the current
    context.
    """


    def prepare_launch(self, exec_path, args, file_to_open=None):
        """
        Prepares an environment to launch Sketchbook.

        This environment will automatically load Toolkit and the tk-Sketchbook engine when
        the program starts.

        :param str exec_path: Path to Sketchbook executable.
        :param str args: Command line arguments as strings.
        :param str file_to_open: (optional) Full path name of a file to open on launch.
        :returns: :class:`LaunchInformation` instance
        """
        self.logger.debug("Here!  Launching Sketchbook at %s" % exec_path)

        required_env = {}

        # Append executable folder to PATH environment variable
        sgtk.util.append_path_to_env_var("PATH", os.path.dirname(sys.executable))
        # We're going to append all of this Python process's sys.path to the
        # PYTHONPATH environment variable. This will ensure that we have access
        # to all libraries available in this process. We're appending instead of
        # setting because we don't want to stomp on any PYTHONPATH that might already
        # exist that we want to persist
        sgtk.util.append_path_to_env_var("PYTHONPATH", os.pathsep.join(sys.path))
        required_env["PYTHONPATH"] = os.environ["PYTHONPATH"]

        # Prepare the launch environment with variables required by the
        # classic bootstrap approach.
        self.logger.debug("Preparing Sketchbook Launch...")
        required_env["SGTK_ENGINE"] = self.engine_name
        required_env["SGTK_CONTEXT"] = sgtk.context.serialize(self.context)

        if file_to_open:
            # Add the file name to open to the launch environment
            required_env["SGTK_FILE_TO_OPEN"] = file_to_open

        return LaunchInformation(exec_path, args, required_env)


    def scan_software(self):
        """
        Scan the filesystem for SketchBook executables.

        :return: A list of :class:`SoftwareVersion` objects.
        """
        self.logger.debug ("Here!  Scanning for Sketchbook executables...")

        if sys.platform == "darwin":
            sbpPath = subprocess.check_output (['mdfind', 'kMDItemCFBundleIdentifier = "com.autodesk.SketchBook"']).strip ()
        elif sys.platform == "win32":
            sbpPath = ''
        
        self.logger.debug ('Found SketchBook at ' + sbpPath)
        icon_path = os.path.join (self.disk_location, "SketchBook.png")

        return [ SoftwareVersion ('2020', 'SketchBook', sbpPath, icon_path) ]





