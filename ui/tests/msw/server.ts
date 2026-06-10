// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// The Node-side MSW server for Tier-2 (jsdom) UI tests. Started/reset/stopped
// from tests/setup.ts so every test runs against the /api/v1 mock by default.

import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
