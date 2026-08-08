import os

# Must be set before `app` is imported by any test module so the SQLAlchemy
# engine is created against an in-memory SQLite database. This prevents the
# test suite from ever touching (or wiping) the real on-disk `instance/bos.db`.
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
