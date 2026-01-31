import uvicorn

from server.app import create_app
from server.config import PORT

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
