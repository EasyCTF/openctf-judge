from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager, Server

import util
from main import app
from models import db, APIKey

manager = Manager(app)

migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)

server_command = Server(host='0.0.0.0', port=5000, use_debugger=True, use_reloader=True)
manager.add_command('runserver', server_command)

api_key_manager = Manager()


@api_key_manager.command
def generate(name=None, jury=False, reader=False, master=False):
    if name and len(name) > 16:
        print('Name must be 16 characters or less.')
        return
    with app.app_context():
        api_key = APIKey.new(name=name, perm_jury=jury, perm_reader=reader, perm_master=master)
        key = api_key.key
    print(key)

manager.add_command('api_key', api_key_manager)

if __name__ == '__main__':
    manager.run()
