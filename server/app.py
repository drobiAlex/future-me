import contextlib

from fastapi import FastAPI

from server.mcp_server import create_mcp_server
from server.middleware import add_cors


def create_app() -> FastAPI:
    mcp = create_mcp_server()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        async with mcp.session_manager.run():
            yield

    app = FastAPI(title="Goal Tracker MCP", lifespan=lifespan)
    add_cors(app)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.mount("/", mcp.streamable_http_app())

    return app
