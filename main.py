"""NCE Backend entrypoint."""
import uvicorn
from backend.api.app import create_app
from backend.config.logging_config import setup_logging
from backend.config.settings import get_settings

settings = get_settings()
setup_logging(settings.logging)

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.debug,
        log_level="info",
    )
