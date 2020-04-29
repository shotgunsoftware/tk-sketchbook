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
import datetime
from os.path import expanduser

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
        self.startLog ("Here!  Launching Sketchbook at %s" % exec_path)
        
        required_env = {}

        # Append executable folder to PATH environment variable
        sgtk.util.append_path_to_env_var ("PATH", os.path.dirname(sys.executable))
        
        # We're going to append all of this Python process's sys.path to the
        # PYTHONPATH environment variable. This will ensure that we have access
        # to all libraries available in this process. We're appending instead of
        # setting because we don't want to stomp on any PYTHONPATH that might already
        # exist that we want to persist
        sgtk.util.append_path_to_env_var ("PYTHONPATH", os.pathsep.join (sys.path))
        
        if sys.platform == "darwin":
            sitePackagesPath = os.path.join (self.macAppPath (), '/Contents/Frameworks/python2.7/site-packages')
            sgtk.util.append_path_to_env_var ("PYTHONPATH", sitePackagesPath)
        
        sgtk.util.append_path_to_env_var ("PYTHONPATH", os.path.join (self.disk_location, "startup"))

        # Prepare the launch environment with variables required by the
        # classic bootstrap approach.
        self.startLog ("Preparing Sketchbook Launch...")
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
        sbpPath = self.sketchBookPath ()
        icon_path = os.path.join (self.disk_location, "SketchBook.png")
        return [ SoftwareVersion ('2020', 'SketchBook', sbpPath, icon_path) ]

    def sketchBookPath(self):
        if sys.platform == "darwin":
            sbpPath = self.macAppPath () + '/Contents/MacOS/SketchBook'
        elif sys.platform == "win32":
            paths = self.windowsExePath (expanduser("~/Desktop"))

            if len (paths) == 0:
                paths = self.windowsExePath (expanduser("~/SketchBook"))

            if len (paths) == 0:
                paths = self.windowsExePath ('C:\\Program Files')

            sbpPath = paths [0] if len (paths) > 0 else ''
        
        self.startLog ('2Found SketchBook at ' + sbpPath)
        return sbpPath

    def macAppPath(self):
        found = subprocess.check_output (['mdfind', 'kMDItemCFBundleIdentifier = "com.autodesk.SketchBook"'])
        paths = found.strip ().split ()
        return paths [0] if len (paths) else ''

    def windowsExePath(self, directory):
        paths = ''
        exePatterns = [directory + '\\' + name + '.exe' for name in ['SketchBook', 'SketchBookPro']]
        
        for pattern in exePatterns:
            command = 'dir "' + pattern + '" /s /B'
            try:
                paths += subprocess.check_output (command, shell=True, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                pass

        return paths.splitlines ()


    def startLog(self, message):
        with open (expanduser ("~") + "/Desktop/start_log.txt", "a") as logfile:
            logfile.write (datetime.datetime.now ().strftime ("%a %d %b %H:%M") + '  ' + message + "\n")




