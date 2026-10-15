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

// jsdom no implementa scrollTo
window.scrollTo = () => {};

afterEach(() => {
    cleanup();
});
