import "./test/setupDom";
import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";
import { waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { AuthProvider } from "./lib/auth";
import { ProtectedRoute, PublicRoute } from "./layout/RouteGuards";
import { renderWithProviders } from "./test/render";

type FetchCall = [RequestInfo | URL, RequestInit | undefined];

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

describe("routing and auth", () => {
  const originalFetch = globalThis.fetch;
  let calls: FetchCall[] = [];

  beforeEach(() => {
    window.localStorage.clear();
    globalThis.fetch = originalFetch;
    calls = [];
  });

  function GuardHarness() {
    return (
      <AuthProvider>
        <Routes>
          <Route element={<PublicRoute />}>
            <Route path="/login" element={<h1>Welcome back</h1>} />
          </Route>
          <Route element={<ProtectedRoute />}>
            <Route path="/providers" element={<h1>Protected providers</h1>} />
            <Route path="/dashboard" element={<h1>Dashboard</h1>} />
          </Route>
        </Routes>
      </AuthProvider>
    );
  }

  it("protected routes redirect unauthenticated users", async () => {
    const view = renderWithProviders(<GuardHarness />, ["/providers"]);

    assert.ok(await view.findByRole("heading", { name: "Welcome back" }));
  });

  it("boot refresh restores session and redirects authenticated users away from login", async () => {
    window.localStorage.setItem("scrapegpt_refresh_token", "refresh-token");
    window.localStorage.setItem("scrapegpt_user_email", "user@example.com");
    const responses = [
      jsonResponse({
          access_token: "access",
          refresh_token: "refresh-2",
          token_type: "bearer"
        }),
      jsonResponse({ status: "ok" }),
      jsonResponse({ detail: "No active task" }, 404)
    ];
    globalThis.fetch = async (input, init) => {
      calls.push([input, init]);
      return responses.shift() ?? jsonResponse({ status: "ok" });
    };

    const view = renderWithProviders(<GuardHarness />, ["/login"]);

    await waitFor(() =>
      assert.ok(view.getByRole("heading", { name: "Dashboard" }))
    );
  });
});
