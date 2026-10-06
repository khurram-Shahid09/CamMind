"""Camera URLs: validate, mask, and check a camera with one RTSP DESCRIBE.

``parse`` refuses anything that isn't an RTSP URL to a normal network host: no other schemes,
no loopback, link-local (cloud metadata) or multicast addresses (docs/14, "SSRF via the camera
URL field").

``probe`` connects, sends DESCRIBE (answering Basic or Digest auth), and reads the SDP to
learn the video codec. Its error codes are the ones the dashboard explains to people
(docs/12-api-spec.md, ``POST /cameras/test``): ``unreachable``, ``timeout``, ``auth_failed``,
``not_found``, ``unsupported_codec``, ``rtsp_error``.
"""

import base64
import hashlib
import ipaddress
import os
import re
import socket
import ssl
from dataclasses import dataclass, field
from urllib.parse import quote, unquote, urlsplit

from django.conf import settings

SCHEMES = {"rtsp": 554, "rtsps": 322}
SUPPORTED_CODECS = {"H264": "H264", "H265": "H265", "HEVC": "H265"}
BLOCKED_HOSTNAMES = {"localhost", "metadata", "metadata.google.internal"}
# Factory logins that should never stay on a camera (docs/14, "default passwords").
DEFAULT_CREDENTIALS = {
    ("admin", ""),
    ("admin", "admin"),
    ("admin", "1234"),
    ("admin", "12345"),
    ("admin", "123456"),
    ("admin", "password"),
    ("root", "pass"),
    ("root", "root"),
    ("888888", "888888"),
    ("666666", "666666"),
}
MASK = "•••"
MAX_RESPONSE_BYTES = 64 * 1024


class CameraUrlError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.code = "invalid_url"
        self.message = message


@dataclass(frozen=True)
class CameraUrl:
    scheme: str
    host: str
    port: int
    path: str  # path and query, e.g. "/Streaming/Channels/101?transport=tcp"
    username: str = ""
    password: str = ""

    @property
    def public(self) -> str:
        """The URL without credentials, as sent in the RTSP request line."""
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"{self.scheme}://{host}:{self.port}{self.path}"

    @property
    def uses_default_password(self) -> bool:
        return bool(self.username) and (self.username, self.password) in DEFAULT_CREDENTIALS


def parse(url: str) -> CameraUrl:
    url = url.strip()
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise CameraUrlError("This isn't a valid URL.") from exc
    scheme = parts.scheme.lower()
    if scheme not in SCHEMES:
        raise CameraUrlError("Camera URLs start with rtsp:// (or rtsps://).")
    host = (parts.hostname or "").lower()
    if not host:
        raise CameraUrlError("The URL has no camera address.")
    _check_host(host)
    path = parts.path or "/"
    if parts.query:
        path += f"?{parts.query}"
    return CameraUrl(
        scheme=scheme,
        host=host,
        port=port or SCHEMES[scheme],
        path=path,
        username=unquote(parts.username or ""),
        password=unquote(parts.password or ""),
    )


def _check_host(host: str) -> None:
    if host in BLOCKED_HOSTNAMES or host.endswith(".localhost"):
        raise CameraUrlError("Use the camera's network address, not this machine's.")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return  # a host name: resolved on the camera network
    if ip.is_loopback or ip.is_unspecified:
        raise CameraUrlError("Use the camera's network address, not this machine's.")
    if ip.is_link_local or ip.is_multicast or ip.is_reserved:
        raise CameraUrlError("This address can't be a camera.")


def mask(url: str) -> str:
    """``rtsp://admin:•••@192.168.1.20:554/...``: never shows a password, even in a bad URL."""
    try:
        parts = urlsplit(url.strip())
        parts.port  # noqa: B018  # raises on a malformed port
    except ValueError:
        return MASK
    if parts.password is None:
        return url.strip()
    user = quote(unquote(parts.username or ""), safe="")
    netloc = f"{user}:{MASK}@{parts.netloc.rsplit('@', 1)[1]}"
    return parts._replace(netloc=netloc).geturl()


# --- probe ---


@dataclass
class ProbeResult:
    ok: bool
    error_code: str = ""
    message: str = ""
    codec: str = ""
    fps: float | None = None
    warnings: list[str] = field(default_factory=list)


class _Failure(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def probe(url: str, timeout: float | None = None) -> ProbeResult:
    """Check that ``url`` serves video CamMind can use. Never raises for network problems."""
    try:
        camera = parse(url)
    except CameraUrlError as exc:
        return ProbeResult(ok=False, error_code=exc.code, message=exc.message)
    warnings = []
    if camera.uses_default_password:
        warnings.append("This camera uses a factory password. Change it in the camera's settings.")
    try:
        sdp = _describe(camera, timeout or settings.CAMERA_PROBE_TIMEOUT_S)
        codec, fps = _video_from_sdp(sdp)
    except _Failure as exc:
        return ProbeResult(ok=False, error_code=exc.code, message=exc.message, warnings=warnings)
    return ProbeResult(ok=True, codec=codec, fps=fps, warnings=warnings)


def _address(camera: CameraUrl) -> tuple[str, int]:
    """Where to connect. CAMERA_HOST_ALIASES lets a developer's machine reach test cameras
    that only have a name inside Docker (``mediamtx:8554`` -> ``localhost:8654``)."""
    alias = settings.CAMERA_HOST_ALIASES.get(f"{camera.host}:{camera.port}")
    if alias:
        host, _, port = alias.rpartition(":")
        return host, int(port)
    return camera.host, camera.port


def _connect(camera: CameraUrl, timeout: float) -> socket.socket:
    host, port = _address(camera)
    where = f"{camera.host}:{camera.port}"
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except TimeoutError as exc:
        raise _Failure("timeout", f"No answer from {where}. Is the camera on?") from exc
    except socket.gaierror as exc:
        raise _Failure("unreachable", f"Can't find {camera.host} on the network.") from exc
    except ConnectionRefusedError as exc:
        raise _Failure(
            "unreachable", f"{where} refused the connection. Check the port (usually 554)."
        ) from exc
    except OSError as exc:
        raise _Failure("unreachable", f"Can't reach {where}.") from exc
    if camera.scheme == "rtsps":
        # Cameras use self-signed certificates; the TLS here protects the password in transit.
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE  # noqa: S503
        try:
            sock = context.wrap_socket(sock, server_hostname=camera.host)
        except (ssl.SSLError, OSError) as exc:
            sock.close()
            raise _Failure("unreachable", f"TLS handshake with {where} failed.") from exc
    return sock


def _exchange(
    camera: CameraUrl, timeout: float, cseq: int, authorization: str | None
) -> tuple[int, dict[str, list[str]], str]:
    # A fresh connection per request: many cameras hang up after a 401.
    sock = _connect(camera, timeout)
    try:
        return _request(sock, camera, cseq, authorization)
    except TimeoutError as exc:
        raise _Failure("timeout", "The camera stopped answering.") from exc
    except OSError as exc:
        raise _Failure("unreachable", "The connection to the camera dropped.") from exc
    finally:
        sock.close()


def _describe(camera: CameraUrl, timeout: float) -> str:
    status, headers, body = _exchange(camera, timeout, 1, None)
    if status == 401 and camera.username:
        authorization = _authorization(camera, headers.get("www-authenticate", []))
        status, headers, body = _exchange(camera, timeout, 2, authorization)
    if status == 401:
        message = (
            "Wrong user name or password."
            if camera.username
            else "The camera needs a user name and password: rtsp://user:password@..."
        )
        raise _Failure("auth_failed", message)
    if status in (400, 404):  # some servers (MediaMTX, several NVRs) say 400 for an unknown path
        raise _Failure(
            "not_found", "The camera has no stream at this path. Check the camera's RTSP path."
        )
    if status != 200:
        raise _Failure("rtsp_error", f"The camera answered {status}.")
    return body


def _request(
    sock: socket.socket, camera: CameraUrl, cseq: int, authorization: str | None
) -> tuple[int, dict[str, list[str]], str]:
    lines = [
        f"DESCRIBE {camera.public} RTSP/1.0",
        f"CSeq: {cseq}",
        "Accept: application/sdp",
        "User-Agent: CamMind",
    ]
    if authorization:
        lines.append(f"Authorization: {authorization}")
    sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())

    reader = sock.makefile("rb")
    status_line = reader.readline(1024).decode("latin-1").strip()
    match = re.match(r"RTSP/1\.\d (\d{3})", status_line)
    if not match:
        raise _Failure("rtsp_error", "This address doesn't speak RTSP.")
    headers: dict[str, list[str]] = {}
    size = 0
    while True:
        line = reader.readline(4096).decode("latin-1")
        size += len(line)
        if line in ("\r\n", "\n", "") or size > MAX_RESPONSE_BYTES:
            break
        name, _, value = line.partition(":")
        headers.setdefault(name.strip().lower(), []).append(value.strip())
    length = int((headers.get("content-length") or ["0"])[0] or 0)
    body = reader.read(min(length, MAX_RESPONSE_BYTES)) if length else b""
    return int(match.group(1)), headers, body.decode("utf-8", "replace")


def _authorization(camera: CameraUrl, challenges: list[str]) -> str:
    digest = next((c for c in challenges if c.lower().startswith("digest")), None)
    if digest is None:
        token = base64.b64encode(f"{camera.username}:{camera.password}".encode()).decode()
        return f"Basic {token}"
    params = _digest_params(digest)
    realm, nonce = params.get("realm", ""), params.get("nonce", "")
    uri = camera.public

    def md5(text: str) -> str:
        return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()

    ha1 = md5(f"{camera.username}:{realm}:{camera.password}")
    ha2 = md5(f"DESCRIBE:{uri}")
    fields = [
        f'username="{camera.username}"',
        f'realm="{realm}"',
        f'nonce="{nonce}"',
        f'uri="{uri}"',
    ]
    if "auth" in params.get("qop", "").split(","):
        cnonce, nc = os.urandom(8).hex(), "00000001"
        response = md5(f"{ha1}:{nonce}:{nc}:{cnonce}:auth:{ha2}")
        fields += ["qop=auth", f"nc={nc}", f'cnonce="{cnonce}"']
    else:
        response = md5(f"{ha1}:{nonce}:{ha2}")
    fields.append(f'response="{response}"')
    if "opaque" in params:
        fields.append(f'opaque="{params["opaque"]}"')
    return "Digest " + ", ".join(fields)


def _digest_params(challenge: str) -> dict[str, str]:
    params = {}
    for match in re.finditer(r'(\w+)=(?:"([^"]*)"|([^,\s]*))', challenge):
        params[match.group(1).lower()] = (
            match.group(2) if match.group(2) is not None else match.group(3)
        )
    return params


def _video_from_sdp(sdp: str) -> tuple[str, float | None]:
    """The first video track's codec and frame rate (when the camera states it)."""
    in_video, payloads = False, set()
    codec, fps = "", None
    for line in sdp.splitlines():
        line = line.strip()
        if line.startswith("m="):
            if in_video and codec:
                break
            in_video = line.startswith("m=video")
            payloads = set(line.split()[3:]) if in_video else set()
            continue
        if not in_video:
            continue
        if line.startswith("a=rtpmap:"):
            payload, _, rest = line[len("a=rtpmap:") :].partition(" ")
            if payload in payloads and not codec:
                codec = rest.split("/")[0].upper()
        elif line.startswith(("a=framerate:", "a=x-framerate:")):
            try:
                fps = float(line.split(":", 1)[1])
            except ValueError:
                fps = None
    if not codec:
        if in_video or "m=video" in sdp:
            raise _Failure("unsupported_codec", "The camera's video format isn't stated.")
        raise _Failure("unsupported_codec", "This stream has no video.")
    if codec not in SUPPORTED_CODECS:
        raise _Failure(
            "unsupported_codec",
            f"The camera sends {codec} video. Switch the stream to H.264 or H.265.",
        )
    return SUPPORTED_CODECS[codec], fps
