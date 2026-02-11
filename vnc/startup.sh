#!/bin/bash
set -e

# Start Xvfb (virtual framebuffer)
Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99

# Wait for Xvfb to start
sleep 2

# Start x11vnc on the virtual display
x11vnc -display :99 -nopw -listen 0.0.0.0 -xkb -ncache 10 -forever &

# Start noVNC (websockify proxy)
websockify --web /usr/share/novnc/ 6080 localhost:5900

