import os

from flask import Flask

import config
import util
import views
from models import db
from sockets import socketio

app = Flask(__name__)
self_path = os.path.dirname(os.path.abspath(__file__))
app.config.from_object(config.JudgeConfig(app_root=self_path))

app.json_encoder = util.JSONEncoder

db.init_app(app)
if app.config['ENABLE_SOCKETIO']:
    socketio.init_app(app, message_queue=app.config['REDIS_URI'])

app.register_blueprint(views.blueprint)
