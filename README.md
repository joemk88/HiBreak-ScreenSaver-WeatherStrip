# Bigme Weather Strip

Stamps a clean weather dashboard onto the top of your Bigme e-ink screensaver image, refreshed at preferred frequency (recommended every 2 hrs). This is designed to work alongside the KOreader plugin [CustomisableSleepScreen](https://github.com/joemk88/customisablesleepscreen.koplugin) or [CoverProgress](https://github.com/joemk88/koreader-coverprogress) which puts your current book cover (with reading progress and stats) as the Bigme screensaver.

**How it works:** Tasker gets your GPS location on a timer and hands it to a small Python script running in Termux. The script fetches weather from Open-Meteo and draws the dashboard onto your screensaver image. Tasker handles scheduling and location (reliable in the background); Termux just does the drawing.


- Free — no API keys, no accounts.
- No `termux-location`, no Termux:API, no cron.
- Font and icon style are adjustable from Tasker.
- Weather: [Open-Meteo](https://open-meteo.com/). Mono icons: [IBM Carbon](https://carbondesignsystem.com/) (Apache-2.0). Colour icons: **Glyphs Poly** by Goran Spasojevic.

---

## You need

| App | Where | Notes |
|-----|-------|-------|
| **Termux** | F-Droid | runs the Python script |
| **Termux:Tasker** | F-Droid | lets Tasker run Termux scripts (install same source as Termux) |
| **Tasker** | Play Store | scheduling + GPS ($4.49 USD/ $7.49 AUD) |

Plus the files from this project: `weather_strip.py`, `run_weather.sh`, and `Run_Weather_Script.tsk.xml`.

---

<img width="1648" height="1648" alt="WeatherStripDemo" src="https://github.com/user-attachments/assets/2e5c49f6-04c8-4c7c-93a9-a6bceb7f70cd" />

Screenshots of WeatherStrip stamped in colour and mono on a BigMe HiBreak Pro with the KOreader plugin [CustomisableSleepScreen](https://github.com/joemk88/customisablesleepscreen.koplugin) 

---

## Part 1 — Termux

Open Termux and run these blocks.

**Install Python + imaging:**
```sh
pkg install python python-pillow
```

**Allow Tasker to run Termux scripts** (required for Termux:Tasker):
```sh
mkdir -p ~/.termux/tasker
echo "allow-external-apps = true" >> ~/.termux/termux.properties
termux-reload-settings
```

**Put the files in place.** Downloads usually land in `/sdcard/Download/`, and your browser may add a suffix (`weather_strip-3.py` etc.) — copy whatever the real name is onto the fixed names below:
```sh
cp /sdcard/Download/weather_strip.py ~/weather_strip.py
cp /sdcard/Download/run_weather.sh   ~/.termux/tasker/run_weather.sh
chmod +x ~/.termux/tasker/run_weather.sh
```

**Set your home location** (used as the header label, and as a fallback if GPS fails). Edit this one line near the top of `~/weather_strip.py`:
```python
DEFAULT_LAT, DEFAULT_LON, DEFAULT_LABEL = -33.920, 151.356, "Sydney"
```

**Test it** with any coordinates and your screensaver image path:
```sh
~/.termux/tasker/run_weather.sh -33.87 151.21 /sdcard/screensaver.jpg
tail ~/weather.log
```
You should see a `stamped: … temp=… rain=…%` line, and the image should update.

> The script reads the image at the path you pass, draws the strip on the top fifth, and writes it back. Point your Bigme screensaver at that same image.

---

## Part 2 — Termux:Tasker

Just **install the Termux:Tasker app** from F-Droid. Nothing to configure — any executable script in `~/.termux/tasker/` becomes runnable from Tasker.

---

## Part 3 — Tasker

### Import the task

1. Open **Tasker** → **Tasks** tab.
2. **Hold** the *Tasks* tab heading → **Import Task**.
3. Tap the **phone icon** (bottom-right) to browse files.
4. Select **`Run_Weather_Script.tsk.xml`** from this project.

The imported task ("Run Weather Script") already has every action wired up and passes your location, cover path, font, and icon style to `run_weather.sh`.

**After importing, open the task and check the first three actions:**
- `%Cover1` → your screensaver image path (default `/sdcard/screensaver.jpg`).
- `%Font` → by default on DroidSansMono.ttf, or pick another font name *(search your phone's available fonts on Temux with: `ls /system/fonts/` )*.
- `%Icons` → `colour` for Glyphs Poly, or  `mono` for monochrome.

### Schedule it — every 2 hours

1. Tasker → **Profiles** tab → `+` → **Time**.
2. **From** your start time (e.g. `6:00 AM`) → **To** `11:59 PM` 
3. Turn on **Repeat** → **every `2` hours**.
4. Back out → when prompted, link it to the **Run Weather Script** task.

Done — it now refreshes every 2 hours through the day.

<details>
<summary>Prefer to build the task by hand? (instead of importing)</summary>

Six actions, in order:

1. **Variables → Variable Set** — `%Cover1` = `/sdcard/screensaver.jpg`
2. **Variables → Variable Set** — `%Font` = *(DroidSansMono.tff, or another font)*
3. **Variables → Variable Set** — `%Icons` = *(`mono`, or `colour`)*
4. **Location → Get Location v2**  *(produces `%gl_coordinates`)*
5. **Variables → Variable Split** — `%gl_coordinates`, splitter `,`
6. **Plugin → Termux:Tasker** — Executable `run_weather.sh`, Arguments `%gl_coordinates1 %gl_coordinates2 %Cover1 %Font %Icons`, terminal session **OFF**.
</details>


---

## Verify it's working

After a scheduled run (or tap the Play button on the Tasker task):
```sh
tail ~/weather.log
```
Each run adds a timestamped line showing what Tasker sent, e.g.:
```
----- 2026-08-18 14:00:03 args:[-33.87 151.21 /sdcard/screensaver.jpg Roboto-Bold colour] -----
stamped: Blacktown Tue, Aug 18  temp=15 feels=16 rain=20% clouds=95 rh=83
```
If a new block appears on its own every 2 hours, it's working. Termux does **not** need to be open — Tasker wakes it for the couple of seconds each run takes.

---

Part 4 — Permissions & battery (do this or it stops firing)

Tasker wakes Termux in the background every 2 hours, and Android will kill that unless you exempt the apps. Set all of the following for all three apps — Termux, Termux:Tasker, and Tasker. Wording varies by Android build; the intent is what matters.

1. Phone Settings → Battery → App battery usage → Apps → (app) → Battery → Unrestricted. Do this for Termux, Termux:Tasker, and Tasker.

2. Phone Settings → App Background Refresh → Toggle ON for Termux, Termux:Tasker, and Tasker.

4. App info for each app → Enable all permissions + Allow Display over other Apps + Allow modify system settings + Allow Install Unknown Apps

4. Let Tasker run commands in Termux Two parts:

In Termux you already enabled external apps in Part 1 (allow-external-apps = true → termux-reload-settings).
The first time the task runs the Termux action, Android pops “Allow Termux:Tasker to run commands in Termux?” — tap Allow. If you missed it: Settings → Apps → Termux:Tasker (and Tasker) → Permissions → enable the Termux “Run commands” permission (com.termux.permission.RUN_COMMAND).

---

## Other tweaks (in `weather_strip.py`)

Near the top of `draw_dashboard()`:
- **Move the strip down / up:** the `g_top` line (`int(W * 0.016) + 25`) — raise the number to push it lower.
- **Sizes / margins:** `hfs` (header), `ih` (icons), `lfs` (labels), `vfs` (values), `side` (side margins).
- **Dark covers:** the strip auto-flips to white-on-black when the cover's top is dark. Force with `DARK=1` / `DARK=0`.
- **Update interval:** the Tasker Time profile.

---

## Credits

- Weather data: **Open-Meteo** (free, no key).
- Monochrome icons: **IBM Carbon** (Apache-2.0).
- Colour icons: **Glyphs Poly** by Goran Spasojevic.
