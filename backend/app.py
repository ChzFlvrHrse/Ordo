import os, logging
from quart import Quart
from quart_cors import cors
from dotenv import load_dotenv
from api.scheduler import scheduler
# from modal import App, Image, Secret, asgi_app, fastapi_endpoint, Period

# Blueprint imports
from api import (
    agent_bp,
    action_bp,
    integrations_bp,
    google_calendar_bp,
    microsoft_calendar_bp,
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
quart_app.register_blueprint(agent_bp)
quart_app.register_blueprint(action_bp)
quart_app.register_blueprint(integrations_bp)
quart_app.register_blueprint(google_calendar_bp)
quart_app.register_blueprint(microsoft_calendar_bp)

# @modal_app.function(image=image)
# @asgi_app()
# def quart_app():
#     return quart_app


# @modal_app.local_entrypoint()
# def serve():
#     return quart_app.run()

@quart_app.before_serving
async def startup():
    scheduler.start()

@quart_app.after_serving
async def shutdown():
    scheduler.shutdown()

if __name__ == "__main__":
    from classes import OrdoDB
    db = OrdoDB()
    # db.reset()
    # db.seed()
    quart_app.run(host="0.0.0.0", port=5000)
