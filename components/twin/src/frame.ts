/**
 * Everything about living inside a Streamlit iframe.
 *
 * We speak the host protocol directly rather than through
 * `streamlit-component-lib`'s `withStreamlitConnection`. That wrapper mounts,
 * renders null while it waits for the first render message, and — with React
 * 19 and Streamlit 1.60 — never completed the handshake in this project: the
 * iframe stayed at height zero with an empty root. A hand-written protocol
 * check proved the host side is fine, so we keep the twenty lines and drop the
 * dependency. The message names below are the host's contract, verified
 * against a live Streamlit 1.60 page.
 *
 * Two failure modes this file exists to prevent:
 *
 * HEIGHT — the iframe does not size itself. If nobody reports a height, the
 * page either clips the component or gives it an internal scrollbar. Height is
 * reported after every render, after data changes, on element resize, and once
 * more when web fonts settle and the text reflows.
 *
 * STANDALONE — the same bundle runs outside Streamlit for development and
 * fixture demos, where every host call must be a no-op.
 */

import { useEffect, useLayoutEffect, useRef, useState } from "react";

const READY = "streamlit:componentReady";
const SET_FRAME_HEIGHT = "streamlit:setFrameHeight";
const RENDER = "streamlit:render";
const API_VERSION = 1;

/** Streamlit always mounts us in an iframe; standalone dev is top level. */
export const insideStreamlit = (): boolean => {
  try {
    return window.parent !== window;
  } catch {
    // A cross-origin access threw, which only happens when we are framed.
    return true;
  }
};

const post = (type: string, data: Record<string, unknown> = {}): void => {
  if (!insideStreamlit()) return;
  window.parent.postMessage({ isStreamlitMessage: true, type, ...data }, "*");
};

/** What the host sends us on every rerun. */
export interface RenderPayload {
  args: Record<string, unknown>;
  disabled: boolean;
  /** The host's own theme. We do not use it — see `contract.ts`. */
  theme?: { base?: string };
}

/**
 * Subscribe to the host's render messages.
 *
 * Returns undefined until the first message arrives. The listener is attached
 * before we announce readiness, so a fast host reply cannot be missed.
 */
export function useStreamlitArgs(): RenderPayload | undefined {
  const [payload, setPayload] = useState<RenderPayload | undefined>(undefined);

  useEffect(() => {
    if (!insideStreamlit()) return;

    const onMessage = (event: MessageEvent) => {
      const data = event.data as { type?: string; args?: Record<string, unknown> };
      if (data?.type !== RENDER) return;
      setPayload({
        args: data.args ?? {},
        disabled: Boolean((data as { disabled?: unknown }).disabled),
        theme: (data as { theme?: { base?: string } }).theme,
      });
    };

    window.addEventListener("message", onMessage);
    post(READY, { apiVersion: API_VERSION });

    return () => window.removeEventListener("message", onMessage);
  }, []);

  return payload;
}

/**
 * Keep the host frame exactly as tall as the content.
 *
 * Attach the returned ref to the outermost element. The height is measured
 * from a layout effect, before paint, so the frame never flashes at the wrong
 * size, and re-reported whenever the element's own box changes.
 */
export function useFrameHeight<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const last = useRef<number>(-1);

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;

    const send = () => {
      const height = Math.ceil(node.getBoundingClientRect().height);
      if (height === last.current) return; // the host redraws on every message
      last.current = height;
      post(SET_FRAME_HEIGHT, { height });
    };

    send();
    const frame = requestAnimationFrame(send);
    const observer = new ResizeObserver(send);
    observer.observe(node);
    document.fonts?.ready.then(send).catch(() => undefined);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  });

  return ref;
}
