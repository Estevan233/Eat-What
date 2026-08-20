# WeChat Miniapp Login Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore guest and WeChat login requests in the mp-weixin build and make failures diagnosable in WeChat DevTools.

**Architecture:** Move authentication persistence into a framework-independent module. The request layer reads that module directly, while Pinia owns only reactive state and calls the same persistence API, eliminating the request/store circular dependency.

**Tech Stack:** uni-app, Vue 3, Pinia, TypeScript, Vitest, FastAPI, WeChat DevTools

---

### Task 1: Reproduce the request-layer regression

**Files:**
- Create: `miniapp/src/api/request.test.ts`
- Modify: `miniapp/vitest.config.ts`

- [ ] Write a test that invokes `request()` without installing Pinia and expects `uni.request` to be called.
- [ ] Run the focused test and verify the current implementation fails before `uni.request`.
- [ ] Configure the existing `@` alias for Vitest if required by the focused test.

### Task 2: Remove the circular dependency

**Files:**
- Create: `miniapp/src/auth/storage.ts`
- Create: `miniapp/src/auth/storage.test.ts`
- Modify: `miniapp/src/api/request.ts`
- Modify: `miniapp/src/stores/user.ts`

- [ ] Write failing tests for token retrieval, session persistence, and authentication cleanup.
- [ ] Implement the storage module with the existing storage keys.
- [ ] Change `request.ts` to read/clear auth storage without importing Pinia.
- [ ] Change `stores/user.ts` to persist and restore through the storage module.
- [ ] Run focused tests and verify they pass.

### Task 3: Expose login failures and silence unrelated telemetry

**Files:**
- Modify: `miniapp/src/pages/auth/auth.vue`
- Modify: `miniapp/src/manifest.json`

- [ ] Add one shared click lock for both login actions.
- [ ] Log caught errors and show a fallback toast for pre-request failures.
- [ ] Set `mp-weixin.uniStatistics.enable` to `false`.

### Task 4: Configure local WeChat credentials safely

**Files:**
- Local only: `backend/.env`

- [ ] Preserve all existing local values and replace only `WX_APPID` and `WX_SECRET`.
- [ ] Ensure `.env` remains ignored and mode `600` in WSL.
- [ ] Restart FastAPI so its cached settings and `wx_client` use the new values.
- [ ] Verify health and guest-login from Windows without printing credentials.

### Task 5: Build and WeChat DevTools verification

**Files:**
- Verify: `miniapp/dist/dev/mp-weixin`
- Verify: `miniapp/dist/build/mp-weixin`

- [ ] Run frontend tests, type-check, lint check, and mp-weixin production build.
- [ ] Run the development compiler and verify `app.json` plus the expected AppID.
- [ ] Inspect compiled `api/request.js` to ensure no dynamic store import remains.
- [ ] Open the development output in WeChat DevTools, clear cache, compile, and verify guest login and WeChat login requests in Network.
- [ ] Document the hard boundary between local simulator debugging and phone QR preview.
