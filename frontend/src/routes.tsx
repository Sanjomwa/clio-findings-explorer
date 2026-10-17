import type { RouteObject } from "react-router-dom";
import Shell from "./components/Shell";
import { About, Finding, Findings, Ledger, Methodology, NotFound } from "./pages/Placeholders";

export const routes: RouteObject[] = [
  {
    element: <Shell />,
    children: [
      { path: "/", element: <Ledger /> },
      { path: "/findings", element: <Findings /> },
      { path: "/findings/:slug", element: <Finding /> },
      { path: "/methodology", element: <Methodology /> },
      { path: "/about", element: <About /> },
      { path: "*", element: <NotFound /> },
    ],
  },
];
