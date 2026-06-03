#!/usr/bin/env python3
"""
Hermes Dashboard Proxy Server v2
Serves custom dashboard HTML + proxies HTTP API + WebSocket PTY to Hermes backend.
Supports target switching between Hangzhou and Tokyo Hermes instances.
Hangzhou target spawns hermes CLI locally (fast, no TUI overhead).
Tokyo target forwards PTY to Tokyo dashboard via SSH tunnel.
"""
import os, re, sys, json, time, threading, socket, select, struct, hashlib, base64
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError
from socketserver import ThreadingMixIn

_HERMES_BIN = "/root/.local/bin/hermes"
_HERMES_ENV = os.environ.copy()
_HERMES_ENV.setdefault("PATH", "/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
_HERMES_ENV.setdefault("HOME", "/root")
_HERMES_ENV.setdefault("TERM", "xterm-256color")

# Try to import ptyprocess for local PTY support
try:
    import ptyprocess
    _PTYPROCESS_OK = True
except ImportError:
    _PTYPROCESS_OK = False

HZ_BACKEND = os.environ.get("HZ_BACKEND", "http://127.0.0.1:9119")
TOKYO_BACKEND = os.environ.get("TOKYO_BACKEND", "http://127.0.0.1:8644")
PROXY_PORT = int(os.environ.get("PROXY_PORT", "8642"))
STATIC_DIR = os.environ.get("STATIC_DIR", os.path.dirname(os.path.abspath(__file__)))

_target = os.environ.get("DEFAULT_TARGET", "hangzhou")
_session_token = None
_token_lock = threading.Lock()
_token_refresh_interval = 300

def get_backend_url():
    if _target == "tokyo":
        return TOKYO_BACKEND
    return HZ_BACKEND

def get_backend_host():
    url = get_backend_url()
    return url.replace("http://", "").replace("https://", "")

def get_pty_target():
    if _target == "tokyo":
        return ('127.0.0.1', 8644)  # SSH tunnel to Tokyo dashboard
    return ('127.0.0.1', 9119)  # Hangzhou Hermes dashboard

def fetch_token():
    global _session_token
    try:
        url = f"{get_backend_url()}/"
        req = Request(url)
        with urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")
        m = re.search(r'__HERMES_SESSION_TOKEN__\s*=\s*["\']([^"\']+)["\']', html)
        if m:
            with _token_lock:
                _session_token = m.group(1)
            return _session_token
    except Exception as e:
        print(f"[proxy] Token fetch failed: {e}")
    return None

def refresh_token_loop():
    while True:
        token = fetch_token()
        if token:
            print(f"[proxy] Session token refreshed ({_target}): {token[:16]}...")
        else:
            print(f"[proxy] Waiting for dashboard ({_target})...")
        time.sleep(_token_refresh_interval)

class ProxyHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/token":
            self.send_json({"token": _session_token})
        elif self.path == "/api/target":
            self.send_json({"target": _target, "backend": get_backend_url()})
        elif self.path == "/api/proxy-status":
            self.send_json({
                "target": _target,
                "backend": get_backend_url(),
                "token_ok": _session_token is not None,
                "mode": "production"
            })
        elif self.path.startswith("/api/pty") and self.headers.get("Upgrade", "").lower() == "websocket":
            if _target == "hangzhou":
                self.handle_local_pty()
            else:
                self.proxy_websocket()
        elif self.path.startswith("/api/") and self.headers.get("Upgrade", "").lower() == "websocket":
            self.proxy_websocket()
        elif self.path.startswith("/api/"):
            self.proxy_api("GET")
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/target":
            self.set_target()
        elif self.path.startswith("/api/"):
            self.proxy_api("POST")
        else:
            self.send_error(405)

    def do_PUT(self):
        if self.path.startswith("/api/"):
            self.proxy_api("PUT")
        else:
            self.send_error(405)

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            self.proxy_api("DELETE")
        else:
            self.send_error(405)

    def set_target(self):
        global _target
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}
        new_target = body.get("target", "hangzhou")
        if new_target not in ("hangzhou", "tokyo"):
            self.send_json({"ok": False, "error": "invalid target"})
            return
        _target = new_target
        fetch_token()
        self.send_json({"ok": True, "target": _target, "backend": get_backend_url()})
        print(f"[proxy] Target switched to {_target}")

    def proxy_api(self, method):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None
        target = f"{get_backend_url()}{self.path}"
        headers = {
            "Content-Type": self.headers.get("Content-Type", "application/json"),
            "X-Hermes-Session-Token": _session_token or "",
        }
        req = Request(target, data=body, headers=headers, method=method)
        try:
            with urlopen(req, timeout=30) as resp:
                data = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in ("content-type", "content-length", "cache-control"):
                        self.send_header(k, v)
                self.end_headers()
                self.wfile.write(data)
        except URLError as e:
            if hasattr(e, 'code') and e.code:
                self.send_response(e.code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(e.read() if hasattr(e, 'read') else b'{}')
            else:
                self.send_error(502, f"Proxy error: {e.reason}")
        except Exception as e:
            self.send_error(502, f"Proxy error: {str(e)}")

    def proxy_websocket(self):
        addr, host = get_pty_target(), get_backend_host()
        path = self.path
        backend = None
        try:
            backend = socket.create_connection(addr, timeout=10)
            req = f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
            for k, v in self.headers.items():
                excluded = ('host', 'content-length', 'origin', 'sec-fetch-site', 'sec-fetch-mode', 'sec-fetch-dest')
                if k.lower() not in excluded:
                    req += f"{k}: {v}\r\n"
            req += "\r\n"
            backend.sendall(req.encode())
            resp = b""
            while b"\r\n\r\n" not in resp:
                chunk = backend.recv(4096)
                if not chunk:
                    break
                resp += chunk
            client = self.request
            client.sendall(resp)
            self._forward_bidirectional(client, backend)
        except Exception as e:
            print(f"[proxy] WebSocket error: {e}")
            try:
                self.send_error(502, str(e))
            except:
                pass
        finally:
            if backend:
                try:
                    backend.close()
                except:
                    pass

    def _forward_bidirectional(self, client, backend):
        sockets = [client, backend]
        while True:
            try:
                readable, _, _ = select.select(sockets, [], [], 30)
                if not readable:
                    continue
                for s in readable:
                    data = s.recv(65536)
                    if not data:
                        return
                    if s is client:
                        print(f"[proxy] WS→backend: {len(data)} bytes", flush=True)
                        backend.sendall(data)
                    else:
                        client.sendall(data)
            except (OSError, ConnectionError):
                return

    def handle_local_pty(self):
        """Spawn hermes CLI locally in a PTY and bridge with the WebSocket client.
        Avoids the Node.js TUI overhead — runs the fast Python CLI directly.
        """
        from ptyprocess import PtyProcess

        cols, rows = 80, 24
        client = self.request
        print(f"[proxy-pty] Handling local PTY for Hangzhou", flush=True)

        # --- WebSocket handshake ---
        key = self.headers.get("Sec-WebSocket-Key", "")
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-5AB5DC11B735").encode()).digest()).decode()
        resp = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n"
            "\r\n"
        )
        client.sendall(resp.encode())
        print(f"[proxy-pty] 101 handshake sent", flush=True)

        # --- Spawn hermes CLI ---
        try:
            bridge = PtyProcess.spawn([_HERMES_BIN], env=_HERMES_ENV, dimensions=(rows, cols))
            print(f"[proxy-pty] Hermes CLI spawned (pid={bridge.pid})", flush=True)
        except Exception as e:
            print(f"[proxy-pty] Failed to spawn hermes: {e}", flush=True)
            return

        # --- PTY → WS pump ---
        def pump_pty_to_ws(bridge, client):
            while True:
                try:
                    data = os.read(bridge.fd, 65536)
                    if not data:
                        print(f"[proxy-pty] PTY EOF", flush=True)
                        break
                except OSError as e:
                    print(f"[proxy-pty] PTY read error: {e}", flush=True)
                    break
                try:
                    frame = self._make_ws_frame(data, 0x2)
                    client.sendall(frame)
                except Exception as e:
                    print(f"[proxy-pty] WS send error: {e}", flush=True)
                    break

        pump_thread = threading.Thread(target=pump_pty_to_ws, args=(bridge, client), daemon=True)
        pump_thread.start()

        # --- WS → PTY reader ---
        buf = b""
        try:
            while True:
                ready, _, _ = select.select([client], [], [], 0.5)
                if not ready:
                    if not pump_thread.is_alive():
                        break
                    continue
                chunk = client.recv(65536)
                if not chunk:
                    print(f"[proxy-pty] Client disconnected", flush=True)
                    break
                buf += chunk
                while True:
                    payload, used = self._read_one_ws_frame(buf)
                    if payload is None or used == 0:
                        break
                    buf = buf[used:]
                    if isinstance(payload, bytes) and payload.startswith(b"\x1b[RESIZE:"):
                        try:
                            _, rest = payload.split(b":", 1)
                            c, r = rest.split(b";")
                            bridge.setwinsize(int(r), int(c))
                        except: pass
                    elif isinstance(payload, (bytes, str)):
                        data = payload if isinstance(payload, bytes) else payload.encode()
                        if data == b"\x03":
                            bridge.write(b"\x03")
                        else:
                            bridge.write(data)
        except Exception as e:
            print(f"[proxy-pty] Error in WS→PTY loop: {e}", flush=True)
        finally:
            print(f"[proxy-pty] Cleaning up", flush=True)
            try: bridge.close()
            except: pass

    def _make_ws_frame(self, data, opcode):
        frame = bytearray()
        frame.append(0x80 | opcode)
        length = len(data)
        if length < 126:
            frame.append(length)
        elif length < 65536:
            frame.append(126)
            frame.extend(struct.pack(">H", length))
        else:
            frame.append(127)
            frame.extend(struct.pack(">Q", length))
        frame.extend(data)
        return bytes(frame)

    def _read_one_ws_frame(self, buf):
        """Try to read one complete WebSocket frame from buffer.
        Returns (payload, bytes_consumed) or (None, 0) if incomplete.
        """
        if len(buf) < 2:
            return None, 0
        b1, b2 = buf[0], buf[1]
        opcode = b1 & 0x0F
        masked = (b2 & 0x80) != 0
        length = b2 & 0x7F
        header_len = 2
        if length == 126:
            header_len = 4
        elif length == 127:
            header_len = 10
        if masked:
            header_len += 4
        if len(buf) < header_len:
            return None, 0
        offset = 2
        if length == 126:
            length = struct.unpack(">H", buf[2:4])[0]
            offset = 4
        elif length == 127:
            length = struct.unpack(">Q", buf[2:10])[0]
            offset = 10
        if masked:
            mask = buf[offset:offset+4]
            offset += 4
        if len(buf) < offset + length:
            return None, 0
        payload = buf[offset:offset+length]
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        total = offset + length
        if opcode == 0x8:  # close
            return None, total
        if opcode == 0x9:  # ping
            return None, total
        return payload, total

    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        try:
            print(f"[proxy] {args[0]} {args[1]}") if len(args) >= 2 else print(f"[proxy] {args}")
        except:
            pass

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def main():
    os.chdir(STATIC_DIR)
    print(f"[proxy] Hermes Dashboard Proxy v2")
    print(f"[proxy] Listening on 127.0.0.1:{PROXY_PORT}")
    print(f"[proxy] Default target: {_target}")
    print(f"[proxy] HZ backend: {HZ_BACKEND}")
    print(f"[proxy] Tokyo backend: {TOKYO_BACKEND}")
    print(f"[proxy] Static dir: {STATIC_DIR}")

    token = fetch_token()
    if token:
        print(f"[proxy] Initial token: {token[:16]}...")
    else:
        print("[proxy] WARNING: No session token yet")

    t = threading.Thread(target=refresh_token_loop, daemon=True)
    t.start()

    server = ThreadedHTTPServer(("127.0.0.1", PROXY_PORT), ProxyHandler)
    print(f"[proxy] Ready on http://127.0.0.1:{PROXY_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[proxy] Shutting down...")
        server.server_close()

if __name__ == "__main__":
    main()
