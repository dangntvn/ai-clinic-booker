---
title: AI Clinic Booking Agent
emoji: 🩺
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8000
pinned: false
---

# AI Clinic Booking Agent — demo API

This is the live demo deploy of the AI Clinic Booking Agent backend (see the project's main
[README.md](https://github.com/dangntvn/ai-clinic-booker) for the full write-up — architecture,
agents, evaluation harness). This Space runs the FastAPI backend only; Postgres and Qdrant are
managed external services (Neon/Supabase + Qdrant Cloud), not containers inside this Space.

- `GET /health` — liveness check.
- `POST /api/v1/...` — conversation/booking API consumed by the chat widget
  (see the `demo/deploy-vercel` branch of the frontend repo).

Required environment variables are documented in `docs/hf-space-deploy.md` in this repo
(`demo/deploy-hf-space` branch) — set them under this Space's **Settings → Repository secrets**
before the first build.
