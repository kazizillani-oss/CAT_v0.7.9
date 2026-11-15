---
name: browser-automation
display_name: "Browser Automation & E2E Testing"
version: "1.1.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "testing"
description: "Drives headless browsers, Playwright/Puppeteer flows, automated scraping, synthetic testing, and screenshot verification."
tags: ["browser", "playwright", "puppeteer", "automation", "e2e"]
permissions: ["read_files", "write_files", "shell_commands"]
compatibility: ">=0.9.0"
---

# Browser Automation & E2E Testing

## Overview
Automate web browser interactions, end-to-end user journeys, synthetic monitoring, and visual regression testing using Playwright, Puppeteer, or Chrome DevTools.

## Operational Standards
1. **Selector Robustness**:
   - Prefer semantic accessibility selectors (`getByRole`, `getByLabel`, `data-testid`) over brittle CSS classes or deep XPath.
2. **Asynchronous Waiting & Flakiness Prevention**:
   - Avoid hardcoded `sleep` delays; always wait on explicit DOM state changes (`waitForSelector`, `waitForResponse`, network idle).
3. **Visual Verification & Artifacts**:
   - Capture full-page screenshots and DOM snapshots on assertion failure.
   - Record network activity and console errors for root-cause diagnosis.
