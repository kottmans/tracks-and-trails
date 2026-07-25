# Tracks & Trails

A desktop GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp) on Linux and Windows.

yt-dlp is the best media downloader available, and it is command-line only. Tracks & Trails
puts a real queue-based interface on it — presets and one-click downloads when you want
simple, and the full format table, output templates, and post-processors when you don't.

Video and audio are equally first-class.

> **Status: pre-alpha, planning only.** No code exists yet. There is nothing to install or
> run. See [ai/STATUS.md](ai/STATUS.md) for where things actually stand.

---

## Planned features

- Paste, drag, or batch-paste URLs; probe them without downloading
- Presets for the common cases, with the effective yt-dlp format selector always visible
- Full sortable format table — pick exact video and audio streams to merge
- Persistent download queue with configurable concurrency, live progress, and cancel/retry
- Queue and history survive restarts and crashes
- Audio extraction, container remux, embedded thumbnails, metadata, chapters, and subtitles
- Configurable output templates with live path preview
- In-app yt-dlp version display and update, so a broken site is fixable without waiting for us
- No telemetry, no analytics, no phone-home

## Requirements

- Linux (x86-64) or Windows 10/11 (x86-64) — both are primary, verified platforms
- ffmpeg — install from your package manager on Linux; bundled in the Windows installer

**You do not need Python installed.** Releases bundle their own interpreter, Qt, and yt-dlp
(`REL-001`). Python is how the app is built, not something you have to set up.

macOS is not supported.

## What this is not

Tracks & Trails does **not** circumvent access controls. No DRM stripping, no paywall or
geo-restriction bypass, no authentication bypass, no rate-limit evasion, no bulk scraping.
Cookie support exists so you can reach content you already have an account for — nothing
more. See [ai/REQUIREMENTS.md §8](ai/REQUIREMENTS.md) and decision `SEC-001`.

**You are responsible for having the right to download what you queue.** The application
cannot and does not verify this.

## Documentation

The project uses a structured documentation system so that human and AI contributors share
one source of truth.

| Document | Answers |
|---|---|
| [AGENTS.md](AGENTS.md) | How must an AI agent behave in this repository? |
| [ai/REQUIREMENTS.md](ai/REQUIREMENTS.md) | What must the product do? |
| [ai/ARCHITECTURE.md](ai/ARCHITECTURE.md) | How is the system designed? |
| [ai/DECISIONS.md](ai/DECISIONS.md) | Why was it designed that way? |
| [ai/IMPLEMENTATION_PLAN.md](ai/IMPLEMENTATION_PLAN.md) | In what order is it being built? |
| [ai/TASKS.md](ai/TASKS.md) | What work is ready, active, or blocked? |
| [ai/STATUS.md](ai/STATUS.md) | Where does the project stand right now? |
| [ai/REVIEWS.md](ai/REVIEWS.md) | What was reviewed, and is it ready? |
| [ai/TESTING.md](ai/TESTING.md) | What must be tested, and how? |
| [ai/PROMPTS.md](ai/PROMPTS.md) | Reusable task-launch templates (non-authoritative) |

`ai/REQUIREMENTS.md` and `ai/ARCHITECTURE.md` describe the **approved design**, not what is
built. `ai/STATUS.md` is the only document authoritative for implementation reality.

## Contributing

Not yet open to contributions — there is no code to contribute to. Contributions will be
accepted under the MIT License. If you are an AI agent working in this repository, start with
[AGENTS.md](AGENTS.md).

## License

[MIT](LICENSE) — Copyright (c) 2026 Sean Kottman. See `LIC-001` in
[ai/DECISIONS.md](ai/DECISIONS.md).

MIT covers this source. Distributed binaries additionally carry third-party obligations:
Qt/PySide6 is **LGPLv3** and must stay dynamically linked, any bundled ffmpeg build must be
**LGPL**, and yt-dlp is **Unlicense**. Those license texts ship with every release artifact.
