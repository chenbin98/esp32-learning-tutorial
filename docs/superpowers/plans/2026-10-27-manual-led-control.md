# Manual LED Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add browser control for GPIO23 while preserving a deliberate automatic alarm mode.

**Architecture:** Keep the existing MicroPython HTTP server and single-page UI. Add in-memory control mode and desired manual LED state, a validated command route, and API fields that distinguish the automatic threshold condition from actual LED output. Update the project tutorial and embedded source together.

**Tech Stack:** MicroPython, built-in socket/ujson, inline HTML/CSS/JavaScript.

**Spec:** `docs/superpowers/specs/2026-10-27-manual-led-control-design.md`

## Global Constraints

- Boot in automatic mode with GPIO23 low.
- Automatic mode controls GPIO23 only when valid DHT11 readings are available; on a sensor read error retain the last valid output.
- Manual mode lets browser commands set GPIO23 and sampling must not override that state.
- Returning to automatic mode immediately applies the latest valid threshold result; if no valid reading exists, turn GPIO23 off.
- Invalid commands must not change mode or GPIO output.
- Keep project `main.py` and its complete code block in `index.html` synchronized.
- Work in the current project directory; do not create a worktree.

## Review Focus

- A later sensor sample must not override a manual LED command; keep this branch explicit in `sample_sensor()`.
- Automatic threshold state and physical GPIO output diverge in manual mode; expose both separately in `/api/readings` and label the page accordingly.
- Switching to automatic without a valid reading must not reuse stale or null data as an alarm; set output low.
- Unknown paths, unsupported methods, and invalid mode/action values must not mutate control state.
- A button request can race with the one-second refresh; disable controls during command submission and refresh from the returned API state.
- The control endpoint has no authentication; label the feature as trusted-local-network only and do not present it as internet-safe.

---

### Task 1: Add server-side mode and command API

**Files:**
- Modify: `projects/01-temperature-humidity-alarm/main.py`

**Interfaces:**
- `/api/readings` adds `mode` (`auto` or `manual`), `alarm_condition` (latest valid strict AND threshold result), and `led_on` (current GPIO output state).
- `POST /api/control` accepts one URL-encoded `action` value: `mode_auto`, `mode_manual`, `led_on`, or `led_off`.
- Valid commands return JSON status; invalid method/action returns an error without state mutation.

- [x] Add `control_mode` defaulting to `auto` and `manual_led_on` defaulting to `False`.
- [x] Add a single state transition helper that changes mode/manual state, writes the output, and applies the latest valid threshold result on return to auto (or off when no valid sample exists).
- [x] Update `sample_sensor()` to retain the last valid automatic threshold value but only write GPIO23 when `control_mode == 'auto'`.
- [x] Extend `readings_json()` with independent `alarm_condition`, `mode`, and `led_on` fields.
- [x] Route `POST /api/control` through strict method/action validation; preserve existing GET routes and request-size handling.
- [x] Run `python scripts/device.py deploy project-01 --port /dev/cu.usbserial-0001 --dry-run` to confirm the deployment manifest, local config, and MicroPython source syntax are accepted.

### Task 2: Add the web control interface

**Files:**
- Modify: `projects/01-temperature-humidity-alarm/main.py` (embedded `PAGE`)
- Modify: `projects/01-temperature-humidity-alarm/index.html`

**Interfaces:**
- The web page uses `POST /api/control` with the actions defined in Task 1.
- Refresh uses `GET /api/readings` and renders mode, automatic condition, and actual LED output.

- [x] Add automatic/manual mode controls plus manual ON/OFF buttons; disable ON/OFF controls outside manual mode.
- [x] Show mode and actual LED output independently from the automatic threshold result.
- [x] On each command, disable controls while pending, send the selected action, then refresh authoritative API state; show request failure without presenting a false state.
- [x] Synchronize the complete embedded page/code in the tutorial with the deployable `main.py` source.
- [x] Confirm `git diff --check` and deployment dry-run succeed.

### Task 3: Update tutorial, verify on ESP32, and publish

**Files:**
- Modify: `projects/01-temperature-humidity-alarm/index.html`
- Modify: `projects/index.html`
- Modify: `README.md`
- Modify: `docs/validation.md`

- [x] Explain startup mode, manual controls, automatic alarm pause in manual mode, and immediate threshold re-evaluation when returning to automatic.
- [x] Enumerate the serial port and deploy the project to the connected ESP32.
- [x] From the computer, request `/` and `/api/readings`; manually issue auto/manual/on/off commands and confirm returned mode and LED state.
- [x] Read GPIO23 after an ON and OFF command; report the physical LED as visually verified only if it is actually observed.
- [x] Regenerate `dist/esp32-learning-tutorial.zip` and confirm the project files are included without private Wi-Fi configuration.
- [x] Update the validation record with observed commands/results and limitations; do not claim threshold-triggered alarm unless observed.
- [ ] Commit and push the project update to the existing public repository.

## Verification Boundary

No automated tests are added or run. Verification uses the existing deployment dry-run, device deployment's source compilation and upload hash check, and live HTTP/API plus GPIO observations where the connected device permits.