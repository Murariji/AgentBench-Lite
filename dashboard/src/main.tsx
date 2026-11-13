import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// Inter, installed locally (@fontsource, Latin subset): bundled with the app - no request to Google.
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/inter/latin-700.css";
import { App } from "./App";
import "./index.css";

// Put the React app into <div id="root"> of index.html.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
