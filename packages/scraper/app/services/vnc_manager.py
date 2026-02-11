import asyncio
import os
import signal
import subprocess
import uuid
from app.config import settings


class VNCManager:
    """Manages Xvfb + x11vnc + websockify processes for manual browser intervention."""

    def __init__(self):
        self.sessions: dict[str, dict] = {}
        self._xvfb_proc: subprocess.Popen | None = None
        self._x11vnc_proc: subprocess.Popen | None = None
        self._websockify_proc: subprocess.Popen | None = None
        self._display = ":99"
        self._vnc_port = 5900
        self._ws_port = 6080

    def _start_xvfb(self):
        """Start Xvfb virtual framebuffer if not already running."""
        if self._xvfb_proc and self._xvfb_proc.poll() is None:
            return
        self._xvfb_proc = subprocess.Popen(
            ["Xvfb", self._display, "-screen", "0", "1280x720x24"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _start_x11vnc(self):
        """Start x11vnc server on the Xvfb display."""
        if self._x11vnc_proc and self._x11vnc_proc.poll() is None:
            return
        self._x11vnc_proc = subprocess.Popen(
            [
                "x11vnc",
                "-display", self._display,
                "-nopw",
                "-listen", "0.0.0.0",
                "-xkb",
                "-ncache", "10",
                "-forever",
                "-rfbport", str(self._vnc_port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _start_websockify(self):
        """Start websockify to proxy VNC over WebSocket for noVNC."""
        if self._websockify_proc and self._websockify_proc.poll() is None:
            return
        self._websockify_proc = subprocess.Popen(
            [
                "websockify",
                "--web", "/usr/share/novnc/",
                str(self._ws_port),
                f"localhost:{self._vnc_port}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _stop_vnc_processes(self):
        """Stop x11vnc and websockify (keep Xvfb running for reuse)."""
        for proc in (self._x11vnc_proc, self._websockify_proc):
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        self._x11vnc_proc = None
        self._websockify_proc = None

    def get_display(self) -> str:
        """Return the DISPLAY value for Playwright to use."""
        return self._display

    async def start_session(self, execution_id: str) -> dict:
        """Start a VNC session: Xvfb + x11vnc + websockify."""
        session_id = str(uuid.uuid4())

        self._start_xvfb()
        await asyncio.sleep(1)  # Wait for Xvfb
        self._start_x11vnc()
        self._start_websockify()
        await asyncio.sleep(0.5)

        vnc_url = f"http://localhost:{self._ws_port}/vnc_lite.html?autoconnect=true"

        resume_event = asyncio.Event()

        self.sessions[session_id] = {
            "execution_id": execution_id,
            "vnc_url": vnc_url,
            "status": "active",
            "resume_event": resume_event,
        }

        return {
            "session_id": session_id,
            "vnc_url": vnc_url,
        }

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
        """Stop a VNC session and clean up processes."""
        session = self.sessions.pop(session_id, None)
        if session:
            session["status"] = "stopped"
            # Signal resume event so executor can clean up
            session["resume_event"].set()

        # Only stop VNC processes if no active sessions remain
        if not any(s["status"] == "active" for s in self.sessions.values()):
            self._stop_vnc_processes()

        return {"status": "stopped"}

    def cleanup(self):
        """Stop all VNC processes."""
        self._stop_vnc_processes()
        if self._xvfb_proc and self._xvfb_proc.poll() is None:
            try:
                self._xvfb_proc.terminate()
                self._xvfb_proc.wait(timeout=5)
            except Exception:
                try:
                    self._xvfb_proc.kill()
                except Exception:
                    pass
        self._xvfb_proc = None
