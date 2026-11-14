"""Run with: python lan_clipboard.py"""

import hashlib
import json
import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock


DATA_FILE = Path(__file__).resolve().with_name("clipboard.txt")
MAX_BYTES = 256 * 1024
WRITE_LOCK = Lock()

PAGE = '''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>局域网剪贴板</title>
<style>
  :root { color-scheme: light dark; font-family: system-ui, sans-serif;
    --bg: #f0f4f2; --paper: #fff; --ink: #142820; --muted: #4b6057;
    --line: #c2d1c8; --accent: #176547; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #131d18; --paper: #1a2720; --ink: #edf6ef;
      --muted: #b1c7ba; --line: #586f62; --accent: #176547; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink); }
  main { max-width: 760px; margin: clamp(28px, 9vh, 90px) auto; padding: 0 20px; }
  h1 { margin: 0 0 8px; font-size: clamp(27px, 6vw, 42px); letter-spacing: -.025em; }
  p { color: var(--muted); margin: 0 0 26px; line-height: 1.55; }
  label { display: block; font-weight: 650; margin-bottom: 8px; }
  textarea { display: block; width: 100%; min-height: 200px; height: 42vh; max-height: 540px;
    resize: vertical; border: 1px solid var(--line); border-radius: 14px; padding: 15px;
    background: var(--paper); color: var(--ink); font: inherit; line-height: 1.55; }
  .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
  button { border: 1px solid var(--line); background: var(--paper); color: var(--ink);
    border-radius: 9px; min-height: 46px; padding: 8px 16px; font: inherit; cursor: pointer; }
  #save { color: white; background: var(--accent); border-color: var(--accent); font-weight: 650; }
  header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
  button:disabled { opacity: .55; cursor: default; }
  :focus-visible { outline: 3px solid #439b79; outline-offset: 2px; }
  #status { margin-top: 12px; }
</style>
</head>
<body>
<main>
  <header>
    <h1 data-text="title">局域网剪贴板</h1>
    <button id="language" type="button" lang="en">English</button>
  </header>
  <p data-text="intro">输入文字并保存，其他设备刷新后就能看到。</p>
  <label for="clip" data-text="label">共享文字</label>
  <textarea id="clip" placeholder="在这里输入或粘贴文字…" disabled></textarea>
  <div class="actions">
    <button id="save" data-text="save" disabled>保存</button>
    <button id="copy" data-text="copy" disabled>复制</button>
    <button id="refresh" data-text="refresh">刷新内容</button>
  </div>
  <p id="status" role="status">正在读取…</p>
</main>
<script>
  const clip = document.querySelector('#clip');
  const save = document.querySelector('#save');
  const copy = document.querySelector('#copy');
  const refresh = document.querySelector('#refresh');
  const status = document.querySelector('#status');
  const languageButton = document.querySelector('#language');
  const translations = {
    'zh-CN': {
      title: '局域网剪贴板',
      intro: '输入文字并保存，其他设备刷新后就能看到。',
      label: '共享文字',
      placeholder: '在这里输入或粘贴文字…',
      save: '保存',
      copy: '复制',
      refresh: '刷新内容',
      loading: '正在读取…',
      discard: '刷新会替换当前未保存的文字，继续吗？',
      loaded: '已读取最新内容',
      empty: '剪贴板为空',
      loadError: '读取失败，请点「刷新内容」重试。',
      conflict: '其他设备已更新内容。请先复制你输入的文字，再刷新查看。',
      tooLarge: '文字太长，最多可保存 256 KB。',
      saved: '已保存',
      saveError: '保存失败，请重试。',
      copied: '已复制',
      selected: '文字已选中，请使用浏览器的复制菜单。',
      synced: '内容已同步',
      unsaved: '有未保存的修改',
    },
    en: {
      title: 'LAN Clipboard',
      intro: 'Save your text, then refresh on another device to see it.',
      label: 'Shared text',
      placeholder: 'Type or paste text here…',
      save: 'Save',
      copy: 'Copy',
      refresh: 'Refresh',
      loading: 'Loading…',
      discard: 'Refreshing will replace your unsaved text. Continue?',
      loaded: 'Latest text loaded',
      empty: 'The clipboard is empty',
      loadError: 'Could not load text. Select Refresh to try again.',
      conflict: 'Another device updated the clipboard. Copy your edits before refreshing.',
      tooLarge: 'Text is too long. The limit is 256 KB.',
      saved: 'Saved',
      saveError: 'Could not save text. Try again.',
      copied: 'Copied',
      selected: 'Text selected. Use your browser’s Copy command.',
      synced: 'Text is up to date',
      unsaved: 'Unsaved changes',
    },
  };
  let revision = null;
  let savedText = '';
  let language = 'zh-CN';
  let statusKey = 'loading';

  function showStatus(key) {
    statusKey = key;
    status.textContent = translations[language][key];
  }

  function setLanguage(nextLanguage) {
    language = nextLanguage;
    const messages = translations[language];
    document.documentElement.lang = language;
    document.title = messages.title;
    document.querySelectorAll('[data-text]').forEach(element => {
      element.textContent = messages[element.dataset.text];
    });
    clip.placeholder = messages.placeholder;
    languageButton.lang = language === 'en' ? 'zh-CN' : 'en';
    languageButton.textContent = language === 'en' ? '中文' : 'English';
    showStatus(statusKey);
  }

  function updateButtons() {
    save.disabled = clip.disabled || clip.value === savedText;
    copy.disabled = clip.disabled || clip.value.length === 0;
  }

  function setBusy(busy) {
    clip.disabled = busy || revision === null;
    refresh.disabled = busy;
    updateButtons();
  }

  async function load() {
    if (clip.value !== savedText && !confirm(translations[language].discard)) return;
    setBusy(true);
    showStatus('loading');
    try {
      const response = await fetch('/clipboard', { cache: 'no-store' });
      if (!response.ok) throw new Error();
      const data = await response.json();
      revision = data.revision;
      clip.value = data.text;
      savedText = clip.value;
      showStatus(savedText ? 'loaded' : 'empty');
    } catch {
      showStatus('loadError');
    } finally {
      setBusy(false);
    }
  }

  async function store() {
    setBusy(true);
    try {
      const response = await fetch('/clipboard', {
        method: 'PUT',
        headers: { 'Content-Type': 'text/plain; charset=utf-8', 'If-Match': revision },
        body: clip.value,
      });
      if (response.status === 412) {
        showStatus('conflict');
      } else if (response.status === 413) {
        showStatus('tooLarge');
      } else if (response.ok) {
        revision = (await response.json()).revision;
        savedText = clip.value;
        showStatus('saved');
      } else {
        throw new Error();
      }
    } catch {
      showStatus('saveError');
    } finally {
      setBusy(false);
    }
  }

  copy.addEventListener('click', async () => {
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(clip.value);
      } else {
        clip.focus();
        clip.select();
        clip.setSelectionRange(0, clip.value.length);
        if (!document.execCommand('copy')) throw new Error();
      }
      showStatus('copied');
    } catch {
      clip.focus();
      clip.select();
      clip.setSelectionRange(0, clip.value.length);
      showStatus('selected');
    }
  });
  clip.addEventListener('input', () => {
    updateButtons();
    showStatus(clip.value === savedText ? 'synced' : 'unsaved');
  });
  languageButton.addEventListener('click', () => {
    const nextLanguage = language === 'en' ? 'zh-CN' : 'en';
    setLanguage(nextLanguage);
    try {
      localStorage.setItem('clipboard-language', nextLanguage);
    } catch {
      // The current page can still switch languages when browser storage is blocked.
    }
  });
  save.addEventListener('click', store);
  refresh.addEventListener('click', load);
  try {
    if (localStorage.getItem('clipboard-language') === 'en') setLanguage('en');
  } catch {
    // Use the default language when browser storage is blocked.
  }
  load();
</script>
</body>
</html>'''.encode("utf-8")


def read_clipboard():
    try:
        return DATA_FILE.read_bytes()
    except FileNotFoundError:
        return b""


def revision(data):
    return '"' + hashlib.sha256(data).hexdigest() + '"'


class ClipboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def setup(self):
        self.request.settimeout(10)
        super().setup()

    def reply(self, status, body=b"", content_type="text/plain; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def reply_json(self, **data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.reply(200, body, "application/json; charset=utf-8")

    def do_GET(self):
        if self.path == "/":
            self.reply(200, PAGE, "text/html; charset=utf-8")
        elif self.path == "/clipboard":
            try:
                data = read_clipboard()
                clipboard_text = data.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                self.reply(500)
                return
            self.reply_json(text=clipboard_text, revision=revision(data))
        else:
            self.reply(404)

    def do_PUT(self):
        if self.path != "/clipboard":
            self.reply(404)
            return
        origin = self.headers.get("Origin")
        if origin and origin != f'http://{self.headers.get("Host")}':
            self.reply(403)
            return
        try:
            size = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            size = -1
        if size < 0 or size > MAX_BYTES:
            self.reply(411 if size < 0 else 413)
            return
        data = self.rfile.read(size)
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            self.reply(400)
            return
        if len(data) != size:
            self.reply(400)
            return
        try:
            with WRITE_LOCK:
                if self.headers.get("If-Match") != revision(read_clipboard()):
                    self.reply(412)
                    return
                temporary = DATA_FILE.with_suffix(".tmp")
                temporary.write_bytes(data)
                os.replace(temporary, DATA_FILE)
        except OSError:
            self.reply(500)
            return
        self.reply_json(revision=revision(data))


class ClipboardServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.allow_reuse_address = False
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


if __name__ == "__main__":
    try:
        server = ClipboardServer(("0.0.0.0", 8000), ClipboardHandler)
    except OSError as error:
        raise SystemExit(f"Could not listen on port 8000: {error}") from None
    with server:
        print("Clipboard running at http://127.0.0.1:8000", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
