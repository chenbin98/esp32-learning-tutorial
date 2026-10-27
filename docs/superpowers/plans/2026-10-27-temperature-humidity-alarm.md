# Temperature Humidity Alarm Project Implementation Plan

> **For agentic workers:** This plan was approved against the project spec. Work task by task and keep the actual verification boundary explicit.

**Goal:** Add a standalone practical-project section and project 01, which reuses DHT11 readings from case 04 and turns on the D23 LED only when both strict thresholds are exceeded.

**Architecture:** Put projects in a separate `projects/` namespace, with a category page and a self-contained project folder. Extend the existing guarded uploader, package allowlist, and source/document checker to support the `project-01` namespace while preserving case behavior.

**Tech Stack:** ESP32 MicroPython 1.29.0, built-in `dht`, `network`, `socket`, `ujson`; static HTML/CSS/JavaScript; existing Python deploy/package scripts.

---

## File map

- Create `projects/index.html` for the practical-project catalog.
- Create `projects/01-temperature-humidity-alarm/project.json`, `main.py`, and `index.html`.
- Modify root `index.html` and `README.md` for the new section and deployment command.
- Modify `scripts/device.py` to resolve `project-01` from `projects/` and read `project.json`; retain current backup, hash, and rename behavior.
- Modify `scripts/package_tutorial.py` to include only the catalog and standard project files.
- Modify `scripts/check_tutorial.py` to include projects in local-link, source parity, public-file, and syntax checks.
- Modify `docs/architecture.md`, `docs/contributing.html`, and `docs/validation.md` to describe the new section and evidence boundary.
- Modify case 04's next-navigation to point to the practical-project catalog.

## Task 1: Implement the standalone ESP32 project

**Files:** create `projects/01-temperature-humidity-alarm/main.py`, `project.json`, and `index.html`.

- [ ] Copy the known working Wi-Fi connection and DHT11 sampling patterns from `examples/04-temperature-humidity/main.py`.
- [ ] Define DHT pin 2, alarm LED pin 23, LED active level 1, temperature threshold 25, humidity threshold 60, and 2500 ms DHT sampling period.
- [ ] Initialize GPIO23 as output low. After successful reads, set alarm to `temperature > 25 and humidity > 60`; turn it off otherwise.
- [ ] Define `/api/readings` state fields explicitly: `sensor_ok`, `has_reading`, nullable temperature/humidity, `alarm`, `age_ms`, and `error`. On the initial read failure return null values, `has_reading:false`, alarm false, and age null; on later errors retain last valid values/alarm, set `sensor_ok:false`, keep `has_reading:true`, and report age since last successful sample. The page labels this retained state stale/error next to the alarm state. Log errors.
- [ ] Serve a page showing temperature, humidity, thresholds, alarm LED state, and data freshness. Poll cached `/api/readings` once per second.
- [ ] Document the combined case-04 sensor/web plus threshold/LED alarm principle; wiring DHT11 VCC to 3V3 after confirming the module supports it, GND common, SIG at D2/GPIO2; LED series 330 Ω on D23/GPIO23 with polarity; Wi-Fi setup; deploy and browser URL steps; threshold edge cases; troubleshooting; acceptance and verification limits. State that this low-voltage LED is a learning demonstration, not a safety/environment monitoring device.

## Task 2: Integrate project discovery and safe deployment

**Files:** modify `scripts/device.py`, create `projects/index.html`, modify root `index.html`, `README.md`, and `docs/contributing.html`.

- [ ] Resolve ordinary numeric/name targets only under `examples/`. For IDs beginning `project-`, scan immediate `projects/*/project.json` files and match exact manifest `id`; require exactly one match, rejecting missing or duplicate IDs. Expected manifest schema: `{"id":"project-01","title":"...","files":{"main.py":"main.py"},"config":{"wifi_config.py":"wifi_config.py"}}`. Apply the same path traversal, source syntax, Wi-Fi configuration, and duplicate destination checks as case manifests.
- [ ] Keep path traversal protection, local Wi-Fi validation, backup, temporary upload, SHA-256 verification, and main-last installation unchanged.
- [ ] Add a distinct practical-project section and link project 01 from both the category page and root home page.
- [ ] Document the exact deploy command: `python scripts/device.py deploy project-01 --port /dev/cu.usbserial-0001`.

## Task 3: Integrate sharing and project documentation

**Files:** modify `scripts/package_tutorial.py`, `scripts/check_tutorial.py`, `docs/architecture.md`, and `docs/validation.md`.

- [ ] Include only `projects/index.html`, `projects/*/index.html`, `projects/*/main.py`, and `projects/*/project.json` in public packages.
- [ ] Check local links and ensure each project's embedded complete source matches its `main.py`; include project Python in syntax and secret-boundary checks.
- [ ] Keep the Wi-Fi credential file excluded from the ZIP and Git changes.
- [ ] Record deployed observations separately from logic-level expectations; only claim alarm activation if both thresholds actually occur during observation.

## Task 4: Build and hardware handoff

**Files:** verify staged diff; update `docs/validation.md` with observed results.

- [ ] Generate the public ZIP and inspect the changed-file list; do not run the automated test suite unless requested.
- [ ] Immediately enumerate serial ports; if the expected port is missing or occupied, leave hardware verification pending. If available, deploy via `project-01` and confirm startup, sensor JSON, and LED-off state under the current ambient reading.
- [ ] If environment does not satisfy both thresholds, explicitly mark physical alarm-on observation pending; do not artificially claim it.
- [ ] Review final `git diff` and `git status`, confirm the generated ZIP and staged files contain no Wi-Fi credentials, then commit and push using the user's existing publishing authorization.
