# Running Contragest as a Windows Service

Production-grade guide for deploying the Contragest attendance system as a
24/7 native Windows service that keeps punching data, alerts, audits and clock
sync alive even when nobody is logged into the desktop application.

> **Companion guide:** [tray_agent.md](tray_agent.md) describes the system-tray
> agent that gives logged-in users a live view of this service, hide-to-tray
> behaviour for the desktop app, and one-click Start/Stop/Restart of the
> service without UAC prompts. Install both for the complete 24/7 setup:
>
> ```powershell
> .\scripts\install_service.ps1 -Silent      # boot-start service (this guide)
> .\scripts\install_tray.ps1 -RestartAgent   # logon tray agent (see tray_agent.md)
> ```

---

## 1. Recommendation

**Use the native pywin32 service (`ContragestSync`) as the primary approach.**

* Native integration with the Service Control Manager (SCM): auto-start at
  boot, `sc.exe`/`services.msc` management, configurable service account,
  Windows Recovery actions, Event Log lifecycle messages.
* No third-party runtime binary on the target machine.
* Tested on Python 3.14 with `pywin32>=312`.

**Use NSSM as the fallback** when you cannot install pywin32 on the target, or
when you want a wrapper around a raw interpreter without shipping a service
class. Both wrappers drive the same headless engine, so behaviour is
identical.

> **Why a headless service at all?**
> Contragest is a Tkinter/ttkbootstrap **desktop GUI**. A Windows service runs
> in Session 0 with no desktop and cannot show windows. The service therefore
> runs the *headless engine* — everything the desktop app starts after login
> that does not need a screen:
>
> * `BackgroundScheduler`: contract alerts (07:00), daily attendance audit
>   (06:30) + auto-correction (06:35), machine clock sync (startup + 06:15).
> * ZK machine sync loop: downloads punches from every active machine every
>   30 s (same work as the dashboard's `HRDashboard._run_machine_sync`).
> * Heartbeat + Event Log + optional HTTP health endpoint.
>
> The desktop GUI remains the interactive front-end; the service is the
> always-on engine that keeps the network database fresh.

---

## 2. Architecture

```
┌──────────────────────────── Windows Service (Session 0) ─────────────────────────────┐
│                                                                                       │
│  service_main.py  ──(no args, started by SCM)──►  contragest/win_service.py            │
│                                                      ContragestSyncService            │
│                                                      (pywin32 ServiceFramework)        │
│                                                           │                            │
│                                                           ▼                            │
│  contragest/service_engine.py  ServiceEngine (headless, no Tkinter)                   │
│      ├─ [scheduler]          BackgroundScheduler  -> alerts / audit / corrector /      │
│      │                                               clock sync (daily + startup)     │
│      ├─ [scheduler-watchdog] restarts scheduler thread if it dies (self-healing)      │
│      ├─ [machine-sync]       every N s: PointageService.download_attendance(machine)  │
│      ├─ [heartbeat]          writes logs/service_heartbeat.json + Event Log           │
│      └─ [http-health]        opt-in http://127.0.0.1:<port>/health                    │
│                                                                                       │
│  persistence: contragest.core.database -> app_config.db_custom_path (UNC share)       │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

**Threading model:** every worker is a daemon thread. `SvcStop` signals a stop
event; the engine joins workers for up to 30 s; the process then exits even if
a network call is stuck (daemon threads do not prevent process exit).

**Concurrency with the desktop app:** `PointageService.download_attendance`
deduplicates punches and uses a per-process machine lock, so the service and a
logged-in desktop app can poll simultaneously — at worst a redundant,
deduplicated download. Recommended production layout: let the service own the
24/7 polling and use the desktop app for interactive work.

---

## 3. Implementation options compared

| Option                    | Auto-start | Service account | Graceful stop | Crash restart | Event Log | Python 3.14 | Verdict |
|---------------------------|:---------:|:---------------:|:-------------:|:-------------:|:---------:|:-----------:|---------|
| **pywin32 service** (used) | ✅ SCM    | ✅ SCM          | ✅ win32event | ✅ sc failure| ✅ native | ✅ 312      | **Primary** |
| **NSSM**                  | ✅        | ✅              | ✅ console events | ✅ built-in | ⚠️ via app | ✅          | Good fallback |
| python-daemon             | ❌        | ❌              | ❌            | ❌            | ❌         | ❌          | POSIX only — **not usable on Windows** |
| sc.exe / raw `svcHost`    | ✅        | ✅              | ❌ (no code hook) | ❌ (SCM only) | ❌      | n/a         | Too low-level; no in-process control |
| Task Scheduler at logon   | ⚠️        | ⚠️              | ⚠️            | ⚠️            | ❌         | n/a         | Not a service; runs per-user; not recommended |

**pywin32 pros/cons**

* Pros: no extra binaries, native SCM + `python service_main.py install`
  handles quoting/accounts, clean `win32event` stop handshake, `servicemanager`
  lifecycle messages.
* Cons: requires installing `pywin32` in the runtime venv; the service class
  must be maintained in Python.

**NSSM pros/cons**

* Pros: battle-tested, no code changes needed, excellent for wrapping
  arbitrary executables (incl. the PyInstaller exe), built-in crash restart and
  output capture with rotation.
* Cons: ships its own binary (`nssm.exe`), stop uses console events which need
  the console-enabled `python.exe` (not `pythonw.exe`), one more component to
  patch/manage.

---

## 4. Supported environments and Python versions

* **OS**: Windows Server 2016 / 2019 / 2022, Windows 10 / 11 (64-bit).
* **Python**: 3.10–3.14. The development environment uses **3.14.0**; the
  runtime venv must match the build interpreter.
  * `pywin32>=312` provides cp314 wheels; on older interpreters pip selects the
    matching wheel automatically (`pywin32>=308` is fine for 3.8–3.13).
  * `PyInstaller>=6.11` for packaging.
* **Network**: outbound TCP **4370** to each ZK machine, outbound SMTP
  (587/465/25) for alerts, outbound HTTPS for weather/location. The database is
  accessed over SMB (`\\srv-hotix\pointage\Contragest\contragest.db`).

---

## 5. Components delivered

| File | Purpose |
|------|---------|
| `contragest/service_engine.py` | Headless engine: scheduler + machine sync + heartbeat + optional HTTP health. State machine, self-healing watchdog. |
| `contragest/win_service.py` | `ContragestSyncService` pywin32 `ServiceFramework` + SCM dispatcher entry point. |
| `contragest/service_eventlog.py` | Windows Event Log wrapper (registers source `ContragestSync`, degrades to file log without pywin32). |
| `service_main.py` | CLI: `run` / `install` / `start` / `stop` / `restart` / `status` / `healthcheck`. |
| `requirements-service.txt` | `pywin32>=308`, `pyinstaller>=6.11`. |
| `scripts/install_service.ps1` | Native-service installer: account, logon right, SCM recovery, ACLs, firewall, `service_config.json`. Silent-capable. |
| `scripts/uninstall_service.ps1` | Removes service, event source, firewall rule. |
| `scripts/install_nssm.ps1` / `uninstall_nssm.ps1` | NSSM alternative. |
| `packaging/contragest-service.spec` + `scripts/build_service.ps1` | PyInstaller onedir build. |
| `test_service_engine.py` | Unit tests for the engine (pytest). |

Operational artifacts (generated at runtime, do not edit by hand):
`logs/service_heartbeat.json`, optional `service_config.json` next to the app,
`logs/service_stdout.log` / `service_stderr.log` (NSSM).

---

## 6. Deployment checklist

### 6.1 Prerequisites
1. A Windows server/VM with a static IP reachable from the ZK machines.
2. Python 3.10–3.14 (64-bit) installed machine-wide OR a venv deployed with
   the app.
3. The Contragest files (or the PyInstaller build output) in a stable folder,
   e.g. `C:\Contragest\`.
4. A **bootstrap `contragest.db`** next to `service_main.py` whose
   `app_config.db_custom_path` points at the real network database
   (`\\srv-hotix\pointage\Contragest\contragest.db`). The engine resolves the
   active DB from this file at startup, exactly like the desktop app.

### 6.2 Build (optional — for the frozen exe)
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_service.ps1
# -> dist\ContragestSync\ContragestSync.exe  (copy this folder to the server)
```

### 6.3 Native service install
```powershell
# As Administrator, on the server:
powershell -ExecutionPolicy Bypass -File .\scripts\install_service.ps1 `
    -AppDir C:\Contragest `
    -ServiceAccount 'DOMAIN\contragest-svc' `
    -ServicePassword 'P@ssw0rd!' `
    -DataSharePath '\\srv-hotix\pointage\Contragest' `
    -HealthPort 8088 -Silent
```
Silent defaults: `LocalSystem`, `--startup auto`, sync every 30 s, no health
port.

### 6.4 NSSM alternative
```powershell
# install nssm (script auto-downloads if needed)
powershell -ExecutionPolicy Bypass -File .\scripts\install_nssm.ps1 `
    -AppDir C:\Contragest -SyncInterval 30 -HealthPort 8088
```

### 6.5 Verify
```powershell
python service_main.py status           # SCM status (RUNNING)
python service_main.py healthcheck      # heartbeat freshness (exit 0 = healthy)
Get-EventLog -LogName Application -Source ContragestSync -Newest 5   # lifecycle
Get-Content C:\Contragest\logs\contragest.log -Tail 20
```

---

## 7. Service behaviour

* **Auto-start at boot**: installed with `--startup auto` (`delayed-auto`
  optional) via the SCM.
* **Configurable service account**: `LocalSystem` (default) or
  `DOMAIN\user`/`.\user` via `-ServiceAccount`. The installer grants
  `SeServiceLogonRight` ("Log on as a service") automatically.
* **Graceful start/stop/restart**: `SvcStop` signals `hWaitStop`; the engine
  stops the scheduler and joins all workers (max 30 s) before the SCM records
  `STOPPED`. `sc.exe stop/start/restart` or `services.msc` work normally.
* **Self-restart on failure (two layers)**:
  1. *Scheduler watchdog*: if the `BackgroundScheduler` thread dies, the
     engine restarts it (see `service_engine.py:_scheduler_watchdog_loop`).
  2. *SCM recovery*: the installer sets
     `sc.exe failure ContragestSync reset= 86400 actions= restart/60000/restart/120000/restart/300000`
     so the OS restarts the process 60 s / 120 s / 300 s after each crash, with
     the counter resetting daily. `sc.exe failureflag` is set so even
     non-critical failures trigger recovery.

---

## 8. Logging and monitoring

### 8.1 File logging (rotating)
Existing `contragest/core/logging.py` writes `logs\contragest.log`
(5 MB × 5 backups) with a permission-safe rotation handler. For the service,
two env vars pin stable paths when frozen:
`CONTRAGEST_BASE_DIR`, `CONTRAGEST_LOG_DIR` (set by `service_main.py`).

### 8.2 Windows Event Log
Source `ContragestSync` (registered under
`HKLM\SYSTEM\...\Services\EventLog\Application\ContragestSync`). Lifecycle and
failure events are written by the engine (`service_eventlog.py`), plus the
standard `PYS_SERVICE_STARTED/STOPPED` messages from `servicemanager`.
```powershell
wevtutil qe Application /q:"*[System[Provider[@Name='ContragestSync']]]" /f:text /c:20
```

### 8.3 Heartbeat file
`logs\service_heartbeat.json` is rewritten every 15 s with `state`, `pid`,
`last_machine_sync`, `total_new_records`, `sync_errors`, `scheduler_alive`, …
```powershell
python service_main.py healthcheck              # human-readable, exit code
python service_main.py healthcheck --json --max-age 60
```
Exit code `0` = fresh heartbeat in `RUNNING`; `1` = stale/missing. Wire this
into Nagios/Zabbix/PRTG or a scheduled task.

### 8.4 HTTP health endpoint (opt-in)
Set `"health_port": 8088` in `service_config.json` (or `-HealthPort 8088` at
install). Serves `GET http://127.0.0.1:8088/health` with the status JSON.
The installer adds an inbound firewall rule for external probes.

### 8.5 Windows Recovery (manual equivalent)
```powershell
sc.exe failure ContragestSync reset= 86400 actions= restart/60000/restart/120000/restart/300000
sc.exe failureflag ContragestSync 1
```

---

## 9. Security and permissions

* **Least privilege**: run under a dedicated `contragest-svc` account, not
  `LocalSystem`, when the box hosts other workloads. The installer grants only:
  * `SeServiceLogonRight`,
  * `Modify` on `<AppDir>\logs`,
  * `ReadAndExecute` on `<AppDir>`,
  * `Modify` on the data share folder (NTFS + share must both be set server-side).
* **LocalSystem**: accesses the UNC share via the computer account
  `DOMAIN\<SERVERNAME>$` — grant that account on the share server.
* **Service dependency**: `LanmanWorkstation` is declared so the SCM does not
  start the service before SMB networking is ready.
* **Firewall**:
  * outbound TCP **4370** to every ZK machine (default in most configurations,
    verify the server's outbound policy),
  * outbound SMTP (587/465/25) for alert emails,
  * inbound TCP `<health_port>` only if you want external health probes.
* **Secrets**: SMTP credentials live in the `app_config` DB table; protect the
  DB share. Never store passwords in `service_config.json`.

---

## 10. Testing and validation

### 10.1 Unit tests
```powershell
\.venv\Scripts\python.exe -m pytest test_service_engine.py -v
```
Covers: state machine + double-start, heartbeat file content, machine sync
downloads each active machine, sync loop survives a failing machine, scheduler
start/stop wiring, HTTP `/health`, `healthcheck` CLI exit codes, service class
metadata. All DB/network access is mocked or disabled.

### 10.2 Foreground smoke test (no install needed)
```powershell
\.venv\Scripts\python.exe service_main.py run --no-machine-sync --no-scheduler
# Ctrl+C to stop; then in a second terminal:
\.venv\Scripts\python.exe service_main.py healthcheck
```

### 10.3 Install / uninstall verification
```powershell
# after install:
sc.exe query ContragestSync        # state RUNNING
python service_main.py status      # exit 0
python service_main.py healthcheck # exit 0
sc.exe qfailure ContragestSync     # shows recovery actions
# after uninstall:
sc.exe query ContragestSync        # SERVICE_DOES_NOT_EXIST
```

### 10.4 Startup timing
The service should reach `RUNNING` within ~5–15 s (venv import of pywin32 +
SQLAlchemy is the dominant cost). If it exceeds 30 s, check `sc.exe qc` for
`LanmanWorkstation` startup and Event Log for dependency timeouts.

### 10.5 CI/CD
Example GitHub Actions job (Windows runner):

```yaml
- name: Setup Python
  uses: actions/setup-python@v5
  with:
    python-version: "3.12"
- name: Install deps
  run: |
    python -m pip install -r requirements-service.txt
    python -m pip install -r <runtime-requirements>
- name: Test engine
  run: python -m pytest test_service_engine.py
- name: Build service exe
  run: |
    powershell -File scripts/build_service.ps1 -DistDir "$env:GITHUB_WORKSPACE\dist"
- name: Upload artifact
  uses: actions/upload-artifact@v4
  with:
    name: ContragestSync
    path: dist/ContragestSync
```
Production release flow: run the unit tests → build → deploy the artifact to
the server → run `install_service.ps1` → run the verification commands from
§10.3. Gate the release on `healthcheck` exit code 0 after a 1-minute soak.

---

## 11. Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `SERVICE NOT FOUND` on `status` | Service not installed; run `install_service.ps1`. |
| `healthcheck` exit 1 `state: STARTING` | Service just booting; wait ~10 s. |
| Heartbeat age grows, `state: RUNNING` but `last_machine_sync: None` | Machine sync disabled in `service_config.json` or `download_attendance` erroring; check `logs/contragest.log` and Event Log. |
| Service stops with "disk I/O error" | Network share dropped; the DB layer uses `TRUNCATE` journal + `busy_timeout`. SCM recovery restarts the process; also verify the share is reachable from the service account. |
| `Download attendance` also runs in the GUI → double work | Expected and deduplicated. To avoid it, set `"enable_machine_sync": false` in `service_config.json` when the desktop app always runs, or vice-versa. |
| `nssm stop` hangs | `pythonw.exe` has no console; use `python.exe` (console-enabled) so `AppStopMethodConsole` can deliver Ctrl events. |
| Service starts then immediately stops | Check Event Viewer source `ContragestSync` for a Python traceback; verify the bootstrap `contragest.db` exists next to the exe/script. |
| Frozen exe writes logs to a temp dir | `service_main.py` sets `CONTRAGEST_BASE_DIR` to the exe folder automatically; check the deploy used the onedir build, not a moved onefile. |

---

## 12. Command cheat sheet

```powershell
# install (native, silent, dedicated account, health endpoint)
powershell -File scripts\install_service.ps1 -AppDir C:\Contragest `
    -ServiceAccount DOMAIN\contragest-svc -ServicePassword '***' `
    -DataSharePath '\\srv-hotix\pointage\Contragest' -HealthPort 8088 -Silent

# tune without touching the SCM
Set-Content C:\Contragest\service_config.json @'
{ "sync_interval_seconds": 30, "health_port": 8088 }
'@
sc.exe stop ContragestSync; sc.exe start ContragestSync

# manage
sc.exe start/stop/restart ContragestSync
python service_main.py status
python service_main.py healthcheck --json

# event log
wevtutil qe Application /q:"*[System[Provider[@Name='ContragestSync']]]" /f:text /c:20

# remove
powershell -File scripts\uninstall_service.ps1 -Silent
```
