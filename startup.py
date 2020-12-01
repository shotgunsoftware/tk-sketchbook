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
import sys
import subprocess
import re

import sgtk
from sgtk.platform import SoftwareLauncher, SoftwareVersion, LaunchInformation
from sgtk.util import is_windows, is_macos, is_linux


class SketchBookLauncher(SoftwareLauncher):
    """
    Handles launching SketchBook executables.

    Automatically starts up a tk-sketchbook engine with the current
    context.
    """

    @property
    def minimum_supported_version(self):
        """
        The minimum software version that is supported by the launcher.
        """
        return "9.0"

    def scan_software(self):
        """
        Scan the Windows Registry for SketchBook executables on Windows
        Use software_profiler technique on MacOS

        :return: A list of :class:`SoftwareVersion` objects.
        """
        self.logger.debug("Scanning for SketchBook executables.")

        if is_linux():
            # No linux version
            return []

        supported_sw_versions = []

        if is_windows() or is_macos():
            for sw_version in self._find_software():
                (supported, reason) = self._is_supported(sw_version)
                if supported:
                    supported_sw_versions.append(sw_version)
                else:
                    self.logger.debug(
                        "SoftwareVersion %s is not supported: %s" % (sw_version, reason)
                    )

        return supported_sw_versions

    def prepare_launch(self, exec_path, args, file_to_open=None):
        """
        Prepares an environment to launch SketchBook.

        This environment will automatically load Toolkit and the tk-sketchbook engine when
        the program starts.

        :param str exec_path: Path to SketchBook executable.
        :param str args: Command line arguments as strings.
        :param str file_to_open: (optional) Full path name of a file to open on launch.
        :returns: :class:`LaunchInformation` instance
        """
        # Declare the base required_env here
        required_env = {}

        # Append executable folder to PATH environment variable
        sgtk.util.append_path_to_env_var("PATH", os.path.dirname(sys.executable))

        # We're going to append all of this Python process's sys.path to the
        # PYTHONPATH environment variable. This will ensure that we have access
        # to all libraries available in this process. We're appending instead of
        # setting because we don't want to stomp on any PYTHONPATH that might already
        # exist that we want to persist
        sgtk.util.append_path_to_env_var("PYTHONPATH", os.pathsep.join(sys.path))

        sgtk.util.append_path_to_env_var(
            "PYTHONPATH", os.path.join(self.disk_location, "startup")
        )

        # Prepare the launch environment with variables required by the
        # classic bootstrap approach.
        self.logger.debug("Preparing SketchBook Launch...")
        required_env["SGTK_ENGINE"] = self.engine_name
        required_env["SGTK_CONTEXT"] = sgtk.context.serialize(self.context)

        if file_to_open:
            # Add the file name to open to the launch environment
            required_env["SGTK_FILE_TO_OPEN"] = file_to_open

        return LaunchInformation(exec_path, args, required_env)

    def _find_software(self):
        """
        Find executables in the Registry for Windows
        Find executables using mdfind for MacOS

        :returns: List of :class:`SoftwareVersion` instances
        """
        sw_versions = []
        if is_windows():
            # Determine a list of paths to search for SketchBook executables based
            # on the windows registry
            install_paths_dicts = _get_installation_paths_from_windows_registry(
                self.logger
            )

        # MacOS
        if is_macos():
            # Determine a list of paths to search for SketchBook executables based
            # on the system_profiler return values
            install_paths_dicts = _get_installation_paths_from_mac(self.logger)

        for install_paths in install_paths_dicts:
            executable_version = install_paths["version"]
            executable_path = install_paths["path"]
            launcher_name = install_paths["_name"]
            # Create The actual SoftwareVersions
            sw_versions.append(
                SoftwareVersion(
                    executable_version,
                    launcher_name,
                    executable_path,
                    os.path.join(self.disk_location, "icon_256.png"),
                )
            )

        return sw_versions

    def _is_supported(self, sw_version):
        """
        Determine if a software version is supported or not
        :param sw_version:
        :return: boolean, message
        """
        try:
            if int(sw_version.version.replace(".", "")[0:3]) >= int(
                str(self.minimum_supported_version).replace(".", "")
            ):
                return True, ""
            else:
                return False, "Unsupported version of SketchBook"
        except Exception:
            return False, "Error determining SketchBook version"


def _get_installation_paths_from_windows_registry(logger):
    """
    Query Windows registry for SketchBook installations.

    :returns: List of dictionaries of paths and versions
    where SketchBook is installed.
    """
    # Local scope here
    from tank_vendor.shotgun_api3.lib import six

    winreg = six.moves.winreg

    logger.debug(
        "Querying Windows registry for keys "
        "HKEY_LOCAL_MACHINE\\SOFTWARE\\Autodesk\\SketchBook Pro\\9.0"
    )

    install_paths = []

    # SketchBook install key
    base_key_name = [
        "SOFTWARE\\Autodesk\\SketchBook Pro\\9.0",
        "",
        "SketchBookPro.exe",
        "SketchBook Pro",
    ]

    sub_key_names = []
    # find all subkeys in keys
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_key_name[0])
        sub_key_count = winreg.QueryInfoKey(key)[0]
        i = 0
        while i < sub_key_count:
            sub_key_names.append(winreg.EnumKey(key, i))
            i += 1
        winreg.CloseKey(key)
    except WindowsError:
        logger.error("error opening key %s" % base_key_name[0])

    # Query the value InstallLocation on all subkeys.
    try:
        for name in sub_key_names:
            key_name = base_key_name[0] + "\\" + name
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_name)
            try:
                base_path = winreg.QueryValueEx(key, base_key_name[1])
                full_path = base_path[0] + base_key_name[2]
                version = _get_windows_version(full_path, logger)
                name = base_key_name[3]
                install_paths.append(
                    {"path": full_path, "version": version, "_name": name}
                )
                logger.debug("Found InstallLocation value for key %s" % key_name)
            except WindowsError:
                logger.debug(
                    "Value InstallLocation not found for key %s, skipping key"
                    % key_name
                )
            winreg.CloseKey(key)
    except WindowsError:
        logger.error("Error opening key %s" % key_name)

    return install_paths


def _get_windows_version(full_path, logger):
    """
    Use `wmic` to determine the installed version of SketchBook
    """
    try:
        version_command = subprocess.check_output(
            [
                "wmic",
                "datafile",
                "where",
                "name=" + '"' + str(full_path).replace("\\", "\\\\") + '"',
                "get",
                "Version",
                "/value",
            ]
        )
        version_list = re.findall(r"[\d.]", str(version_command))
        version = "".join(map(str, version_list[0:3]))
    except Exception:
        logger.debug("wmic command unable to determine SketchBook Version.")
        version = "0.0"

    return version


def _get_installation_paths_from_mac(logger):
    """
    Use mdfind command for SketchBook installations.

    :returns: List of dictionaries including paths where SketchBook is installed.
    """
    # Local scoping import for Mac only with Py 2 / 3 check
    import plistlib
    from tank_vendor import six

    install_paths = []
    try:
        if six.PY3:
            installed_path_list = (
                subprocess.check_output(
                    [
                        "/usr/bin/mdfind",
                        "kMDItemCFBundleIdentifier = com.autodesk.SketchBookPro",
                    ]
                )
                .decode("utf-8")
                .split("\n")
            )
        else:
            installed_path_list = subprocess.check_output(
                ["mdfind", "kMDItemCFBundleIdentifier = com.autodesk.SketchBookPro"]
            ).split("\n")
        filtered_path_list = list(filter(None, installed_path_list))
    except Exception:
        logger.debug("Python subprocess of mdfind command failed")

    if filtered_path_list:
        for installed_path in filtered_path_list:
            try:
                installed_path_plist = subprocess.check_output(
                    [
                        "/usr/libexec/PlistBuddy",
                        "-x",
                        "-c",
                        "Print",
                        installed_path + "/Contents/Info.plist",
                    ]
                )
            except Exception:
                logger.debug("Python subprocess of PlistBuddy failed")

            if installed_path_plist:
                try:
                    if six.PY3:
                        installed_app_dict = plistlib.loads(
                            installed_path_plist, fmt=plistlib.FMT_XML
                        )
                    else:
                        installed_app_dict = plistlib.readPlistFromString(
                            installed_path_plist
                        )
                except Exception:
                    logger.debug("Python plistlib call failed")
            else:
                logger.debug("Did not find an installed_path_plist. Exiting.")
                return install_paths

            if installed_app_dict:
                try:
                    install_paths.append(
                        {
                            "path": installed_path,
                            "version": installed_app_dict["CFBundleVersion"][0:3],
                            "_name": "SketchBook Pro",
                        }
                    )
                except Exception:
                    logger.debug("Python path append failed")
            else:
                logger.debug("Did not find an installed_app_dict. Exiting.")

    else:
        logger.debug("Did not find an installed_path_list. Exiting.")

    return install_paths
