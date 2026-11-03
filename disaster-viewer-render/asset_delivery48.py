"""Exact-byte gzip delivery; bounded disk cache, no extra packages or API changes."""
import gzip
import hashlib
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from threading import Lock, Semaphore
from flask import request, send_file

_locks = [Lock() for _ in range(8)]
_compressors = Semaphore(2)
_prune_lock = Lock()
TEXT_SUFFIXES = {'.js', '.css', '.json', '.geojson', '.svg', '.txt'}
CACHE_BYTES = 64 * 1024 * 1024

@lru_cache(maxsize=128)
def _digest(name, modified, size):
    digest = hashlib.sha256()
    with open(name, 'rb') as stream:
        for chunk in iter(lambda: stream.read(512 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def _prune(directory, keep):
    files = sorted(directory.glob('*.gz'), key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in files)
    for path in files:
        if total <= CACHE_BYTES:
            break
        if path == keep or path.is_symlink() or path.resolve().parent != directory.resolve():
            continue
        try:
            size = path.stat().st_size
            path.unlink()
            total -= size
        except OSError:
            pass  # A Windows response may still have the file open; retry later.

def compressed_asset(source, directory):
    stat = source.stat()
    digest = _digest(str(source), stat.st_mtime_ns, stat.st_size)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (digest + '.gz')
    with _locks[int(digest[:8], 16) % len(_locks)]:
        if not target.is_file():
            temporary = None
            try:
                with _compressors, tempfile.NamedTemporaryFile(dir=directory, suffix='.tmp', delete=False) as output:
                    temporary = Path(output.name)
                    with source.open('rb') as stream, gzip.GzipFile(filename='', fileobj=output, mode='wb', compresslevel=3, mtime=0) as zipped:
                        for chunk in iter(lambda: stream.read(512 * 1024), b''):
                            zipped.write(chunk)
                after = source.stat()
                if (after.st_mtime_ns, after.st_size) != (stat.st_mtime_ns, stat.st_size):
                    raise OSError('Asset changed during compression')
                os.replace(temporary, target)
                temporary = None
                with _prune_lock:
                    _prune(directory, target)
            finally:
                if temporary is not None and temporary.exists():
                    temporary.unlink()
    return target, digest

def install(app):
    @app.after_request
    def deliver(response):
        # Runs only AFTER origin authentication and the original route succeeded.
        static = request.endpoint == 'static'
        api = request.path.startswith('/api/') and response.is_json
        if not (static or api):
            return response
        response.vary.add('Accept-Encoding')
        if response.status_code != 200 or request.method not in ('GET', 'HEAD') or request.headers.get('Range') or response.headers.get('Content-Encoding') or request.accept_encodings['gzip'] <= 0:
            return response
        if static:
            source = (Path(app.static_folder) / request.view_args['filename']).resolve()
            if not source.is_relative_to(Path(app.static_folder).resolve()) or source.suffix not in TEXT_SUFFIXES:
                return response
            try:
                if source.stat().st_size < 2048:
                    return response
                cached, digest = compressed_asset(source, Path(app.instance_path) / 'asset-cache48')
                encoded = send_file(cached, mimetype=response.mimetype, conditional=True, etag=digest + '-gzip')
            except OSError:
                return response  # Read-only installs still serve the original bytes.
            for name, value in response.headers.items():
                if name.lower() not in {'content-length', 'content-encoding', 'etag', 'last-modified', 'content-range'}:
                    encoded.headers[name] = value
            encoded.headers['Content-Encoding'] = 'gzip'
            encoded.vary.add('Accept-Encoding')
            response.close()
            return encoded
        if not response.is_streamed:
            body = response.get_data()
            if 2048 <= len(body) <= 4 * 1024 * 1024:
                encoded = gzip.compress(body, compresslevel=3, mtime=0)
                if len(encoded) < len(body) * .95:
                    response.set_data(encoded)
                    response.headers['Content-Encoding'] = 'gzip'
        return response
