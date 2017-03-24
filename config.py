import os
import pathlib

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

SUPPORTED_LANGUAGES = {
    'cxx': 'C++',
    'python2': 'Python 2',
    'python3': 'Python 3',
    'java': 'Java',
}


class JudgeConfig:
    def __init__(self, app_root: str = None, testing: bool = False):
        if app_root is None:
            self.app_root = pathlib.Path(os.path.dirname(os.path.abspath(__file__)))
        else:
            self.app_root = pathlib.Path(app_root)

        self.ENABLE_SOCKETIO = bool(int(os.getenv('ENABLE_SOCKETIO', 1)))

        self.SECRET_KEY = None
        self._load_secret_key()
        self.SQLALCHEMY_DATABASE_URI = self._get_test_database_uri() if testing else self._get_database_uri()
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        self.REDIS_URI = self._get_redis_uri()

        if testing:
            self.TESTING = True
            self.WTF_CSRF_ENABLED = False

    def _load_secret_key(self):
        if 'SECRET_KEY' in os.environ:
            self.SECRET_KEY = os.environ['SECRET_KEY']
        else:
            secret_path = self.app_root / '.secret_key'
            with secret_path.open('a+b') as secret_file:
                secret_file.seek(0)
                contents = secret_file.read()
                if not contents and len(contents) == 0:
                    key = os.urandom(128)
                    secret_file.write(key)
                    secret_file.flush()
                else:
                    key = contents
            self.SECRET_KEY = key

        return self.SECRET_KEY

    def _get_database_uri(self):
        return os.getenv('DATABASE_URI', '')

    def _get_test_database_uri(self):
        return os.getenv('TEST_DATABASE_URI', '')

    def _get_redis_uri(self):
        return os.getenv('REDIS_URI', '')
