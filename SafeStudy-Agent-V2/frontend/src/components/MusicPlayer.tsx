import { useEffect, useRef, useState } from "react";

// Official YouTube embed (IFrame Player API). Nothing is downloaded or bundled.
// Override with VITE_BGM_VIDEO_ID in frontend/.env to use a different video.
const VIDEO_ID: string = import.meta.env.VITE_BGM_VIDEO_ID || "pidL4XYP_II";
const WATCH_URL = `https://www.youtube.com/watch?v=${VIDEO_ID}`;

/* eslint-disable @typescript-eslint/no-explicit-any */
declare global { interface Window { YT?: any; onYouTubeIframeAPIReady?: () => void } }

let apiPromise: Promise<void> | null = null;
function loadYouTubeApi(): Promise<void> {
  if (window.YT?.Player) return Promise.resolve();
  if (!apiPromise) {
    apiPromise = new Promise((resolve, reject) => {
      const prev = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => { prev?.(); resolve(); };
      const s = document.createElement("script");
      s.src = "https://www.youtube.com/iframe_api";
      s.onerror = () => { apiPromise = null; reject(new Error("blocked")); };
      document.head.appendChild(s);
    });
  }
  return apiPromise;
}

export default function MusicPlayer() {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const host = useRef<HTMLDivElement>(null);
  const player = useRef<any>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setError("");
    loadYouTubeApi().then(() => {
      if (cancelled || !host.current) return;
      const mount = document.createElement("div");
      host.current.appendChild(mount);
      player.current = new window.YT.Player(mount, {
        width: 240, height: 240, videoId: VIDEO_ID,
        playerVars: { loop: 1, playlist: VIDEO_ID, playsinline: 1, rel: 0, controls: 1 },
        events: { onError: () => setError("This video can’t be embedded or played here.") },
      });
    }).catch(() => setError("Couldn’t reach YouTube. Check your connection or ad blocker."));
    return () => {
      cancelled = true;
      try { player.current?.destroy(); } catch { /* already gone */ }
      player.current = null;
      if (host.current) host.current.innerHTML = "";
    };
  }, [open]);

  return (
    <div className="fixed bottom-20 right-4 z-30 flex flex-col items-end gap-2 lg:bottom-4">
      {open && (
        <div className="card w-[272px] p-3 shadow-xl" role="dialog" aria-label="Background music">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-extrabold">Study music</span>
            <button className="text-sm text-mute hover:text-ink" onClick={() => setOpen(false)} aria-label="Close music player">Close</button>
          </div>
          <div ref={host} className="overflow-hidden rounded-xl" style={{ width: 240, height: 240 }} />
          {error ? (
            <p role="alert" className="mt-2 text-sm text-bad">{error} <a className="underline" href={WATCH_URL} target="_blank" rel="noreferrer">Open on YouTube</a></p>
          ) : (
            <p className="mt-2 text-xs text-mute">Press play in the player. Closing this panel stops the music.</p>
          )}
        </div>
      )}
      <button className="btn-primary shadow-lg" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {open ? "Hide music" : "Music"}
      </button>
    </div>
  );
}
