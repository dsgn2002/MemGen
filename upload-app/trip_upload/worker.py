"""Exclusive GPU queue supervisor with cancellation and persisted recovery."""
import fcntl
import json
import os
import re
import signal
import subprocess
import time

from .config import ROOT, Settings
from .presentation import carry_forward_presentation
from .store import Store, now


def stop_child(child):
    if child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()


def run_generation(settings, store, job, lock):
    env = {**os.environ, 'TRIP_DATA': str(settings.data), 'TRIP_WORKER_PYTHON':settings.worker_python,
           'TRIP_GENERATION_ROOT':settings.generation_root, 'PYTHONPATH':str(ROOT), 'PYTHONUNBUFFERED':'1'}
    path = store.project_dir(job['project'])/'logs'/('generation-'+job['id']+'.log')
    path.parent.mkdir(parents=True,exist_ok=True)
    child = None
    try:
        with path.open('w') as log:
            child = subprocess.Popen([settings.worker_python,'-m','trip_upload.generation',job['id']],
                env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,pass_fds=(lock.fileno(),))
            started = now()
            while child.poll() is None:
                with store.db() as db:
                    cancelled = db.execute('SELECT cancel FROM generations WHERE id=?',(job['id'],)).fetchone()['cancel']
                if cancelled:
                    stop_child(child)
                    break
                if now()-started > settings.stage_timeout*2:
                    stop_child(child)
                    raise TimeoutError('Generation timed out; inputs and diagnostics retained.')
                time.sleep(1)
        if child.returncode:
            raise RuntimeError('Generation failed. Your approved choices are saved; inspect the private generation log.')
        result = json.loads((store.generation_dir(job['project'],job['id'])/'result.json').read_text())
        if result['generation_id'] != job['id']:
            raise ValueError('Generation result ID mismatch.')
        try:
            if carry_forward_presentation(store, job['id'], result):
                print('Reused curated presentation for the same approved source moments.', flush=True)
        except Exception as error:
            print(f'Presentation reuse skipped: {error}', flush=True)
        store.finish_generation(job['id'])
    except (Exception, KeyboardInterrupt) as error:
        if child:
            stop_child(child)
        store.finish_generation(job['id'],str(error))
        if isinstance(error,KeyboardInterrupt):
            raise


def work(settings, once=False):
    def interrupted(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    store = Store(settings.data)
    with (store.root / 'worker.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another upload worker already owns this queue.')
        store.recover()
        last_cleanup = 0
        while True:
            if now() - last_cleanup > 3600:
                store.cleanup()
                last_cleanup = now()
            job = store.claim()
            if job is None:
                generation = store.claim_generation()
                if generation:
                    run_generation(settings,store,generation,lock)
                    if once:
                        return
                    continue
                if once:
                    return
                time.sleep(2)
                continue
            env = {**os.environ, 'TRIP_DATA': str(settings.data), 'PYTHONPATH': str(ROOT), 'PYTHONUNBUFFERED': '1'}
            log_path = store.project_dir(job['project']) / 'logs' / f"{job['id']}.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            child = None
            try:
                with log_path.open('w') as log:
                    child = subprocess.Popen([settings.worker_python, '-m', 'trip_upload.pipeline', job['id']],
                                             env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                                             pass_fds=(lock.fileno(),))
                    last_stage, stage_started = None, now()
                    log_offset = 0
                    while child.poll() is None:
                        with log_path.open() as progress:
                            progress.seek(log_offset)
                            lines = progress.readlines()
                            log_offset = progress.tell()
                        for line in lines:
                            match = re.search(r'Inspecting (coarse|refinement|photos) frames (\d+)-(\d+)/(\d+)', line)
                            if match:
                                store.stage(job['id'], f"Reviewing {match[1]} images {match[2]}–{match[3]} of {match[4]}")
                            elif line.startswith('Loading local Qwen:'):
                                store.stage(job['id'], 'Loading the local model on Spark')
                            elif line.startswith('Verifying full claims:'):
                                store.stage(job['id'], 'Checking proposed evidence against the original images')
                        with store.db() as db:
                            row = db.execute('SELECT cancel,stage FROM jobs WHERE id=?', (job['id'],)).fetchone()
                        if row['stage'] != last_stage:
                            last_stage, stage_started = row['stage'], now()
                        if row['cancel']:
                            stop_child(child)
                            break
                        if now() - stage_started > settings.stage_timeout:
                            stop_child(child)
                            raise TimeoutError('Analysis stage timed out. Uploaded files and diagnostics are retained.')
                        time.sleep(1)
                if child.returncode:
                    raise RuntimeError('Analysis failed. Your files are saved; the operator can inspect the private job log.')
                path = store.job_dir(job['project'], job['id']) / 'proposal.json'
                value = json.loads(path.read_text())
                if value['job_id'] != job['id'] or value['revision'] != job['revision']:
                    raise ValueError('Analysis returned a mismatched revision.')
                store.finish(job['id'], 'review')
            except (Exception, KeyboardInterrupt) as e:
                if child:
                    stop_child(child)
                store.finish(job['id'], 'failed', str(e))
                if isinstance(e, KeyboardInterrupt):
                    raise
            if once:
                return
