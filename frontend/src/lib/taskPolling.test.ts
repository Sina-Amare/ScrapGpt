import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { shouldPollTask } from "./taskPolling";
import { TaskResponse } from "../types";

const baseTask: TaskResponse = {
  task_id: 1,
  state: "SCRAPING",
  url: "https://example.com",
  error: null,
  result: null,
  message: null,
  created_at: null,
  content_length: null
};

describe("task polling", () => {
  it("stops on terminal states", () => {
    assert.equal(shouldPollTask({ ...baseTask, state: "COMPLETED" }, 0), false);
    assert.equal(shouldPollTask({ ...baseTask, state: "FAILED" }, 0), false);
  });

  it("stops on current task 404", () => {
    assert.equal(shouldPollTask(null, 0, true), false);
  });

  it("stops after three consecutive failures", () => {
    assert.equal(shouldPollTask(baseTask, 3), false);
  });

  it("keeps polling unknown active states", () => {
    assert.equal(shouldPollTask({ ...baseTask, state: "FUTURE_STATE" }, 0), true);
  });
});
