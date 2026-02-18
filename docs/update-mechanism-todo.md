# Update Mechanism — Remaining Phases

Completed in a prior session:
- `goldflipper/utils/updater.py` — version.json fetch + semver compare
- `goldflipper/__init__.py` — `__version__` defined
- `settings_template.yaml` — `update_check.url` + `timeout_seconds`
- `goldflipper_tui.py` — `_check_for_updates()` wired into `on_mount` (fires 6 s after startup)

---

## Phase 2 — n8n Publishing Workflow

**Goal:** One webhook call from beQuiet after a build → MSI on Nextcloud + Forgejo release + version.json updated.

**Nodes to build in n8n:**

1. **Webhook trigger** (POST `/goldflipper-release`)
   - Receives: `{ "version": "0.2.4", "notes": "...", "msi_path": "C:\\...\\goldflipper-0.2.4-x64.msi" }`
   - Or: trigger manually from n8n UI after each build

2. **Read MSI file** — `Read Binary File` node
   - Input: `msi_path` from webhook body

3. **Upload MSI to Nextcloud** — HTTP Request node (WebDAV PUT)
   - `PUT https://nextcloud.zimerguz.xxx/remote.php/dav/files/USER/goldflipper-releases/goldflipper-{{ version }}-x64.msi`
   - Auth: Nextcloud app password (store in n8n credentials)
   - Body: binary MSI content

4. **Create/ensure Nextcloud public share** — HTTP Request node (OCS Share API)
   - `POST https://nextcloud.zimerguz.xxx/ocs/v2.php/apps/files_sharing/api/v1/shares`
   - Body: `path=/goldflipper-releases/goldflipper-{{ version }}-x64.msi`, `shareType=3` (public link)
   - Extract share token from response → build download URL:
     `https://nextcloud.zimerguz.xxx/index.php/s/{{ token }}/download`
   - Note: if a share already exists for the file, the API returns it — handle both create and fetch cases

5. **Write version.json to Nextcloud** — HTTP Request node (WebDAV PUT)
   - Path: `/goldflipper-releases/version.json`
   - Body (JSON string):
     ```json
     {
       "version": "{{ version }}",
       "download_url": "{{ nextcloud_share_url }}",
       "notes": "{{ notes }}"
     }
     ```
   - This file should have a **stable public share link** (create once, reuse URL forever)
     → The app's `update_check.url` in settings.yaml points to this stable link

6. **Create Forgejo release** — HTTP Request node
   - `POST https://forgejo.zimerguz.xxx/api/v1/repos/OWNER/goldflipper/releases`
   - Auth: Forgejo API token (n8n credential)
   - Body: `{ "tag_name": "v{{ version }}", "name": "v{{ version }}", "body": "{{ notes }}" }`
   - Extract `release.id` from response

7. **Upload MSI to Forgejo release** — HTTP Request node (multipart)
   - `POST https://forgejo.zimerguz.xxx/api/v1/repos/OWNER/goldflipper/releases/{{ release_id }}/assets`
   - Body: multipart form with MSI binary

8. **Respond to webhook** — Respond to Webhook node
   - Return: `{ "status": "ok", "download_url": "...", "forgejo_release": "..." }`

**Pre-requisites:**
- Create the `goldflipper-releases/` folder in Nextcloud
- Create one stable public share for `version.json` → copy that URL into each user's `settings.yaml` `update_check.url`
- Generate a Forgejo API token with `repo` scope
- Store both as n8n credentials

---

## Phase 3 — Forgejo Mirror (one-time UI setup, no code)

**Goal:** Forgejo automatically stays in sync with GitHub.

**Steps (done in Forgejo web UI):**
1. Log in as admin → **Explore → Repositories → +**
2. Choose **"Migrate"** → source: **GitHub**
3. Enter GitHub repo URL: `https://github.com/Zaroganos/goldflipper`
4. Enable **"This repository will be a mirror"**
5. Set sync interval (e.g. every 8 hours)
6. Forgejo will pull branches, tags, and commits automatically

**Result:** When you push a tag to GitHub, Forgejo picks it up within the sync interval. The n8n workflow creates the Forgejo release from the tag.

---

## Phase 4 — `build_msi.py --publish` Flag (convenience)

**Goal:** One command builds + publishes.

**Change:** Add `--publish` to `build_msi.py` argument parser.

After a successful MSI build, if `--publish` is set:
```python
import requests
webhook_url = os.environ.get("GOLDFLIPPER_RELEASE_WEBHOOK", "")
if webhook_url:
    requests.post(webhook_url, json={
        "version": version,
        "notes": args.notes or "",
        "msi_path": str(msi_path),
    }, timeout=30)
```

The webhook URL is read from an env var (set it in `.env` or Windows user environment on beQuiet) so no credentials live in the repo.

Add `--notes` argument too for the release description.

**Full publish command:**
```powershell
$env:GOLDFLIPPER_RELEASE_WEBHOOK = "https://n8n.zimerguz.xxx/webhook/goldflipper-release"
uv run python scripts/build_msi.py --publish --notes "Per-user installer scope dialog"
```

---

## Phase 5 — Per-Machine Data Path Fix (existing TODO)

**File:** `goldflipper/utils/exe_utils.py` (marked with TODO comment)

**Problem:** When installed via MSI "Everyone" (per-machine), the exe lands in
`C:\Program Files\Goldflipper\`, but `get_config_dir()`, `get_plays_root()`, and
`get_logs_dir()` all write data next to `sys.argv[0]` → non-admin users get
"Access Denied" on first launch.

**Fix:** In frozen mode, detect whether the exe is under a system directory
(`C:\Program Files\` or `C:\Program Files (x86)\`), and if so, redirect all
user-writable paths to `%LOCALAPPDATA%\Goldflipper\`:

```python
import os
_SYSTEM_DIRS = (
    os.environ.get("ProgramFiles", "C:\\Program Files"),
    os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
    os.environ.get("ProgramW6432", "C:\\Program Files"),
)

def _is_per_machine_install(exe_dir: Path) -> bool:
    exe_str = str(exe_dir).lower()
    return any(exe_str.startswith(d.lower()) for d in _SYSTEM_DIRS if d)

def _get_user_data_root() -> Path:
    """User-writable root: LOCALAPPDATA\Goldflipper for per-machine, exe dir for per-user."""
    exe_path = sys.argv[0] if sys.argv else sys.executable
    exe_dir = Path(exe_path).resolve().parent
    if _is_per_machine_install(exe_dir):
        local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(local_app_data) / "Goldflipper"
    return exe_dir
```

Then replace the inline `Path(exe_path).resolve().parent / "config"` etc. in
`get_config_dir()`, `get_plays_root()`, and `get_logs_dir()` with
`_get_user_data_root() / "config"` etc.

**Also needed:** migrate existing data if a user switches from per-user to per-machine.
This can be a first-run check: if `%LOCALAPPDATA%\Goldflipper\config\settings.yaml`
doesn't exist but `exe_dir\config\settings.yaml` does, copy it over.
