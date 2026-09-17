# Changelog

All notable changes to Tracks & Trails are recorded here. The project follows
[Semantic Versioning](https://semver.org/): `0.y.z` until `1.0` is declared, so a minor release
may change behaviour.

## [0.1.0] - 2026-09-14

The first release: a desktop app for downloading video and audio with
[yt-dlp](https://github.com/yt-dlp/yt-dlp), for Linux and Windows, with no Python to install.

### Downloads

- **Windows 10 and 11 (x86-64):** `Tracks-and-Trails-0.1.0-setup.exe`. It installs for your user
  only, with no administrator prompt, into `%LOCALAPPDATA%\Programs\Tracks & Trails`. ffmpeg is
  included.
- **Linux (x86-64):** `Tracks_and_Trails-0.1.0-x86_64.AppImage`. Make it executable and run it; it
  needs no installing. For a menu entry, use AppImageLauncher or Gear Lever.
- `SHA256SUMS` lists a checksum for each file.

### Before you install

- **Windows may warn you when you run the installer.** This installer is unsigned, so Microsoft
  Defender SmartScreen may show *"Windows protected your PC"* and *"Microsoft Defender SmartScreen
  prevented an unrecognized app from starting. Running this app might put your PC at risk."* If it
  appears, choose **More info**, check the app is `Tracks-and-Trails-0.1.0-setup.exe` from *Unknown
  publisher*, then choose **Run anyway**. Each new unsigned build has to establish its own
  reputation. Signing is planned before 1.0.
- **Linux needs glibc 2.36 or newer:** Debian 12, Ubuntu 24.04 LTS, or newer. Ubuntu 22.04
  is too old.
- **Linux needs ffmpeg from your distribution** to merge separate video and audio streams and to
  extract audio. Without it the app still runs and tells you what it cannot do.
- **Your system needs its usual certificate store** (`ca-certificates` on Debian and Ubuntu), which
  every desktop installation has. The app uses it rather than a bundled one, so a certificate your
  organisation added is trusted.

### What it does

- Paste, drag in, or batch-paste links, and see what each one is before downloading anything.
- Presets for the common cases, or a sortable table of every format to pick exact video and audio
  streams.
- A download queue that keeps going: set how many run at once, cancel, retry, reorder, and queue a
  cancelled download again. It survives closing the app, and survives the app being killed.
- Progress while a file is being processed after it downloads: the step by name, such as
  *Converting to audio*, with its percentage where ffmpeg can report one and the time so far where
  it cannot.
- Each download's own yt-dlp output, from *Diagnostics…* on its row or on a line that would not
  read, with a button that copies the whole log for a bug report.
- Playlists as one row per item, with unavailable items reported instead of skipped silently.
- Audio extraction, remuxing, embedded thumbnails, metadata, chapters and subtitles.
- File names built from fields (title, uploader, upload date, duration and more) in Preferences, and
  any single download renamed before it starts.
- Light and dark themes, network options, a cookie source for sites you are signed in to, and
  ffmpeg detection.
- yt-dlp's version shown in the app, with an update to the newest yt-dlp when a site breaks.
- A check once a day for a newer Tracks & Trails, which only tells you and links to the release
  page. Switch it off in Preferences. It asks GitHub for the latest release number and sends nothing
  about you.
- No telemetry and no analytics.
- Uninstalling on Windows asks whether to keep your settings and download queue. Downloaded files
  are always kept.

### Known limitations

- **Windows: closing from the taskbar does nothing while a dialog is open.** With *Add URLs* or
  *Preferences* open, Windows disables the main window and ignores *Close window* on the taskbar
  button. Close the dialog first.
- **KDE on Wayland: *Show in folder* may not raise Dolphin.** If your download folder is already
  open in a Dolphin window, the file is selected there but the window is not brought forward. Click
  Dolphin in the taskbar.

### Not in this release

- **Not every yt-dlp option is available in the app yet.** This release covers the options above;
  more of yt-dlp's options are planned for a coming update.
- **macOS is not supported.**
- **Windows Narrator has not been checked by a person.** Every control has a name and role for
  screen readers, and that is tested automatically, but how Narrator reads the app has not been
  listened to.
- Links do not open in a running copy of the app, and no file types or link handlers are
  registered.
