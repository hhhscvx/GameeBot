import json

from .logger import logger
from . import launcher

import os

if not os.path.exists(path="sessions"):
    os.mkdir(path="sessions")
if not os.path.exists(path="gamee_uuid.json"):
    with open('gamee_uuid.json', 'w') as json_file:
        json_file.write(json.dumps({}))
