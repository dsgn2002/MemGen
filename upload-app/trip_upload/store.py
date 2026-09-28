import contextlib
import hashlib
import json
import secrets
import sqlite3
import shutil
import time
from pathlib import Path


def now():
    return time.time()


def uid():
    return secrets.token_hex(16)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / 'state.sqlite3'
        with self.db() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS invites(id TEXT PRIMARY KEY, name TEXT, hash TEXT UNIQUE,
                expires REAL, active INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY, owner TEXT, csrf TEXT, expires REAL);
            CREATE TABLE IF NOT EXISTS login_limits(ip TEXT PRIMARY KEY, count INTEGER, started REAL);
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, owner TEXT, title TEXT, request TEXT,
                context TEXT DEFAULT '', revision INTEGER DEFAULT 0, status TEXT DEFAULT 'draft',
                current_job TEXT, approval TEXT, created REAL, updated REAL);
            CREATE TABLE IF NOT EXISTS uploads(id TEXT PRIMARY KEY, project TEXT, name TEXT, kind TEXT,
                size INTEGER, offset INTEGER DEFAULT 0, status TEXT DEFAULT 'uploading', sha256 TEXT,
                metadata TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, project TEXT, revision INTEGER,
                request TEXT, context TEXT, config TEXT, status TEXT DEFAULT 'queued', stage TEXT DEFAULT 'Queued',
                error TEXT, cancel INTEGER DEFAULT 0, created REAL, updated REAL);
            CREATE TABLE IF NOT EXISTS generations(id TEXT PRIMARY KEY, project TEXT, job TEXT,
                approval TEXT, status TEXT DEFAULT 'queued', stage TEXT DEFAULT 'Queued', error TEXT,
                cancel INTEGER DEFAULT 0, created REAL, started REAL, finished REAL);
            CREATE TABLE IF NOT EXISTS upload_parts(upload TEXT, offset INTEGER, size INTEGER, sha256 TEXT,
                PRIMARY KEY(upload,offset));
            CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(status,created);
            ''')

    @contextlib.contextmanager
    def db(self, write=False):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            if write:
                connection.execute('BEGIN IMMEDIATE')
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def invite(self, name, days=30):
        token = secrets.token_urlsafe(32)
        with self.db(True) as db:
            db.execute('INSERT INTO invites(id,name,hash,expires) VALUES(?,?,?,?)',
                       (uid(), name, digest(token), now() + days * 86400))
        return token

    def project_dir(self, project):
        return self.root / 'projects' / project

    def job_dir(self, project, job):
        return self.project_dir(project) / 'jobs' / job

    def stage(self, job, message):
        with self.db(True) as db:
            db.execute('UPDATE jobs SET stage=?,updated=? WHERE id=?', (message, now(), job))

    def finish(self, job, status, error=None):
        with self.db(True) as db:
            row = db.execute('SELECT * FROM jobs WHERE id=?', (job,)).fetchone()
            if not row:
                return
            if row['cancel']:
                status, error = 'cancelled', None
            db.execute('UPDATE jobs SET status=?,stage=?,error=?,updated=? WHERE id=?',
                       (status, {'review':'Ready for review', 'failed':'Analysis failed',
                                 'cancelled':'Cancelled'}[status], error, now(), job))
            db.execute('UPDATE projects SET status=?,updated=? WHERE id=? AND current_job=?',
                       (status, now(), row['project'], job))

    def claim(self):
        with self.db(True) as db:
            row = db.execute("SELECT * FROM jobs WHERE status='queued' AND cancel=0 ORDER BY created LIMIT 1").fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET status='running',stage='Starting analysis',updated=? WHERE id=?", (now(), row['id']))
            db.execute("UPDATE projects SET status='running',updated=? WHERE id=? AND current_job=?", (now(), row['project'], row['id']))
            return dict(row)

    def generation_dir(self, project, generation):
        return self.project_dir(project) / 'generations' / generation

    def generation_stage(self, generation, stage):
        with self.db(True) as db:
            db.execute('UPDATE generations SET stage=? WHERE id=?', (stage, generation))

    def claim_generation(self):
        with self.db(True) as db:
            row = db.execute("SELECT * FROM generations WHERE status='queued' AND cancel=0 ORDER BY created LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute("UPDATE generations SET status='running',stage='Starting generation',started=? WHERE id=?", (now(), row['id']))
            return dict(db.execute('SELECT * FROM generations WHERE id=?', (row['id'],)).fetchone())

    def finish_generation(self, generation, error=None):
        with self.db(True) as db:
            row = db.execute('SELECT cancel FROM generations WHERE id=?', (generation,)).fetchone()
            status = 'cancelled' if row['cancel'] else 'failed' if error else 'ready'
            db.execute('UPDATE generations SET status=?,stage=?,error=?,finished=? WHERE id=?',
                       (status, '3D memory ready' if status == 'ready' else 'Generation ' + status, error, now(), generation))

    def recover(self):
        # Called only by the worker holding the exclusive process lock. Keep failed
        # diagnostics and require an explicit new attempt instead of hidden replay.
        with self.db() as db:
            jobs = [r['id'] for r in db.execute("SELECT id FROM jobs WHERE status='running'")]
        with self.db() as db:
            generations = [r['id'] for r in db.execute("SELECT id FROM generations WHERE status='running'")]
        for generation in generations:
            self.finish_generation(generation, 'Generation worker was interrupted. Saved inputs are retained.')
        for job in jobs:
            self.finish(job, 'failed', 'Worker was interrupted. Review retained diagnostics and retry analysis.')

    def cleanup(self):
        with self.db(True) as db:
            rows = list(db.execute("SELECT id FROM projects WHERE status NOT IN ('queued','running') AND updated<? AND NOT EXISTS (SELECT 1 FROM generations g WHERE g.project=projects.id AND g.status IN ('queued','running'))", (now() - 7 * 86400,)))
            for row in rows:
                shutil.rmtree(self.project_dir(row['id']), ignore_errors=True)
                db.execute('DELETE FROM upload_parts WHERE upload IN (SELECT id FROM uploads WHERE project=?)', (row['id'],))
                for table in ('uploads', 'jobs', 'generations'):
                    db.execute(f'DELETE FROM {table} WHERE project=?', (row['id'],))
                db.execute('DELETE FROM projects WHERE id=?', (row['id'],))
            db.execute('DELETE FROM sessions WHERE expires<?', (now(),))
        return len(rows)
