#!/bin/sh
# Publishes one fake camera into MediaMTX: rtsp://localhost:8554/<name> inside the container.
# - clips/<name>.mp4 present: loop it in real time without re-encoding (like a real camera).
# - otherwise: a moving 640x360 test pattern, encoded as H.264.
set -eu
name="$1"
target="rtsp://localhost:8554/$name"
clip="/clips/$name.mp4"

if [ -f "$clip" ]; then
  exec ffmpeg -hide_banner -loglevel error -re -stream_loop -1 -i "$clip" \
    -an -c:v copy -f rtsp -rtsp_transport tcp "$target"
fi

exec ffmpeg -hide_banner -loglevel error -re \
  -f lavfi -i "testsrc2=size=640x360:rate=10" \
  -c:v libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p -g 20 -b:v 600k \
  -f rtsp -rtsp_transport tcp "$target"
