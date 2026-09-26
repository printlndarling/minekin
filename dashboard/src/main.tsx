import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles/global.css";

const container = document.getElementById("root");
if (container === null) {
  throw new Error("#root 缺失：拒绝在无名宿主上挂载控制台。");
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
