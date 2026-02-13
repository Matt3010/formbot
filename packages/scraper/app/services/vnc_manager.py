import asyncio
import os
import subprocess
import uuid
import secrets
from app.config import settings


class VNCManager:
    """Manages per-session Xvfb + x11vnc with a single token-based websockify.

    Security: All VNC sessions are routed through a single websockify on port 6080
    using token-based routing. Each session gets a unique, unguessable token.
    Without the token, connections are rejected. x11vnc listens on localhost only.

    Two-phase approach:
    1. reserve_display() - starts only Xvfb for Playwright to render on
    2. activate_vnc() - starts x11vnc, registers token in websockify router

    Display allocation:  :99, :100, :101, ...
    VNC port allocation: 5999, 6000, 6001, ... (localhost only, not exposed)
    WebSocket: single port 6080 with token routing
    """

    _BASE_DISPLAY = 99
    _BASE_VNC_PORT = 5999
    _WS_PORT = 6080
    _TOKEN_FILE = "/tmp/vnc_tokens"
    _MAX_SESSIONS = 20

    def __init__(self):
        self.sessions: dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self._websockify_proc: subprocess.Popen | None = None
        self._cleanup_stale_displays()

    def _ensure_websockify(self):
        """Start the shared websockify process with token routing if not running."""
        if self._websockify_proc and self._websockify_proc.poll() is None:
            return

        # Create/reset token file
        with open(self._TOKEN_FILE, "w") as f:
            pass

        self._websockify_proc = subprocess.Popen(
            [
                "websockify",
                "--web", "/usr/share/novnc/",
                "--token-plugin", "TokenFile",
                "--token-source", self._TOKEN_FILE,
                str(self._WS_PORT),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _add_token(self, token: str, vnc_port: int):
        """Register a token -> vnc_port route in the token file."""
        with open(self._TOKEN_FILE, "a") as f:
            f.write(f"{token}: localhost:{vnc_port}\n")

    def _remove_token(self, token: str):
        """Remove a token from the token file, revoking access."""
        try:
            with open(self._TOKEN_FILE, "r") as f:
                lines = f.readlines()
            with open(self._TOKEN_FILE, "w") as f:
                for line in lines:
                    if not line.startswith(f"{token}:"):
                        f.write(line)
        except FileNotFoundError:
            pass

    def _find_free_slot(self) -> int:
        """Find the first available slot (0-based) not used by any active session."""
        used_slots = {s["slot"] for s in self.sessions.values()}
        for slot in range(self._MAX_SESSIONS):
            if slot not in used_slots:
                return slot
        raise RuntimeError(f"No free VNC slots (max {self._MAX_SESSIONS} concurrent sessions)")

    @staticmethod
    def _display_for_slot(slot: int) -> str:
        return f":{VNCManager._BASE_DISPLAY + slot}"

    @staticmethod
    def _vnc_port_for_slot(slot: int) -> int:
        return VNCManager._BASE_VNC_PORT + slot

    @staticmethod
    def _cleanup_stale_displays():
        """Remove stale Xvfb lock files and sockets from previous runs."""
        import glob
        for lock in glob.glob("/tmp/.X*-lock"):
            try:
                with open(lock) as f:
                    pid = int(f.read().strip())
                # Check if the process is still alive
                try:
                    os.kill(pid, 0)
                except OSError:
                    # Process is dead, remove stale lock file
                    os.remove(lock)
                    display_num = lock.replace("/tmp/.X", "").replace("-lock", "")
                    socket_path = f"/tmp/.X11-unix/X{display_num}"
                    if os.path.exists(socket_path):
                        os.remove(socket_path)
            except (ValueError, FileNotFoundError, PermissionError):
                pass

    @staticmethod
    def _clean_display_files(display: str):
        """Remove lock file and socket for a specific display before starting Xvfb."""
        display_num = display.lstrip(":")
        lock_file = f"/tmp/.X{display_num}-lock"
        socket_path = f"/tmp/.X11-unix/X{display_num}"
        for path in [lock_file, socket_path]:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    @staticmethod
    def _kill_existing_xvfb(display: str):
        """Kill any existing Xvfb process on this display."""
        display_num = display.lstrip(":")
        lock_file = f"/tmp/.X{display_num}-lock"
        try:
            with open(lock_file) as f:
                pid = int(f.read().strip())
            os.kill(pid, 9)  # SIGKILL
        except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
            pass

    @staticmethod
    def _start_xvfb(display: str) -> subprocess.Popen:
        VNCManager._kill_existing_xvfb(display)
        VNCManager._clean_display_files(display)
        proc = subprocess.Popen(
            ["Xvfb", display, "-screen", "0", "1280x720x24"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        return proc

    @staticmethod
    def _start_x11vnc(display: str, vnc_port: int) -> subprocess.Popen:
        return subprocess.Popen(
            [
                "x11vnc",
                "-display", display,
                "-nopw",
                "-listen", "localhost",
                "-xkb",
                "-forever",
                "-rfbport", str(vnc_port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @staticmethod
    def _kill_proc(proc: subprocess.Popen | None):
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    async def reserve_display(self, execution_id: str) -> dict:
        """Phase 1: Reserve a slot and start only Xvfb.

        Returns session info with display for Playwright to use.
        x11vnc is NOT started yet (call activate_vnc later).
        """
        async with self._lock:
            slot = self._find_free_slot()

            session_id = str(uuid.uuid4())
            display = self._display_for_slot(slot)

            xvfb_proc = self._start_xvfb(display)

            self.sessions[session_id] = {
                "execution_id": execution_id,
                "slot": slot,
                "display": display,
                "vnc_port": self._vnc_port_for_slot(slot),
                "status": "reserved",
                "resume_event": asyncio.Event(),
                "xvfb_proc": xvfb_proc,
                "x11vnc_proc": None,
                "vnc_token": None,
            }

        await asyncio.sleep(1)  # Wait for Xvfb to be ready

        # Verify Xvfb actually started
        if xvfb_proc.poll() is not None:
            stderr = xvfb_proc.stderr.read().decode() if xvfb_proc.stderr else ""
            self.sessions.pop(session_id, None)
            # Try cleanup and retry once
            self._clean_display_files(display)
            await asyncio.sleep(0.5)
            xvfb_proc = self._start_xvfb(display)
            await asyncio.sleep(1)
            if xvfb_proc.poll() is not None:
                raise RuntimeError(
                    f"Failed to start Xvfb on {display}: {stderr}"
                )
            self.sessions[session_id] = {
                "execution_id": execution_id,
                "slot": slot,
                "display": display,
                "vnc_port": self._vnc_port_for_slot(slot),
                "status": "reserved",
                "resume_event": asyncio.Event(),
                "xvfb_proc": xvfb_proc,
                "x11vnc_proc": None,
                "vnc_token": None,
            }

        return {
            "session_id": session_id,
            "display": display,
        }

    async def activate_vnc(self, session_id: str) -> dict:
        """Phase 2: Start x11vnc and register token for websockify routing.

        Call this when the user actually needs to see the browser (CAPTCHA/2FA pause).
        Returns VNC URL with the unique access token.
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Ensure shared websockify is running
        self._ensure_websockify()

        display = session["display"]
        vnc_port = session["vnc_port"]

        # Start x11vnc (localhost only — only websockify can reach it)
        session["x11vnc_proc"] = self._start_x11vnc(display, vnc_port)

        # Generate unguessable token and register route
        token = secrets.token_urlsafe(32)
        session["vnc_token"] = token
        self._add_token(token, vnc_port)

        session["status"] = "active"

        await asyncio.sleep(0.5)  # Wait for x11vnc to be ready

        novnc_host = os.environ.get("NOVNC_PUBLIC_HOST", "localhost")
        vnc_url = (
            f"http://{novnc_host}:{self._WS_PORT}/vnc_embed.html"
            f"?path=websockify/?token={token}&autoconnect=true"
        )
        session["vnc_url"] = vnc_url

        return {
            "session_id": session_id,
            "vnc_url": vnc_url,
            "ws_port": self._WS_PORT,
            "display": display,
        }

    def deactivate_vnc(self, session_id: str):
        """Kill x11vnc and revoke token, but keep Xvfb running.

        Called after user resumes — browser still needs the display, but VNC
        access is no longer needed and the token is invalidated.
        """
        session = self.sessions.get(session_id)
        if not session:
            return

        # Revoke token (immediate — websockify re-reads the file on each connection)
        if session.get("vnc_token"):
            self._remove_token(session["vnc_token"])
            session["vnc_token"] = None

        # Kill x11vnc
        self._kill_proc(session.get("x11vnc_proc"))
        session["x11vnc_proc"] = None

        session["status"] = "reserved"

    async def start_session(self, execution_id: str) -> dict:
        """Convenience: reserve display + activate VNC in one call."""
        reserved = await self.reserve_display(execution_id)
        session_id = reserved["session_id"]
        result = await self.activate_vnc(session_id)
        return result

    async def wait_for_resume(self, session_id: str, timeout: float = 3600) -> bool:
        """Wait for resume signal. Returns True if resumed, False if timed out."""
        session = self.sessions.get(session_id)
        if not session:
            return False
        try:
            await asyncio.wait_for(session["resume_event"].wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def resume_session(self, session_id: str, execution_id: str) -> dict:
        """Signal the execution to resume after manual VNC intervention."""
        session = self.sessions.get(session_id)
        if not session:
            return {"status": "not_found"}

        session["status"] = "resumed"
        session["resume_event"].set()

        return {"status": "resumed", "execution_id": execution_id}

    async def stop_session(self, session_id: str) -> dict:
        """Stop a VNC session: revoke token, kill x11vnc + Xvfb."""
        session = self.sessions.pop(session_id, None)
        if not session:
            return {"status": "not_found"}

        session["status"] = "stopped"
        session["resume_event"].set()

        # Revoke token
        if session.get("vnc_token"):
            self._remove_token(session["vnc_token"])

        # Kill session processes
        self._kill_proc(session.get("x11vnc_proc"))
        self._kill_proc(session.get("xvfb_proc"))

        # Clean up display files
        if session.get("display"):
            self._clean_display_files(session["display"])

        return {"status": "stopped"}

    def cleanup(self):
        """Stop all VNC sessions and the shared websockify."""
        for session_id in list(self.sessions.keys()):
            session = self.sessions.pop(session_id, None)
            if session:
                session["resume_event"].set()
                if session.get("vnc_token"):
                    self._remove_token(session["vnc_token"])
                self._kill_proc(session.get("x11vnc_proc"))
                self._kill_proc(session.get("xvfb_proc"))

        # Stop shared websockify
        self._kill_proc(self._websockify_proc)
        self._websockify_proc = None

        # Clean token file
        try:
            os.remove(self._TOKEN_FILE)
        except FileNotFoundError:
            pass
