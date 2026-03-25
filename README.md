# Finesse

An AI-powered screen analysis pipeline for macOS. Captures screen content, processes it through vision AI models (Claude, GPT-4o), and displays results via a real-time overlay — backed by Oracle Cloud infrastructure.

## Overview

Finesse demonstrates how to build an end-to-end visual AI pipeline:

- **Screen capture daemon** — captures screen regions on macOS using Quartz, triggered by cursor position
- **Cloud upload** — pushes captures to Oracle Cloud Object Storage
- **AI processing** — Oracle VM watchers analyze images with Claude or GPT-4o Vision
- **Overlay display** — results appear as a fullscreen overlay (toggle with `Option+.`)
- **Notifications** — delivers results to your phone via Telegram or ntfy.sh

## Architecture

```
Mac                         Oracle Cloud              Oracle VM
────────────────────────    ──────────────────────    ──────────────────
Cursor → trigger zone  →→  Object Storage bucket  →→  AI pipeline
daemon.py captures          screenshot-bucket/          (Claude / GPT-4o)
screenshot silently                                      ↓
                                                    Response file
overlay.py reads  ←←←←←←  responses/ folder  ←←←←  uploaded back
Option+. shows result
```

## Project Structure

```
finesse/
├── src/
│   ├── capture/
│   │   ├── daemon.py         # Background capture daemon (runs as LaunchAgent)
│   │   └── uploader.py       # Screenshot uploader with cursor-zone triggers
│   ├── overlay/
│   │   └── display.py        # Fullscreen AI response overlay (Option+.)
│   └── pipeline/             # Oracle VM AI processing pipelines
│       ├── vision_pipeline.py    # GPT-4o vision pipeline
│       ├── content_analyzer.py   # Batch content analysis (Claude, 3-image batches)
│       ├── question_processor.py # General Q&A processor (Claude)
│       ├── code_analyzer.py      # Code analysis pipeline (GPT-4o, 4-image batches)
│       ├── gpt4o_analyzer.py     # GPT-4o specialized analyzer
│       ├── claude_analyzer.py    # Claude specialized analyzer
│       ├── alt_vision.py         # Alternative vision implementation
│       └── local_pipeline.py     # Local (no cloud) pipeline
├── config/
│   ├── com.finesse.daemon.plist  # LaunchAgent: capture daemon
│   └── com.finesse.overlay.plist # LaunchAgent: overlay display
├── scripts/
│   ├── service.sh            # Install/start/stop/status LaunchAgents
│   ├── start.sh              # Quick start script
│   ├── install_mac.sh        # Mac dependency installer
│   ├── install_vm.sh         # Oracle VM installer
│   ├── install_dependencies.sh
│   ├── setup_oracle_vm.sh
│   └── run_pipeline.sh       # Run code analysis pipeline
├── tests/                    # Test suite
├── utils/                    # Helper utilities
│   ├── manual_trigger.py     # Manually trigger a capture
│   ├── reset_state.py        # Reset watcher state
│   └── create_fixture.py     # Create test fixtures
├── docs/                     # Setup guides
├── requirements_mac.txt
└── requirements_vm.txt
```

## Requirements

### Mac
- macOS with Python 3.9+
- Oracle Cloud credentials in `~/.oci/config`
- Screen Recording permission (System Settings → Privacy & Security)

### Oracle VM
- Oracle Cloud Free Tier (E2.1.Micro instance works fine)
- `ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY`

## Quick Start

### 1. Install Mac dependencies
```bash
bash scripts/install_mac.sh
```

### 2. Configure Oracle Cloud
Follow [docs/oracle_cloud.md](docs/oracle_cloud.md) to create an Object Storage bucket and configure `~/.oci/config`.

### 3. Install services
```bash
bash scripts/service.sh install
```

Registers two LaunchAgents that auto-start on login:
- **com.finesse.daemon** — capture daemon (`src/capture/daemon.py`)
- **com.finesse.overlay** — result overlay (`src/overlay/display.py`)

### 4. Set up Oracle VM pipeline
Follow [docs/oracle_vm.md](docs/oracle_vm.md), then start a pipeline:
```bash
python3 src/pipeline/content_analyzer.py
# or
python3 src/pipeline/vision_pipeline.py
```

### 5. Phone notifications (optional)
Follow [docs/notifications.md](docs/notifications.md) to configure Telegram or ntfy.sh.

## Pipelines

| Pipeline | File | Model | Description |
|---|---|---|---|
| Vision pipeline | `vision_pipeline.py` | GPT-4o | General image-to-text analysis |
| Content analyzer | `content_analyzer.py` | Claude | Batch content extraction (3 images) |
| Question processor | `question_processor.py` | Claude | Open-ended Q&A from screen |
| Code analyzer | `code_analyzer.py` | GPT-4o | Code analysis (4-image batches) |
| Claude analyzer | `claude_analyzer.py` | Claude | Code analysis via Claude |

## Service Management

```bash
bash scripts/service.sh install    # install + auto-start on login
bash scripts/service.sh start      # start now
bash scripts/service.sh stop       # stop
bash scripts/service.sh status     # check status
bash scripts/service.sh uninstall  # remove from LaunchAgents
```

Logs:
```
/tmp/finesse_daemon_stderr.log
/tmp/finesse_overlay_stderr.log
```

## Configuration

### Mac — Oracle CLI
```bash
oci setup config
```

### Oracle VM — environment variables
```bash
export ANTHROPIC_API_KEY=your-key
export OPENAI_API_KEY=your-key          # optional
export TELEGRAM_BOT_TOKEN=your-token    # optional
export TELEGRAM_CHAT_ID=your-chat-id   # optional
export NTFY_TOPIC=your-unique-topic    # optional
```

## Tech Stack

| Component | Technology |
|---|---|
| macOS capture | Quartz / Cocoa (pyobjc) |
| Cloud storage | Oracle Cloud Object Storage |
| AI vision | Anthropic Claude, OpenAI GPT-4o |
| Notifications | Telegram Bot API, ntfy.sh |
| Mac services | launchd (LaunchAgents) |
| VM services | systemd |

## Docs

- [Deployment guide](docs/deployment.md)
- [Oracle Cloud setup](docs/oracle_cloud.md)
- [Oracle VM setup](docs/oracle_vm.md)
- [Background services](docs/background_services.md)
- [Notifications](docs/notifications.md)
- [Trigger zones](docs/trigger_zones.md)

## Cost

Runs entirely on Oracle Cloud Free Tier:
- 20 GB Object Storage
- VM.Standard.E2.1.Micro compute
- 10 TB outbound data/month

AI API costs: Claude and GPT-4o Vision are ~$0.01–0.03 per image depending on resolution.

## License

MIT
