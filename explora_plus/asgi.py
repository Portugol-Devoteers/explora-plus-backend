import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "explora_plus.settings.docker")
application = get_asgi_application()
