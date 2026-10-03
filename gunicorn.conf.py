"""
Gunicorn hooks (loaded by run.py).

run.py starts gunicorn with --preload, so the Flask app — and the SQLAlchemy connection
pool it already used during start-up — is created in the master process and then
forked into the workers. Without this hook every worker inherits the SAME open SSL
connections to Railway Postgres; two workers writing to one SSL socket corrupts it:
"SSL error: decryption failed or bad record mac".

Each worker therefore discards the inherited pool (without closing the parent's
sockets) and opens its own connections on first use.
"""


def post_fork(server, worker):
    try:
        from app import app
        from core.models import db
        with app.app_context():
            for engine in db.engines.values():
                engine.dispose(close=False)
        server.log.info(f"Worker {worker.pid}: fresh database connection pool")
    except Exception as e:  # never stop a worker from booting because of this
        server.log.warning(f"Worker {worker.pid}: could not reset DB pool: {e}")
