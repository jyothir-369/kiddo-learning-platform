# Kiddo Assist

Kiddo Assist is a Docker-based educational assistant for children. It combines a FastAPI backend, a Next.js web interface, and Ollama for local language-model inference. The app supports text chat, approved video recommendations, voice responses, and a separate parent dashboard.

## Features

- Child-focused chat with a local Gemma model
- Approved video recommendations and tutorial content
- Text-to-speech responses for every answer
- Speech-to-text input
- Parent dashboard with a separate user experience
- Safety checks for user input, generated output, search results, and ingested content
- Persistent local data for profiles, vectors, audio, and model files

## Project layout

```text
services/
├── api/       # FastAPI application and assistant services
├── ingester/  # Content ingestion and catalog seeding
└── web/       # Next.js chat and parent interfaces
data/          # Persistent application data
eval/          # Evaluation scripts and fixtures
tests/         # Unit and integration tests
docker-compose.yml
.env.example
Makefile
```

## Prerequisites

- Docker Desktop with WSL2 on Windows
- At least 8 GB of available memory
- Enough disk space for the Ollama and Kokoro model files

## Quick start

1. Clone or open this repository.
2. Copy the environment template:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Edit `.env` if needed. The defaults are suitable for a first run:

   - `OLLAMA_NUM_THREADS`: set to the number of physical CPU cores
   - `GEMMA_TAG`: model tag, defaulting to `gemma3:4b`

4. Start all services:

   ```powershell
   docker compose up --build
   ```

5. Open the following URLs:

   - Web app: <http://localhost:3000>
   - Parent dashboard: <http://localhost:3000/parent>
   - API health check: <http://localhost:8000/api/health>

The first start downloads the required model files and may take several minutes.

## Try the demo

1. Open <http://localhost:3000>.
2. Ask a question such as `Why is the sky blue?`.
3. Review the explanation, approved video suggestions, and spoken response.
4. Open <http://localhost:3000/parent> to explore the parent surface.

## Useful commands

Run the test suite:

```powershell
docker compose exec api python -m pytest -q
```

Run the evaluation suite:

```powershell
docker compose exec api python eval/run_eval.py
```

Build the images without starting containers:

```powershell
docker compose build
```

Stop the running services:

```powershell
docker compose down
```

Stop services and remove their data volumes:

```powershell
docker compose down -v
```

> Warning: `docker compose down -v` deletes the named Docker volumes, including stored application data.

## Configuration

The main settings are defined in `.env.example`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_NUM_THREADS` | `4` | CPU threads used by Ollama |
| `GEMMA_TAG` | `gemma3:4b` | Ollama model used by the assistant |

The API stores persistent data in the Docker volume named `data`. The Ollama model cache is stored in the `ollama_models` volume.

## Safety and privacy

Kiddo Assist applies safety checks before content is searched, returned, or stored. Personally identifiable information is redacted from assistant responses. Video files are not copied into application storage; the app references approved content instead.

## Documentation

- `IMPLEMENTATION-GUIDE.md` — detailed implementation and deployment notes
- `kiddo-assist-product-spec.md` — product requirements
- `kiddo-assist-ux-interaction-spec.md` — interaction and UX behavior
- `kiddo-architecture.md` — architecture overview
- `README-DOCKER.md` — short Docker startup note

## Troubleshooting

### Docker is not available

Make sure Docker Desktop is running, WSL2 is enabled, and the current terminal is running from a directory inside the repository.

### The model download fails

Check your internet connection and available disk space. The first startup must download the configured Gemma model. You can also run:

```powershell
docker compose up ollama
```

Then inspect the Ollama service logs:

```powershell
docker compose logs ollama
```

### The API is unreachable

Confirm that the API container is running:

```powershell
docker compose ps
```

Then check its logs:

```powershell
docker compose logs api
```

### Reset local application data

Stop the project and remove its Docker volumes:

```powershell
docker compose down -v
docker compose up --build
```

This recreates the local data volumes and downloads the model files again.

---

## Audit Summary (2026-09-22)

This is a simple summary for easy reading. The full technical details are in `AUDIT_REPORT.md`.

### Main issue
Microphone chat does not work. The app receives audio but does not turn it into text.

### What's fine
- Text chat works
- Voice answers (text-to-speech) work
- Video suggestions work
- Safety filters work
- Database and search work

### What's broken or missing
- Microphone speech-to-text link (main gap)
- Some language files missing
- Small display bug in the web page
- Some tests use fake data

### Quick fixes needed
1. Connect microphone audio to the speech-to-text module in the chat endpoint.
2. Fix the variable name in the web page display.
3. Add a real voice test.
