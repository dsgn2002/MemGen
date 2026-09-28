'use strict';
// Progress is based on bytes acknowledged by Spark, not the browser's local socket.
globalThis.TripUpload = (() => {
  const KiB = 1024, MiB = 1024 * KiB;
  async function verify(file, upload) {
    for (const part of upload.parts || []) {
      const bytes = await file.slice(part.offset, part.offset + part.size).arrayBuffer();
      const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))]
        .map(x => x.toString(16).padStart(2, '0')).join('');
      if (hash !== part.sha256) throw new Error('This file differs from the interrupted upload. Remove that upload and choose the correct file.');
    }
  }
  async function transfer(file, upload, project, api, progress, options = {}) {
    const now = options.now || (() => performance.now());
    const delay = options.delay || (ms => new Promise(resolve => setTimeout(resolve, ms)));
    const timeout = options.timeout || 45000;
    const path = `/projects/${project}/uploads/${upload.id}`;
    let offset = upload.offset, chunkSize = 128 * KiB, failures = 0;
    const started = now(), initial = offset;
    async function request(url, config = {}) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeout);
      try { return await api(url, {...config, signal: controller.signal}); }
      finally { clearTimeout(timer); }
    }
    function status(waiting = '') {
      const elapsed = Math.max(.001, (now() - started) / 1000);
      const rate = (offset - initial) / elapsed;
      const remaining = rate > 0 ? Math.ceil((file.size - offset) / rate / 60) : null;
      progress(`${file.name} · ${(100 * offset / file.size).toFixed(1)}% saved on Spark` +
        ` · ${(offset / MiB).toFixed(2)} / ${(file.size / MiB).toFixed(2)} MiB` +
        (rate > 0 ? ` · ${(rate / KiB).toFixed(1)} KiB/s · about ${Math.max(1, remaining)} min left` : '') + waiting);
    }
    progress(`Checking resumed file: ${file.name}`);
    await verify(file, upload);
    while (offset < file.size) {
      const before = now(), end = Math.min(file.size, offset + chunkSize);
      status(' · sending next part…');
      const ticker = setInterval(() => status(` · waiting for Spark (${Math.floor((now() - before) / 1000)}s)`), 1000);
      try {
        const result = await request(`${path}?offset=${offset}`, {
          method: 'PUT', body: file.slice(offset, end), headers: {'Content-Type': 'application/octet-stream'}
        });
        if (result.offset !== end) throw new Error('Upload offset changed. Reselect the file to verify and resume safely.');
        offset = result.offset;
        failures = 0;
        const seconds = (now() - before) / 1000;
        if (seconds < 2) chunkSize = Math.min(MiB, chunkSize * 2);
        else if (seconds > 8) chunkSize = Math.max(32 * KiB, Math.floor(chunkSize / 2));
      } catch (error) {
        if (!['AbortError', 'TypeError'].includes(error.name) || ++failures >= 3) {
          status(' · paused');
          throw new Error(`${error.message} Your confirmed upload is saved. Reselect the same file to resume.`);
        }
        clearInterval(ticker);
        status(` · connection interrupted; reconnecting (${failures}/2)…`);
        chunkSize = Math.max(32 * KiB, Math.floor(chunkSize / 2));
        await delay(1000 * failures);
        // The response may have been lost after a successful server write.
        // Verify saved bytes before resuming at the server's committed offset.
        try {
          const saved = await request(`/projects/${project}`);
          const current = saved.uploads.find(u => u.id === upload.id);
          if (!current) throw new Error('Upload no longer exists.');
          await verify(file, current);
          offset = current.offset;
        } catch (recoveryError) {
          status(' · paused');
          throw new Error(`${recoveryError.message} Reconnect and reselect the same file; confirmed parts are retained.`);
        }
      } finally { clearInterval(ticker); }
    }
    progress(`${file.name} · 100% saved on Spark · validating media and creating its preview…`);
  }
  return {transfer, verify};
})();
