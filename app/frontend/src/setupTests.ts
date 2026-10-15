import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom no trae ResizeObserver y Radix Slider lo necesita
class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub;

// jsdom no implementa scrollTo ni canvas (axe lo pide para detectar ligaduras)
window.scrollTo = () => {};
HTMLCanvasElement.prototype.getContext = (() =>
    null) as typeof HTMLCanvasElement.prototype.getContext;

afterEach(() => {
    cleanup();
});
