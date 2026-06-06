import { JSDOM } from "jsdom";
import { cleanup } from "@testing-library/react";
import { afterEach } from "node:test";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost/"
});

globalThis.window = dom.window as unknown as Window & typeof globalThis;
globalThis.document = dom.window.document;
Object.defineProperty(globalThis, "navigator", {
  configurable: true,
  value: dom.window.navigator
});
Object.defineProperty(globalThis, "HTMLElement", {
  configurable: true,
  value: dom.window.HTMLElement
});
Object.defineProperty(globalThis, "localStorage", {
  configurable: true,
  value: dom.window.localStorage
});

afterEach(() => {
  cleanup();
});
