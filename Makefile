# Kiddo Assist — Makefile (Iteration 6 / Phase 3)
# Recurring release gate from SDLC-IMPLEMENTATION-PLAN.md §7.
# Every iteration closes with `make eval`.

.PHONY: all eval test clean lint docker-build docker-up

# Default target
all: eval

# ---------------------------------------------------------------------------
# Recurring eval gate (guide §11.3 + SDLC §7)
# ---------------------------------------------------------------------------
eval:
	@echo "🧪 Running Kiddo Assist evaluation suite..."
	@python eval/run_eval.py

# ---------------------------------------------------------------------------
# Unit + integration tests (pytest — guide §11.1–11.2)
# ---------------------------------------------------------------------------
test:
	@echo "🧪 Running pytest suite..."
	@python -m pytest tests/ -q --tb=short

# ---------------------------------------------------------------------------
# Clean artifacts (no data, only caches / .pyc)
# ---------------------------------------------------------------------------
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

# ---------------------------------------------------------------------------
# Docker build / up (Iteration 0 / Iteration 17 deployment)
# ---------------------------------------------------------------------------
docker-build:
	docker compose build

docker-up:
	docker compose up -d

# ---------------------------------------------------------------------------
# Seed the dev catalog (Iteration 1) — idempotent
# ---------------------------------------------------------------------------
seed:
	@echo "📦 Seeding dev catalog..."
	@python -c "import sys; sys.path.insert(0,'services/ingester'); from seed import seed; seed(embed=True, rebuild_vectors=True); print('Seed complete.')"
