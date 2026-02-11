import asyncio
import os
import subprocess
import uuid
from app.config import settings


class VNCManager:
    """Manages per-session Xvfb + x11vnc + websockify processes.

    Each VNC session gets its own isolated display, VNC port, and websocket port
    so multiple users/tasks can have concurrent manual interventions.

    Two-phase approach:
    1. reserve_display() - starts only Xvfb for Playwright to render on
    2. activate_vnc() - starts x11vnc + websockify when user needs to see the browser

    Display allocation:  :99, :100, :101, ...
    VNC port allocation: 5999, 6000, 6001, ...
    WS port allocation:  6080, 6081, 6082, ...
    """

    _BASE_DISPLAY = 99
    _BASE_VNC_PORT = 5999
    _BASE_WS_PORT = 6080
    _MAX_SESSIONS = 20

    def __init__(self):
        self.sessions: dict[str, dict] = {}
        self._lock = asyncio.Lock()

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
    def _ws_port_for_slot(slot: int) -> int:
        return VNCManager._BASE_WS_PORT + slot

    @staticmethod
    def _start_xvfb(display: str) -> subprocess.Popen:
        return subprocess.Popen(
            ["Xvfb", display, "-screen", "0", "1280x720x24"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @staticmethod
    def _start_x11vnc(display: str, vnc_port: int) -> subprocess.Popen:
        return subprocess.Popen(
            [
                "x11vnc",
                "-display", display,
                "-nopw",
                "-listen", "0.0.0.0",
                "-xkb",
                "-ncache", "10",
                "-forever",
                "-rfbport", str(vnc_port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @staticmethod
    def _start_websockify(ws_port: int, vnc_port: int) -> subprocess.Popen:
        return subprocess.Popen(
            [
                "websockify",
                "--web", "/usr/share/novnc/",
                str(ws_port),
                f"localhost:{vnc_port}",
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
        x11vnc + websockify are NOT started yet (call activate_vnc later).
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
                "ws_port": self._ws_port_for_slot(slot),
                "status": "reserved",
                "resume_event": asyncio.Event(),
                "xvfb_proc": xvfb_proc,
                "x11vnc_proc": None,
                "websockify_proc": None,
            }

        await asyncio.sleep(1)  # Wait for Xvfb to be ready

        return {
            "session_id": session_id,
            "display": display,
        }

    async def activate_vnc(self, session_id: str) -> dict:
        """Phase 2: Start x11vnc + websockify on an already-reserved display.

        Call this when the user actually needs to see the browser (CAPTCHA/2FA pause).
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        display = session["display"]
        vnc_port = session["vnc_port"]
        ws_port = session["ws_port"]

        # Start VNC viewer processes
        session["x11vnc_proc"] = self._start_x11vnc(display, vnc_port)
        session["websockify_proc"] = self._start_websockify(ws_port, vnc_port)
        session["status"] = "active"

        await asyncio.sleep(0.5)  # Wait for processes to be ready

        novnc_host = os.environ.get("NOVNC_PUBLIC_HOST", "localhost")
        vnc_url = f"http://{novnc_host}:{ws_port}/vnc_lite.html?autoconnect=true"
        session["vnc_url"] = vnc_url

        return {
            "session_id": session_id,
            "vnc_url": vnc_url,
            "ws_port": ws_port,
            "display": display,
        }

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
        """Stop a VNC session and clean up its processes."""
        session = self.sessions.pop(session_id, None)
        if not session:
            return {"status": "not_found"}

        session["status"] = "stopped"
        session["resume_event"].set()

        # Kill this session's processes
        self._kill_proc(session.get("x11vnc_proc"))
        self._kill_proc(session.get("websockify_proc"))
        self._kill_proc(session.get("xvfb_proc"))

        return {"status": "stopped"}

    def cleanup(self):
        """Stop all VNC sessions and their processes."""
        for session_id in list(self.sessions.keys()):
            session = self.sessions.pop(session_id, None)
            if session:
                session["resume_event"].set()
                self._kill_proc(session.get("x11vnc_proc"))
                self._kill_proc(session.get("websockify_proc"))
                self._kill_proc(session.get("xvfb_proc"))
