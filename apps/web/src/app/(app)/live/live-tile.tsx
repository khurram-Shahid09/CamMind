"use client";

import { useEffect, useState } from "react";

import { GO2RTC_URL } from "@/lib/types";

/** A frame per second from go2rtc on this machine. The next frame loads off-screen first,
 * so the tile never flickers. (WebRTC playback is pending; docs/20.) */
export function LiveTile({ cameraId, name }: { cameraId: string; name: string }) {
  const [src, setSrc] = useState(`${GO2RTC_URL}/api/frame.jpeg?src=${cameraId}`);
  useEffect(() => {
    let alive = true;
    const tick = () => {
      const next = `${GO2RTC_URL}/api/frame.jpeg?src=${cameraId}&t=${Date.now()}`;
      const image = new Image();
      image.onload = () => alive && setSrc(next);
      image.src = next;
    };
    const timer = setInterval(tick, 1000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [cameraId]);
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt={name} className="h-full w-full object-cover" />;
}
