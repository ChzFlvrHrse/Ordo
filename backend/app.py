import os, logging
from dotenv import load_dotenv
from quart import Quart
from quart_cors import cors
# from modal import App, Image, Secret, asgi_app, fastapi_endpoint, Period

# Blueprints
from api import (
    google_calendar_bp,
    agent_bp,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# modal_app = App(name="ordo-backend")

# image = (
#     Image.debian_slim(python_version="3.12")
#     .pip_install_from_requirements("requirements.txt")
#     .add_local_dir("api", "/root/api")
# )

quart_app = Quart(__name__)
quart_app = cors(
    quart_app,
    allow_origin="*",
    allow_methods=["GET", "POST", "PUT", "PATCH",
                   "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Webhook-Secret", "X-Webhook-Signature"]
)

# Blueprints registration
quart_app.register_blueprint(google_calendar_bp)
quart_app.register_blueprint(agent_bp)

# @modal_app.function(image=image)
# @asgi_app()
# def quart_app():
#     return quart_app


# @modal_app.local_entrypoint()
# def serve():
#     return quart_app.run()

@quart_app.route('/callback')
async def callback():
    return "connected", 200

if __name__ == "__main__":
    from classes import OrdoDB
    db = OrdoDB()
    # db.seed()
    # db.reset()
    # db.seed(
    #     name="Ordo Dev",
    #     api_key="ordo_sk_7f3a91c2e84b56d0f2a7139e4c8b05d1",
    #     redirect_uri="http://localhost:5000/callback",
    # )
    quart_app.run(host="0.0.0.0", port=5000)
