# Copyright (c) 2020 Autodesk, Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Autodesk, Inc.

"""
This file is loaded automatically by SketchBook at startup
It sets up the Toolkit context and prepares the tk-sketchbook engine.
"""

import os

import sgtk


def start_engine():
    """
    Parse environment variables for an engine name and
    serialized Context to use to startup Toolkit and
    the tk-alias engine and environment.
    """
    sgtk.LogManager().initialize_base_file_handler("tk-sketchbook")
    logger = sgtk.LogManager.get_logger(__name__)

    logger.debug("Launching SketchBook engine")

    try:
        context = sgtk.context.deserialize(os.environ.get("SGTK_CONTEXT"))
        engine = sgtk.platform.start_engine("tk-sketchbook", context.sgtk, context)
    except Exception as e:
        logger.exception(
            "Unexpected exception while launching the SketchBook engine {!r}.".format(e)
        )
        raise
    else:
        logger.debug("Engine started successfully, returning 'SketchBookEngine' object")
        return engine
