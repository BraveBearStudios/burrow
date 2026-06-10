// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// Vitest global setup: install the jest-dom matchers for every test file. The
// MSW server lifecycle (start/reset/stop) is wired here in Task 3 once the
// handlers exist, so Tier-2 component tests get /api/v1 mocking for free.
import "@testing-library/jest-dom/vitest";
