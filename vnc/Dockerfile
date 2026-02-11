FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

COPY startup.sh /startup.sh
RUN chmod +x /startup.sh

EXPOSE 6080 5900

CMD ["/startup.sh"]
