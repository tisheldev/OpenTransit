import { useSyncExternalStore } from "react";

// Browser connectivity (design: Home, "Offline → Home still renders; the banner reads
// 'no connection'"). navigator.onLine can only say "certainly offline".

function subscribe(onChange: () => void): () => void {
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => {
    window.removeEventListener("online", onChange);
    window.removeEventListener("offline", onChange);
  };
}

const online = () => globalThis.navigator?.onLine !== false;

export function useOnline(): boolean {
  return useSyncExternalStore(subscribe, online, () => true);
}
