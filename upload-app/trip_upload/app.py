"""Owner-scoped HTTP API. GPU work is performed only by the separate worker."""
import json
import hashlib
import secrets
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict

from .config import ROOT, Settings
from .store import Store, uid, now, digest
from .media import inspect_upload, sha256
from .generation import available as generation_available


class Body(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Login(Body):
    code: str = Field(min_length=12, max_length=160)


class Project(Body):
    title: str = Field(min_length=1, max_length=100)
    request: str = Field(min_length=1, max_length=4000)
    context: str = Field(default='', max_length=4000)


class Upload(Body):
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(pattern='^(video|photo)$')
    size: int = Field(gt=0, le=500 * 1024 * 1024)


class Analysis(Body):
    request: str = Field(min_length=1, max_length=4000)
    context: str = Field(default='', max_length=4000)


class Approval(Body):
    job_id: str
    revision: int
    proposal_sha256: str
    moment_ids: list[str] = Field(min_length=1, max_length=3)
    style: str = Field(pattern='^(natural|cinematic|illustrated)$')
    lighting: str = Field(pattern='^(day|sunset|night)$')
    notes: str = Field(default='', max_length=4000)


def create_app(settings=None):
    settings = settings or Settings.env()
    store = Store(settings.data)
    app = FastAPI(title='MemGen upload & evidence', docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store, app.state.settings = store, settings

    @app.middleware('http')
    async def policy(request, call_next):
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            length = request.headers.get('content-length')
            is_chunk = request.method == 'PUT' and '/uploads/' in request.url.path
            if not is_chunk and ((length is not None and (not length.isdigit() or int(length) > 32768))
                                 or request.headers.get('transfer-encoding')):
                return JSONResponse({'detail': 'Metadata requests must declare a body of at most 32 KB.'}, status_code=413)
            origin = request.headers.get('origin')
            if origin and urlsplit(origin).netloc != request.headers.get('host'):
                return JSONResponse({'detail': 'Cross-origin writes are not allowed.'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/api') else 'no-cache'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' blob:; media-src 'self' blob:; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.url.path == '/static/generation.html':
            response.headers['Content-Security-Policy'] = response.headers['Content-Security-Policy'].replace("script-src 'self'", "script-src 'self' 'wasm-unsafe-eval'")
        return response

    def owner(request: Request):
        token = request.cookies.get('trip_session', '')
        with store.db() as db:
            session = db.execute('SELECT s.*,i.name FROM sessions s JOIN invites i ON s.owner=i.id '
                'WHERE s.hash=? AND s.expires>? AND i.active=1 AND i.expires>?', (digest(token), now(), now())).fetchone()
        if not session:
            raise HTTPException(401, 'Enter your invitation code to continue.')
        if request.method not in {'GET', 'HEAD'} and not secrets.compare_digest(request.headers.get('x-csrf-token', ''), session['csrf']):
            raise HTTPException(403, 'Refresh this page before trying again.')
        return dict(session)

    def owned(db, project, who):
        row = db.execute('SELECT * FROM projects WHERE id=? AND owner=?', (project, who['owner'])).fetchone()
        if not row:
            raise HTTPException(404, 'Project not found.')
        return dict(row)

    def no_active_generation(db, project):
        if db.execute("SELECT 1 FROM generations WHERE project=? AND status IN ('queued','running')", (project,)).fetchone():
            raise HTTPException(409, 'Wait for generation to finish or cancel it first.')

    def upload_row(db, project, upload):
        row = db.execute('SELECT * FROM uploads WHERE id=? AND project=?', (upload, project)).fetchone()
        if not row:
            raise HTTPException(404, 'Upload not found.')
        return dict(row)

    def can_upload(p):
        if p['revision'] != 0:
            raise HTTPException(409, 'Media is fixed after analysis starts. Create a new project to change it.')

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'generation_available': generation_available(settings)}

    @app.post('/api/login')
    def login(body: Login, request: Request):
        # Never trust forwarded IP headers from an unconfigured reverse proxy.
        ip = request.client.host if request.client else 'unknown'
        with store.db(True) as db:
            limit = db.execute('SELECT * FROM login_limits WHERE ip=?', (ip,)).fetchone()
            if limit and limit['started'] > now() - 600 and limit['count'] >= 15:
                raise HTTPException(429, 'Too many attempts. Try again in ten minutes.')
            count = limit['count'] + 1 if limit and limit['started'] > now() - 600 else 1
            started = limit['started'] if count > 1 else now()
            db.execute('INSERT OR REPLACE INTO login_limits VALUES(?,?,?)', (ip, count, started))
            invite = db.execute('SELECT * FROM invites WHERE hash=? AND active=1 AND expires>?', (digest(body.code), now())).fetchone()
            if invite:
                token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
                db.execute('INSERT INTO sessions VALUES(?,?,?,?)', (digest(token), invite['id'], csrf, now() + 86400))
                db.execute('DELETE FROM login_limits WHERE ip=?', (ip,))
        if not invite:
            raise HTTPException(401, 'Invitation code is invalid or expired.')
        response = JSONResponse({'name': invite['name'], 'csrf': csrf})
        response.set_cookie('trip_session', token, httponly=True, secure=settings.secure_cookie,
                            samesite='strict', max_age=86400, path='/')
        return response

    @app.get('/api/session')
    def session(who=Depends(owner)):
        return {'name': who['name'], 'csrf': who['csrf'], 'limits': {'video_mb': 500, 'video_minutes': 5,
                'photos': 12, 'photo_mb': 20, 'chunk_size': settings.chunk_size}}

    @app.post('/api/logout')
    def logout(who=Depends(owner)):
        with store.db(True) as db:
            db.execute('DELETE FROM sessions WHERE hash=?', (who['hash'],))
        response = JSONResponse({'ok': True})
        response.delete_cookie('trip_session', path='/')
        return response

    @app.get('/api/projects')
    def projects(who=Depends(owner)):
        with store.db() as db:
            return [dict(r) for r in db.execute('SELECT id,title,status,revision,created,updated FROM projects WHERE owner=? ORDER BY updated DESC', (who['owner'],))]

    @app.post('/api/projects', status_code=201)
    def create(body: Project, who=Depends(owner)):
        if not body.title.strip() or not body.request.strip():
            raise HTTPException(422, 'Enter a title and what you want to highlight.')
        identifier = uid()
        with store.db(True) as db:
            if db.execute('SELECT count(*) FROM projects WHERE owner=?', (who['owner'],)).fetchone()[0] >= settings.max_projects:
                raise HTTPException(429, 'Delete an old project before creating another.')
            db.execute('INSERT INTO projects(id,owner,title,request,context,created,updated) VALUES(?,?,?,?,?,?,?)',
                       (identifier, who['owner'], body.title.strip(), body.request, body.context, now(), now()))
        return {'id': identifier}

    @app.get('/api/projects/{project}')
    def detail(project: str, who=Depends(owner)):
        with store.db() as db:
            p = owned(db, project, who)
            p.pop('owner')
            p['uploads'] = [dict(r) for r in db.execute('SELECT * FROM uploads WHERE project=? ORDER BY created', (project,))]
            for u in p['uploads']:
                u['metadata'] = json.loads(u['metadata']) if u['metadata'] else None
                u['parts'] = [dict(r) for r in db.execute('SELECT offset,size,sha256 FROM upload_parts WHERE upload=? ORDER BY offset', (u['id'],))] if u['status'] == 'uploading' else []
            job = db.execute('SELECT id,revision,status,stage,error,created,updated FROM jobs WHERE id=?', (p['current_job'],)).fetchone()
            p['job'] = dict(job) if job else None
            generation = db.execute('SELECT id,status,stage,error,created,started,finished FROM generations WHERE project=? AND job=? ORDER BY created DESC LIMIT 1', (project, p['current_job'])).fetchone()
            p['generation'] = dict(generation) if generation else None
            p['generation_available'] = generation_available(settings)
            p['approval'] = json.loads(p['approval']) if p['approval'] else None
        return p

    @app.post('/api/projects/{project}/uploads', status_code=201)
    def begin_upload(project: str, body: Upload, who=Depends(owner)):
        if body.size > (settings.max_photo if body.kind == 'photo' else settings.max_video):
            raise HTTPException(413, 'This file exceeds the upload size limit.')
        identifier = uid()
        with store.db(True) as db:
            p = owned(db, project, who)
            can_upload(p)
            rows = db.execute('SELECT kind FROM uploads WHERE project=?', (project,)).fetchall()
            if rows and (body.kind == 'video' or any(r['kind'] != 'photo' for r in rows)):
                raise HTTPException(409, 'Upload one video OR a collection of photos.')
            if len(rows) >= 12:
                raise HTTPException(409, 'A project accepts up to 12 photos.')
            db.execute('INSERT INTO uploads(id,project,name,kind,size,created) VALUES(?,?,?,?,?,?)',
                       (identifier, project, body.name, body.kind, body.size, now()))
            db.execute('UPDATE projects SET updated=? WHERE id=?', (now(), project))
        return {'id': identifier, 'offset': 0, 'chunk_size': settings.chunk_size}

    @app.put('/api/projects/{project}/uploads/{upload}')
    async def chunk(project: str, upload: str, request: Request, offset: int, who=Depends(owner)):
        if offset < 0:
            raise HTTPException(422, 'Invalid upload offset.')
        data = bytearray()
        async for part in request.stream():
            data.extend(part)
            if len(data) > settings.chunk_size:
                raise HTTPException(413, 'Upload chunks must be at most 8 MB.')
        if not data:
            raise HTTPException(422, 'Empty upload chunk.')
        with store.db(True) as db:
            can_upload(owned(db, project, who))
            u = upload_row(db, project, upload)
            if u['status'] != 'uploading':
                raise HTTPException(409, 'Upload is already finalized.')
            path = store.project_dir(project) / 'media' / upload / 'original'
            path.parent.mkdir(parents=True, exist_ok=True)
            if offset < u['offset'] and offset + len(data) <= u['offset']:
                with path.open('rb') as f:
                    f.seek(offset)
                    if f.read(len(data)) == data:
                        return {'offset': u['offset']}
            if offset != u['offset']:
                raise HTTPException(409, {'message': 'Resume from the server offset.', 'offset': u['offset']})
            if offset + len(data) > u['size']:
                raise HTTPException(413, 'Chunk exceeds the declared file size.')
            with path.open('r+b' if path.exists() else 'wb') as f:
                f.truncate(offset)
                f.seek(offset)
                f.write(data)
                f.flush()
                import os
                os.fsync(f.fileno())
            db.execute('UPDATE uploads SET offset=? WHERE id=?', (offset + len(data), upload))
            db.execute('INSERT OR REPLACE INTO upload_parts VALUES(?,?,?,?)',
                       (upload, offset, len(data), hashlib.sha256(data).hexdigest()))
        return {'offset': offset + len(data)}

    @app.post('/api/projects/{project}/uploads/{upload}/complete')
    def complete(project: str, upload: str, who=Depends(owner)):
        # Serializes finalize/delete/analyze against the same SQLite write lock.
        with store.db(True) as db:
            can_upload(owned(db, project, who))
            u = upload_row(db, project, upload)
            if u['status'] == 'ready':
                return {'status': 'ready', 'sha256': u['sha256']}
            if u['offset'] != u['size']:
                raise HTTPException(409, 'Upload is incomplete.')
            folder = store.project_dir(project) / 'media' / upload
            try:
                metadata = inspect_upload(folder / 'original', u['kind'], folder)
            except (ValueError, OSError, RuntimeError) as e:
                raise HTTPException(422, str(e)) from e
            checksum = sha256(folder / 'original')
            db.execute("UPDATE uploads SET status='ready',sha256=?,metadata=? WHERE id=?", (checksum, json.dumps(metadata), upload))
        return {'status': 'ready', 'sha256': checksum}

    @app.delete('/api/projects/{project}/uploads/{upload}')
    def remove_upload(project: str, upload: str, who=Depends(owner)):
        with store.db(True) as db:
            can_upload(owned(db, project, who))
            upload_row(db, project, upload)
            shutil.rmtree(store.project_dir(project) / 'media' / upload, ignore_errors=True)
            db.execute('DELETE FROM upload_parts WHERE upload=?', (upload,))
            db.execute('DELETE FROM uploads WHERE id=?', (upload,))
        return {'ok': True}

    @app.get('/api/projects/{project}/uploads/{upload}/preview')
    def preview(project: str, upload: str, who=Depends(owner)):
        with store.db() as db:
            owned(db, project, who)
            u = upload_row(db, project, upload)
        if u['status'] != 'ready':
            raise HTTPException(404, 'Preview not ready.')
        return FileResponse(store.project_dir(project) / 'media' / upload / 'preview.jpg', media_type='image/jpeg')

    @app.post('/api/projects/{project}/analyze', status_code=202)
    def analyze(project: str, body: Analysis, who=Depends(owner)):
        if not body.request.strip():
            raise HTTPException(422, 'Describe what you want to highlight.')
        if not settings.model:
            raise HTTPException(503, 'The local model has not been configured. Your uploads are saved.')
        with store.db(True) as db:
            p = owned(db, project, who)
            no_active_generation(db, project)
            if p['status'] in {'queued', 'running'}:
                raise HTTPException(409, 'This project already has an active analysis.')
            media = db.execute('SELECT * FROM uploads WHERE project=?', (project,)).fetchall()
            if not media or any(u['status'] != 'ready' for u in media):
                raise HTTPException(409, 'Finish uploading all media first.')
            active = db.execute("SELECT count(*) FROM jobs j JOIN projects p ON j.project=p.id WHERE p.owner=? AND j.status IN ('queued','running')", (who['owner'],)).fetchone()[0]
            if active >= 2 or db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0] >= 8:
                raise HTTPException(429, 'The analysis queue is full. Try again later.')
            job, revision = uid(), p['revision'] + 1
            cfg = {'coarse': settings.coarse, 'refinement': settings.refinement, 'batch': settings.batch,
                   'model': settings.model, 'media_hashes': {u['id']: u['sha256'] for u in media}}
            db.execute('INSERT INTO jobs(id,project,revision,request,context,config,created,updated) VALUES(?,?,?,?,?,?,?,?)',
                       (job, project, revision, body.request, body.context, json.dumps(cfg), now(), now()))
            db.execute("UPDATE projects SET revision=?,current_job=?,request=?,context=?,status='queued',approval=NULL,updated=? WHERE id=?",
                       (revision, job, body.request, body.context, now(), project))
        return {'job_id': job, 'revision': revision}

    @app.post('/api/projects/{project}/cancel')
    def cancel(project: str, who=Depends(owner)):
        with store.db(True) as db:
            p = owned(db, project, who)
            no_active_generation(db, project)
            if p['status'] in {'queued', 'running'}:
                db.execute('UPDATE jobs SET cancel=1 WHERE id=?', (p['current_job'],))
                if p['status'] == 'queued':
                    db.execute("UPDATE jobs SET status='cancelled',stage='Cancelled',updated=? WHERE id=?", (now(), p['current_job']))
                    db.execute("UPDATE projects SET status='cancelled',updated=? WHERE id=?", (now(), project))
        return {'ok': True}

    def proposal_file(p):
        if p['status'] not in {'review', 'approved'}:
            raise HTTPException(409, 'Evidence is not ready for review.')
        return store.job_dir(p['id'], p['current_job']) / 'proposal.json'

    @app.get('/api/projects/{project}/proposal')
    def proposal(project: str, who=Depends(owner)):
        with store.db() as db:
            p = owned(db, project, who)
        path = proposal_file(p)
        return {'proposal': json.loads(path.read_text()), 'sha256': sha256(path)}

    @app.get('/api/projects/{project}/artifacts/{relative:path}')
    def artifact(project: str, relative: str, who=Depends(owner)):
        with store.db() as db:
            p = owned(db, project, who)
        prop = json.loads(proposal_file(p).read_text())
        allowed = {prop.get('contact_sheet')}
        for moment in prop['moments']:
            allowed.update([moment['image'], moment.get('clip')])
            allowed.update(r['image'] for r in moment['references'])
        if relative not in allowed or '..' in Path(relative).parts:
            raise HTTPException(404, 'Artifact not found.')
        base = store.job_dir(project, p['current_job']).resolve()
        path = (base / relative).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            raise HTTPException(404, 'Artifact not found.')
        return FileResponse(path)

    @app.post('/api/projects/{project}/approve')
    def approve(project: str, body: Approval, who=Depends(owner)):
        with store.db(True) as db:
            p = owned(db, project, who)
            no_active_generation(db, project)
            path = proposal_file(p)
            if body.job_id != p['current_job'] or body.revision != p['revision'] or body.proposal_sha256 != sha256(path):
                raise HTTPException(409, 'This proposal changed. Reload and review the current version.')
            prop = json.loads(path.read_text())
            chosen = set(body.moment_ids)
            if len(chosen) != len(body.moment_ids) or not chosen <= {m['id'] for m in prop['moments']}:
                raise HTTPException(422, 'Choose distinct moments from this proposal.')
            saved = {**body.model_dump(), 'approved_at': now(), 'generation_started': False,
                     'note': 'Selection approval does not independently verify model descriptions or identities.'}
            db.execute("UPDATE projects SET approval=?,status='approved',updated=? WHERE id=?", (json.dumps(saved), now(), project))
        return {'approval': saved, 'generation_available': generation_available(settings)}

    @app.post('/api/projects/{project}/generate', status_code=202)
    def generate(project: str, who=Depends(owner)):
        if not generation_available(settings):
            raise HTTPException(503, 'Local generation models are not configured on this host.')
        with store.db(True) as db:
            p = owned(db, project, who)
            no_active_generation(db, project)
            if p['status'] != 'approved' or not p['approval']:
                raise HTTPException(409, 'Save your moment and style choices first.')
            approval = json.loads(p['approval'])
            if approval['job_id'] != p['current_job'] or approval['revision'] != p['revision'] or approval['proposal_sha256'] != sha256(proposal_file(p)):
                raise HTTPException(409, 'The approved proposal changed. Review it again.')
            if db.execute("SELECT count(*) FROM generations WHERE status IN ('queued','running')").fetchone()[0] >= 8:
                raise HTTPException(429, 'Generation queue is full.')
            existing = db.execute("SELECT id,approval FROM generations WHERE project=? AND job=? AND status='ready' ORDER BY created DESC", (project,p['current_job'])).fetchall()
            for row in existing:
                if json.loads(row['approval']) == approval:
                    return {'generation_id': row['id'], 'reused': True}
            identifier = uid()
            db.execute('INSERT INTO generations(id,project,job,approval,created) VALUES(?,?,?,?,?)',
                       (identifier, project, p['current_job'], json.dumps(approval), now()))
        return {'generation_id': identifier}

    @app.post('/api/projects/{project}/generations/{generation}/cancel')
    def cancel_generation(project: str, generation: str, who=Depends(owner)):
        with store.db(True) as db:
            owned(db, project, who)
            row = db.execute('SELECT status FROM generations WHERE id=? AND project=?', (generation,project)).fetchone()
            if not row:
                raise HTTPException(404, 'Generation not found.')
            db.execute("UPDATE generations SET cancel=1 WHERE id=? AND status IN ('queued','running')", (generation,))
            if row['status'] == 'queued':
                db.execute("UPDATE generations SET status='cancelled',stage='Generation cancelled',finished=? WHERE id=?", (now(),generation))
        return {'ok': True}

    @app.get('/api/projects/{project}/generations/{generation}/result')
    def generation_result(project: str, generation: str, who=Depends(owner)):
        with store.db() as db:
            owned(db, project, who)
            row = db.execute('SELECT * FROM generations WHERE id=? AND project=?', (generation,project)).fetchone()
            if not row or row['status'] != 'ready':
                raise HTTPException(409, 'Generation is not ready.')
        return json.loads((store.generation_dir(project,generation)/'result.json').read_text())

    @app.get('/api/projects/{project}/generations/{generation}/assets/{name}')
    def generation_asset(project: str, generation: str, name: str, who=Depends(owner)):
        result = generation_result(project,generation,who)
        allowed = {a[k] for a in result['assets'] for k in ('mesh','design','source')}
        if name not in allowed:
            raise HTTPException(404, 'Asset not found.')
        return FileResponse(store.generation_dir(project,generation)/'output'/name)

    @app.delete('/api/projects/{project}')
    def delete(project: str, who=Depends(owner)):
        with store.db(True) as db:
            p = owned(db, project, who)
            no_active_generation(db, project)
            if p['status'] in {'queued', 'running'}:
                raise HTTPException(409, 'Cancel the analysis and wait for it to stop before deleting.')
            shutil.rmtree(store.project_dir(project), ignore_errors=True)
            db.execute('DELETE FROM upload_parts WHERE upload IN (SELECT id FROM uploads WHERE project=?)', (project,))
            for table in ('uploads', 'jobs', 'generations'):
                db.execute(f'DELETE FROM {table} WHERE project=?', (project,))
            db.execute('DELETE FROM projects WHERE id=?', (project,))
        return {'ok': True}

    app.mount('/static', StaticFiles(directory=ROOT / 'web'), name='static')

    @app.get('/')
    def index():
        return FileResponse(ROOT / 'web/index.html')

    return app
