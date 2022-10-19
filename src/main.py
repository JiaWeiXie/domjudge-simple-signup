import asyncio

from core.config import settings
from ui.views import MainInterface

if __name__ == "__main__":
    interface = MainInterface(settings)
    asyncio.run(interface.render())
