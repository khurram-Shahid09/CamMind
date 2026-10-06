"""A tiny RTSP server for probe tests: answers DESCRIBE like a camera would."""

import hashlib
import re
import socket
import socketserver
import threading
from dataclasses import dataclass, field

H264_SDP = (
    "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=Camera\r\nt=0 0\r\n"
    "m=video 0 RTP/AVP 96\r\na=rtpmap:96 H264/90000\r\na=framerate:25\r\n"
    "m=audio 0 RTP/AVP 0\r\na=rtpmap:0 PCMU/8000\r\n"
)
MJPEG_SDP = "v=0\r\ns=Camera\r\nm=video 0 RTP/AVP 26\r\na=rtpmap:26 JPEG/90000\r\n"
AUDIO_ONLY_SDP = "v=0\r\ns=Mic\r\nm=audio 0 RTP/AVP 0\r\na=rtpmap:0 PCMU/8000\r\n"


@dataclass
class Behaviour:
    path: str = "/live"
    sdp: str = H264_SDP
    auth: str = ""  # "", "basic" or "digest"
    user: str = "viewer"
    password: str = "s3cret pass"
    realm: str = "IPCAM"
    nonce: str = "abc123"
    silent: bool = False  # accept the connection and never answer
    requests: list[str] = field(default_factory=list)


def _md5(text: str) -> str:
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        b: Behaviour = self.server.behaviour  # type: ignore[attr-defined]
        lines = []
        while True:
            line = self.rfile.readline().decode()
            if line in ("\r\n", "\n", ""):
                break
            lines.append(line.strip())
        if not lines:
            return
        b.requests.append("\n".join(lines))
        if b.silent:
            threading.Event().wait(3)
            return
        method, url, _ = lines[0].split(" ")
        headers = {k.lower(): v.strip() for k, _, v in (h.partition(":") for h in lines[1:])}
        cseq = headers.get("cseq", "0")
        if b.auth and not self._authorized(b, method, url, headers.get("authorization", "")):
            challenge = (
                f'Digest realm="{b.realm}", nonce="{b.nonce}"'
                if b.auth == "digest"
                else f'Basic realm="{b.realm}"'
            )
            self._send("401 Unauthorized", cseq, [f"WWW-Authenticate: {challenge}"])
            return
        if not url.endswith(b.path):
            self._send("404 Not Found", cseq)
            return
        self._send("200 OK", cseq, ["Content-Type: application/sdp"], b.sdp)

    def _authorized(self, b: Behaviour, method: str, url: str, header: str) -> bool:
        if b.auth == "basic":
            import base64

            return header == "Basic " + base64.b64encode(f"{b.user}:{b.password}".encode()).decode()
        params = dict(re.findall(r'(\w+)="([^"]*)"', header))
        if not params:
            return False
        ha1 = _md5(f"{b.user}:{b.realm}:{b.password}")
        expected = _md5(f"{ha1}:{b.nonce}:{_md5(f'{method}:{params.get("uri", "")}')}")
        return params.get("username") == b.user and params.get("response") == expected

    def _send(
        self, status: str, cseq: str, headers: list[str] | None = None, body: str = ""
    ) -> None:
        lines = [f"RTSP/1.0 {status}", f"CSeq: {cseq}", *(headers or [])]
        if body:
            lines.append(f"Content-Length: {len(body.encode())}")
        self.wfile.write(("\r\n".join(lines) + "\r\n\r\n" + body).encode())


class FakeCamera:
    def __init__(self, behaviour: Behaviour) -> None:
        self.behaviour = behaviour
        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Handler)
        self.server.daemon_threads = True
        self.server.behaviour = behaviour  # type: ignore[attr-defined]
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
