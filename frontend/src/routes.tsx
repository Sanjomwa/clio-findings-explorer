import type { RouteObject } from "react-router-dom";
import Shell from "./components/Shell";
import About from "./pages/About";
import Finding from "./pages/Finding";
import Findings from "./pages/Findings";
import Ledger from "./pages/Ledger";
import Methodology from "./pages/Methodology";
import NotFound from "./pages/NotFound";

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
