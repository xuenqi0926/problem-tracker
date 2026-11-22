# -*- coding: utf-8 -*-
"""
刷题记录系统 - SQLite 数据库后端
纯 Python 标准库实现，零第三方依赖。
启动: python server.py  然后浏览器访问 http://127.0.0.1:8765
"""
import json
import os
import sqlite3
import time
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'problems.db')
HTML_PATH = os.path.join(BASE_DIR, 'problem-tracker.html')
HOST = '127.0.0.1'
PORT = 8765


# ---------- 数据库层 ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript('''
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS problems (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        name       TEXT NOT NULL,
        difficulty TEXT NOT NULL,
        created    INTEGER NOT NULL,
        url        TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS tags (
        id   INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    );
    CREATE TABLE IF NOT EXISTS problem_tags (
        problem_id INTEGER NOT NULL,
        tag_id     INTEGER NOT NULL,
        PRIMARY KEY (problem_id, tag_id),
        FOREIGN KEY (problem_id) REFERENCES problems(id) ON DELETE CASCADE,
        FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_pt_tag ON problem_tags(tag_id);
    CREATE INDEX IF NOT EXISTS idx_problems_created ON problems(created);
    ''')
    # 兼容旧库：若 problems 表还没有 url 列则补上
    cols = [r[1] for r in conn.execute('PRAGMA table_info(problems)').fetchall()]
    if 'url' not in cols:
        conn.execute("ALTER TABLE problems ADD COLUMN url TEXT NOT NULL DEFAULT ''")
    conn.commit()
    conn.close()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def _tags_of(conn, problem_id):
    rows = conn.execute('''
        SELECT t.name FROM tags t
        JOIN problem_tags pt ON t.id = pt.tag_id
        WHERE pt.problem_id = ? ORDER BY t.name
    ''', (problem_id,)).fetchall()
    return [r[0] for r in rows]


def _set_tags(conn, problem_id, tags):
    conn.execute('DELETE FROM problem_tags WHERE problem_id = ?', (problem_id,))
    for name in tags:
        name = str(name).strip()
        if not name:
            continue
        conn.execute('INSERT OR IGNORE INTO tags(name) VALUES (?)', (name,))
        tag_id = conn.execute('SELECT id FROM tags WHERE name = ?', (name,)).fetchone()[0]
        conn.execute('INSERT OR IGNORE INTO problem_tags(problem_id, tag_id) VALUES (?, ?)',
                     (problem_id, tag_id))


def _clean_orphan_tags(conn):
    conn.execute('''DELETE FROM tags WHERE id NOT IN
                    (SELECT tag_id FROM problem_tags)''')


def get_all_problems():
    conn = db()
    rows = conn.execute('SELECT id, name, difficulty, created, url FROM problems ORDER BY created DESC').fetchall()
    out = []
    for r in rows:
        out.append({
            'id': r['id'], 'name': r['name'], 'difficulty': r['difficulty'],
            'tags': _tags_of(conn, r['id']), 'created': r['created'], 'url': r['url'] or ''
        })
    conn.close()
    return out


def add_problem(name, difficulty, tags, url=''):
    conn = db()
    cur = conn.execute('INSERT INTO problems(name, difficulty, created, url) VALUES (?, ?, ?, ?)',
                       (name, difficulty, int(time.time() * 1000), url or ''))
    _set_tags(conn, cur.lastrowid, tags)
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_problem(pid, name, difficulty, tags, url=''):
    conn = db()
    exists = conn.execute('SELECT 1 FROM problems WHERE id = ?', (pid,)).fetchone()
    if not exists:
        conn.close()
        return False
    conn.execute('UPDATE problems SET name = ?, difficulty = ?, url = ? WHERE id = ?',
                 (name, difficulty, url or '', pid))
    _set_tags(conn, pid, tags)
    _clean_orphan_tags(conn)
    conn.commit()
    conn.close()
    return True


def delete_problem(pid):
    conn = db()
    conn.execute('DELETE FROM problems WHERE id = ?', (pid,))
    _clean_orphan_tags(conn)
    conn.commit()
    conn.close()
    return True


def clear_all():
    conn = db()
    conn.execute('DELETE FROM problem_tags')
    conn.execute('DELETE FROM tags')
    conn.execute('DELETE FROM problems')
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('problems','tags')")
    conn.commit()
    conn.close()


def import_problems(items):
    conn = db()
    n = 0
    for it in items:
        name = str(it.get('name', '')).strip()
        if not name:
            continue
        diff = it.get('difficulty') or '入门'
        created = it.get('created') or int(time.time() * 1000)
        url = it.get('url') or ''
        cur = conn.execute('INSERT INTO problems(name, difficulty, created, url) VALUES (?, ?, ?, ?)',
                           (name, diff, int(created), url))
        _set_tags(conn, cur.lastrowid, it.get('tags') or [])
        n += 1
    conn.commit()
    conn.close()
    return n


def get_stats():
    conn = db()
    n_prob = conn.execute('SELECT COUNT(*) FROM problems').fetchone()[0]
    n_tag = conn.execute('SELECT COUNT(*) FROM tags').fetchone()[0]
    diff = {r['difficulty']: r['cnt'] for r in conn.execute(
        'SELECT difficulty, COUNT(*) AS cnt FROM problems GROUP BY difficulty').fetchall()}
    conn.close()
    size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    return {
        'problems': n_prob, 'tags': n_tag, 'byDifficulty': diff,
        'dbPath': DB_PATH, 'dbSize': size
    }


# ---------- HTTP 层 ----------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print('[%s] %s' % (self.log_date_time_string(), fmt % args))

    def _send(self, code, body, ctype='application/json; charset=utf-8'):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        elif isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _json_ok(self, data):
        self._send(200, {'ok': True, 'data': data})

    def _json_err(self, code, msg):
        self._send(code, {'ok': False, 'error': msg})

    def _body(self):
        length = int(self.headers.get('Content-Length', 0))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode('utf-8'))
        except Exception:
            return {}

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == '/':
                with open(HTML_PATH, 'rb') as f:
                    self._send(200, f.read(), 'text/html; charset=utf-8')
            elif path == '/api/problems':
                self._json_ok(get_all_problems())
            elif path == '/api/stats':
                self._json_ok(get_stats())
            elif path == '/api/export':
                self._json_ok(get_all_problems())
            else:
                self._json_err(404, 'Not found')
        except Exception as e:
            self._json_err(500, str(e))

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self._body()
            if path == '/api/problems':
                name = str(body.get('name', '')).strip()
                if not name:
                    return self._json_err(400, '题名不能为空')
                pid = add_problem(name, body.get('difficulty') or '入门',
                                  body.get('tags') or [], body.get('url') or '')
                self._json_ok({'id': pid})
            elif path == '/api/import':
                items = body.get('problems') or []
                n = import_problems(items)
                self._json_ok({'imported': n})
            else:
                self._json_err(404, 'Not found')
        except Exception as e:
            self._json_err(500, str(e))

    def do_PUT(self):
        path = urlparse(self.path).path
        try:
            if not path.startswith('/api/problems/'):
                return self._json_err(404, 'Not found')
            pid = int(path.rsplit('/', 1)[1])
            body = self._body()
            name = str(body.get('name', '')).strip()
            if not name:
                return self._json_err(400, '题名不能为空')
            ok = update_problem(pid, name, body.get('difficulty') or '入门',
                                body.get('tags') or [], body.get('url') or '')
            self._json_ok({'updated': ok})
        except Exception as e:
            self._json_err(500, str(e))

    def do_DELETE(self):
        path = urlparse(self.path).path
        try:
            if path == '/api/problems':
                clear_all()
                return self._json_ok({'cleared': True})
            if path.startswith('/api/problems/'):
                pid = int(path.rsplit('/', 1)[1])
                delete_problem(pid)
                return self._json_ok({'deleted': pid})
            self._json_err(404, 'Not found')
        except Exception as e:
            self._json_err(500, str(e))


if __name__ == '__main__':
    init_db()
    print('=' * 52)
    print('  刷题记录系统  |  SQLite 数据库后端已启动')
    print('  数据库文件: %s' % DB_PATH)
    print('  访问地址  : http://%s:%d' % (HOST, PORT))
    print('  关闭服务  : 在此窗口按 Ctrl+C')
    print('=' * 52)
    try:
        webbrowser.open('http://%s:%d' % (HOST, PORT))
    except Exception:
        pass
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务已停止。')
        server.shutdown()
