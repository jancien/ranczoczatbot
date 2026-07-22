from .app import app, rt
import uvicorn

from .admin import routes as admin_routes
from .user import routes as user_routes
from .config import settings

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.port, log_level="warning")
