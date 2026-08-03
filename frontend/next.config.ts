import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The site is a single client-rendered page that talks to the FastAPI
  // backend from the browser, so there is nothing for a Node server to do at
  // request time. Exporting to static HTML/JS lets the API process serve the
  // UI from its own origin: one deployment, one URL, and no CORS or
  // mixed-content surface between the two halves.
  output: "export",
};

export default nextConfig;
