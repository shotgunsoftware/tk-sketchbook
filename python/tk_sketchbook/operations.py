# Copyright (c) 2019 Autodesk Inc

import os
import tempfile
import uuid

from sgtk.platform.qt import QtGui

import sketchbook_api


class SketchBookOperations (object):
    def __init__(self, engine):
        """Initialize attributes."""
        self._engine = engine
        self.logger = self._engine.logger

    def get_current_path(self):
        """Get current opened file path."""
        self.logger.debug("Getting current path")
        current_path = alias_api.get_current_path()
        self.logger.debug("Result: {}".format(current_path))

        return current_path

    def open_file(self, path):
        """Open a file in the scene."""
        self.logger.debug("Opening file {}".format(path))

        if not self.can_open_file(path):
            self.logger.debug("Open file aborted because the file is locked")
            return

        as_new_stage = False

        if self.get_current_path() or self.get_stages_number() > 1:
            self.logger.debug("Asking user for deleting the scene or creating a new stage")
            answer = self._can_delete_current_objects()

            if answer == QtGui.QMessageBox.Cancel:
                self.logger.debug("Open file aborted by the user")
                return

            if answer == QtGui.QMessageBox.No:
                as_new_stage = True

        if as_new_stage:
            self.open_file_as_new_stage(path)
        else:
            self.open_file_as_new_scene(path)

        self._engine.stage_selected()

    def create_new_file(self):
        """Create a new file in the scene."""
        self.logger.debug("Creating a New file")

        as_new_stage = False

        self.logger.debug("Asking user for deleting the scene or creating a new stage")
        answer = self._can_delete_current_objects_new_file()

        if answer == QtGui.QMessageBox.Cancel:
            self.logger.debug("Open file aborted by the user")
            return

        if answer == QtGui.QMessageBox.No:
            as_new_stage = True

        if as_new_stage:
            alias_api.create_new_stage(uuid.uuid4().hex)
            pass
        else:
            self.reset_scene()

    def open_file_as_new_stage(self, path):
        """Open a file as a new stage"""
        self.logger.debug("Opening the file as new stage")

        # Opening a file involves closing the old one.
        # Notify the file usage hook of the closing.
        self.current_file_closed()

        success, message = alias_api.open_file_as_new_stage(path)
        self.logger.debug("Result: {}, Message: {}".format(success, message))

        if not success:
            raise Exception("Error opening as new stage the file {}".format(path))

    def open_file_as_new_scene(self, path):
        """Open a file renewing the scene"""
        self.logger.debug("Opening the file as a new scene")

        success, message = alias_api.open_file_as_new_scene(path)
        self.logger.debug("Result: {}, Message: {}".format(success, message))

        if not success:
            raise Exception("Error opening the file {}".format(path))

    def save_file(self):
        """Save current file."""
        self.logger.debug("Saving current_file")

        success, message = alias_api.save_file()

        self.logger.debug("Result: {}, Message: {}".format(success, message))

        if not success:
            raise Exception("Error saving the current file")

    def save_file_as(self, path):
        """Save new file."""
        self.logger.debug("Saving file as: {}".format(path))

        self.current_file_closed()

        success, message = alias_api.save_file_as(path)

        self.logger.debug("Result: {}, Message: {}".format(success, message))

        if not success:
            raise Exception("Error saving the file {}".format(path))

        self._engine.execute_hook_method("file_usage_hook", "file_attempt_open", path=path)

    def reset_scene(self):
        """Reset the current scene."""
        self.logger.debug("Resetting the scene")

        self.current_file_closed()

        success, message = alias_api.reset_scene()

        self.logger.debug("Result: {}, Message: {}".format(success, message))

        if not success:
            raise Exception("Error resetting the scene")

    @staticmethod
    def get_parent_window():
        """Return current active window as parent"""
        return QtGui.QApplication.activeWindow()

    def current_file_closed(self):
        """This method should be called when the current file is closed."""
        path = self.get_current_path()
        if not path:
            return

        self.logger.debug("current_file_closed: notifying the file usage hook that the current file has closed")
        self._engine.execute_hook_method("file_usage_hook", "file_closed", path=path)

    def can_open_file(self, path):
        """Check if file can be opened."""
        self.logger.debug("Check availability of {}".format(path))

        return self._engine.execute_hook_method("file_usage_hook", "file_attempt_open", path=path)

    def _can_delete_current_objects(self):
        """Confirm if can delete objects."""
        message = "DELETE all objects, shaders, views and actions in all existing Stage before Opening this File?"
        message_type = QtGui.QMessageBox.Yes | QtGui.QMessageBox.No | QtGui.QMessageBox.Cancel
        answer = QtGui.QMessageBox.question(self.get_parent_window(), "Open", message, message_type)

        return answer

    def _can_delete_current_objects_new_file(self):
        """Confirm if can delete objects."""
        message = "DELETE all objects, shaders, views and actions in all existing Stages before Opening a New " \
                  "File?"
        message_type = QtGui.QMessageBox.Yes | QtGui.QMessageBox.No | QtGui.QMessageBox.Cancel
        answer = QtGui.QMessageBox.question(self.get_parent_window(), "Open", message, message_type)

        return answer

    def create_reference(self, path, standalone=True):
        """Load a file inside the scene as a reference."""
        self.logger.debug("Creating a reference to {}".format(path))

        if not os.path.exists(path):
            raise Exception("File not found on disk - '%s'" % path)

        success, message = alias_api.create_reference(path)
        self.logger.debug("Result: {}, Message: {}".format(success, message))

        if success:
            self._engine.stage_selected()

        if not standalone:
            message_type = "information" if success else "warning"
            return dict(message_type=message_type, message_code=message, publish_path=path,
                        is_error=False if success else True)

        if not success:
            raise Exception("Error creating the reference")

        QtGui.QMessageBox.information(self.get_parent_window(), "Reference File", "File referenced successfully.")

    def import_file(self, path, create_stage=False, standalone=True):
        """Import a file into the current scene."""
        self.logger.debug("Importing the file {}, and the create stage: {}".format(path, create_stage))

        if not os.path.exists(path):
            raise Exception("File not found on disk - '%s'" % path)

        if create_stage:
            success, message = alias_api.open_file_as_new_stage(path)
        else:
            success, message = alias_api.import_file(path)

        self.logger.debug("Result: {}, Message: {}".format(success, message))

        if success:
            self._engine.stage_selected()

        if not standalone:
            message_type = "information" if success else "warning"
            return dict(message_type=message_type, message_code=message, publish_path=path,
                        is_error=False if success else True)

        if not success:
            raise Exception("Error import the file")

        QtGui.QMessageBox.information(self.get_parent_window(), "Import File", "File imported successfully.")

    def create_texture_node(self, path, standalone=True):
        """Create a texture node."""
        self.logger.debug("Creating a texture node of {}".format(path))

        if not os.path.exists(path):
            raise Exception("File not found on disk - '%s'" % path)

        success, message = alias_api.create_texture_node(path)
        self.logger.debug("Result: {}, Message: {}".format(success, message))

        if success:
            self._engine.stage_selected()

        if not standalone:
            message_type = "information" if success else "warning"
            return dict(message_type=message_type, message_code=message, publish_path=path,
                        is_error=False if success else True)

        if not success:
            raise Exception("Error creating a texture node")

        QtGui.QMessageBox.information(self.get_parent_window(), "Texture Node", "Texture node created successfully.")

    def get_references(self):
        """Get references."""
        self.logger.debug("Getting references")

        COL_SEPARATOR = "COLSEP"
        ROW_SEPARATOR = "ROWSEP"
        references_string = alias_api.get_references()
        references = []

        self.logger.debug("Received: {}".format(references_string))

        for row in references_string.split(ROW_SEPARATOR):
            if not row or COL_SEPARATOR not in row:
                continue

            name, path = row.split(COL_SEPARATOR)

            references.append({
                "node": name,
                "type": "reference",
                "path": path.replace("/", os.path.sep)
            })

        self.logger.debug("Sending: {}".format(references))

        return references

    def update_scene(self, items):
        """Get references."""
        self.logger.debug("Updating scene {}".format(items))

        if not items:
            self.logger.debug("No items to update")
            return

        success, message = alias_api.update_scene(items)

        self.logger.debug("Result: {}, Message: {}".format(success, message))

        if not success:
            msg = "One or more selected items cannot be updated.\nIf there is another version of this file " \
                  "referenced, please check the Alias Reference Manager and remove its reference to enable the update."
            raise Exception(msg)

    def get_info(self):
        """
        Get info.

        :returns: Dict with keys version_number, product_version, product_key, product_license_type,
                                 product_license_path, product_name
        """
        self.logger.debug("Getting info")

        info = alias_api.get_info()

        self.logger.debug("Result: {}".format(info))

        return info

    def get_annotations(self):
        """Export annotations."""
        self.logger.debug("Getting annotations")

        annotations = alias_api.get_annotations()

        self.logger.debug("Result: {}".format(annotations))

        return annotations

    def get_variants(self):
        """Export variants."""
        self.logger.debug("Getting variants")
        success, variants = alias_api.get_variants(tempfile.gettempdir(), uuid.uuid4().hex)
        self.logger.debug("Result: {}, Message: {}".format(success, variants))

        return variants

    def get_stages_number(self):
        """Get stages number."""
        self.logger.debug("Getting stages number")
        stages_number = alias_api.get_stages_number()
        self.logger.debug("Result: {}".format(stages_number))

        return stages_number
