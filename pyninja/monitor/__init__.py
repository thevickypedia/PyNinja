import os

from fastapi.templating import Jinja2Templates

from pyninja.monitor import router, authenticator, config, squire, secure

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
