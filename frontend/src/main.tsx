import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "@fontsource/schibsted-grotesk/500.css";
import "@fontsource/schibsted-grotesk/600.css";
import "@fontsource/schibsted-grotesk/700.css";
import "@fontsource/schibsted-grotesk/800.css";
import "@fontsource/literata/400.css";
import "@fontsource/literata/600.css";
import "@fontsource/literata/400-italic.css";
import "@fontsource/spline-sans-mono/400.css";
import "@fontsource/spline-sans-mono/500.css";
import "@fontsource/spline-sans-mono/600.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/ledger.css";
import "./styles/finding.css";
import "./styles/pages.css";
import { routes } from "./routes";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={createBrowserRouter(routes)} />
  </StrictMode>,
);
