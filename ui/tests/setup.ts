// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// Vitest global setup: install the jest-dom matchers and run the MSW server for
// every test so Tier-2 component tests get /api/v1 mocking for free. Unhandled
// requests error so a missing handler surfaces instead of silently hanging.
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./msw/server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
