#!/usr/bin/env python

import ConfigParser
import os
import user

APP_NAME = "taskdav"

# TODO: make this cross-platform: http://stackoverflow.com/questions/2243895/location-to-put-user-configuration-files-in-windows
CONFIG_PATHS = [
    os.path.join("/etc", "%s.config" % APP_NAME),
    os.path.join(user.home, ".%s" % APP_NAME),
]

def get_config():
    parser = ConfigParser.SafeConfigParser()
    for config_file in CONFIG_PATHS:
        if os.path.exists(config_file):
            parser.read(config_file)
    return parser


