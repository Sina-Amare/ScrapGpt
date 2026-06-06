import "../test/setupDom";
import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";
import { fireEvent } from "@testing-library/react";
import { ProvidersPage } from "./ProvidersPage";
import { renderWithProviders } from "../test/render";

type FetchCall = [RequestInfo | URL, RequestInit | undefined];

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

describe("ProvidersPage", () => {
  const originalFetch = globalThis.fetch;
  let calls: FetchCall[] = [];

  beforeEach(() => {
    window.localStorage.clear();
    calls = [];
    globalThis.fetch = originalFetch;
  });

  it("never renders API key fields returned by mistake", async () => {
    globalThis.fetch = async (input, init) => {
      calls.push([input, init]);
      return jsonResponse([
        {
          id: 1,
          name: "OpenAI",
          provider: "openai",
          model: "gpt-4o-mini",
          is_default: true,
          capability_flags: { validated_json: true },
          api_key: "secret-key",
          api_key_encrypted: "encrypted-secret",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
      ]);
    };

    const view = renderWithProviders(<ProvidersPage />);

    assert.ok(await view.findByText("OpenAI"));
    assert.equal(view.queryByText("secret-key"), null);
    assert.equal(view.queryByText("encrypted-secret"), null);
  });

  it("prompts for password before revealing a provider key", async () => {
    globalThis.fetch = async (input, init) => {
      calls.push([input, init]);
      const path = String(input);
      if (path.endsWith("/providers") && !init?.method) {
        return jsonResponse([
          {
            id: 1,
            name: "OpenAI",
            provider: "openai",
            model: "gpt-4o-mini",
            is_default: true,
            capability_flags: {},
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          }
        ]);
      }
      if (path.endsWith("/providers/1/reveal-key")) {
        return jsonResponse({ api_key: "revealed-secret" });
      }
      return jsonResponse({});
    };

    const view = renderWithProviders(<ProvidersPage />);

    assert.ok(await view.findByText("OpenAI"));

    const revealButton = view
      .getAllByRole("button")
      .find((button) => button.textContent?.trim() === "Reveal");
    assert.ok(revealButton);

    fireEvent.click(revealButton);
    assert.equal(
      calls.some(([input]) => String(input).endsWith("/providers/1/reveal-key")),
      false
    );

    assert.ok(await view.findByText("Reveal key — OpenAI"));
    fireEvent.change(view.getByLabelText(/Account password/), {
      target: { value: "correct-password" }
    });
    fireEvent.click(view.getByRole("button", { name: "Reveal key" }));

    assert.equal(await view.findByDisplayValue("revealed-secret") !== null, true);
    const revealCall = calls.find(([input]) => String(input).endsWith("/providers/1/reveal-key"));

    assert.ok(revealCall);
    assert.equal(revealCall[1]?.method, "POST");
    assert.equal(String(revealCall[1]?.body), '{"password":"correct-password"}');
  });

});
