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

import sgtk
from sgtk.platform import SoftwareLauncher, SoftwareVersion, LaunchInformation


class SketchbookLauncher(SoftwareLauncher):
    """
    Handles launching Sketchbook executables.

    Automatically starts up a tk-Sketchbook engine with the current
    context.
    """

    # Named regex strings to insert into the executable template paths when
    # matching against supplied versions and products. Similar to the glob
    # strings, these allow us to alter the regex matching for any of the
    # variable components of the path in one place
    COMPONENT_REGEX_LOOKUP = {
    }

    # This dictionary defines a list of executable template strings for each
    # of the supported operating systems. The templates are used for both
    # globbing and regex matches by replacing the named format placeholders
    # with an appropriate glob or regex string. As Side FX adds modifies the
    # install path on a given OS for a new release, a new template will need
    # to be added here.
    EXECUTABLE_TEMPLATES = {
        "darwin": [
            # Example: C:\Program Files\Autodesk\SketchbookAutoStudio2019\bin\Sketchbook.exe
            # r"C:\Program Files\Autodesk\Sketchbook{code_name}{version}\bin\Sketchbook.exe",
            "/Users/t_granad/Dev/SketchBook.app"
        ],
    }

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

    ##########################################################################################
    # private methods

    def _icon_from_executable(self, code_name):
        """
        Find the application icon based on the code_name.

        :param code_name: Product code_name (AutoStudio, Design, ...).

        :returns: Full path to application icon as a string or None.
        """
        path = os.path.join(self.disk_location, "icon_256.png")
        return path

    def scan_software(self):
        """
        Scan the filesystem for maya executables.

        :return: A list of :class:`SoftwareVersion` objects.
        """
        self.logger.debug("Scanning for Sketchbook executables...")

        supported_sw_versions = self._find_software():
        return supported_sw_versions

    def _find_software(self):
        """
        Find executables in the default install locations.
        """
        # all the discovered executables
        sw_versions = ["/Users/t_granad/Dev/SketchBook.app"]
        return sw_versions

