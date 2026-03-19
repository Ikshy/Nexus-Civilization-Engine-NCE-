# Nexus Civilization Engine (NCE)

> A living AI civilization sandbox for studying emergence, coordination, conflict, and alignment.

## Overview

NCE is a research-grade multi-agent simulation platform where autonomous AI agents inhabit a synthetic world, pursue goals, form societies, wage conflicts, and develop emergent behaviors — all observable and controllable in real time.

## Architecture

```
nexus_civilization_engine/
├── backend/
│   ├── api/                    # FastAPI control plane
│   ├── simulation/
│   │   ├── world/              # World engine (grid, weather, resources)
│   │   ├── agents/             # Agent system (identity, traits, inventory)
│   │   ├── cognitive/          # Decision loop, memory, planning
│   │   ├── economy/            # Markets, trade, pricing
│   │   ├── social/             # Relationships, gossip, alliances
│   │   ├── conflict/           # War, rebellion, negotiation
│   │   ├── governance/         # Laws, courts, taxation
│   │   ├── information/        # News, rumors, misinformation
│   │   ├── analytics/          # Emergent pattern detection
│   │   └── scenarios/          # Injected scenario events
│   ├── data/
│   │   ├── models/             # SQLAlchemy ORM models
│   │   └── repositories/       # Data access layer
│   └── core/                   # Config, logging, event bus
├── frontend/                   # React dashboard
├── docker/                     # Docker configs
└── scripts/                    # Utilities
```

## Tech Stack

- **Backend**: Python 3.11, FastAPI, AsyncIO
- **Simulation**: NumPy, NetworkX, Pandas
- **Storage**: PostgreSQL, Redis
- **Frontend**: React 18, D3.js, Recharts
- **DevOps**: Docker, docker-compose

## Quick Start

### Prerequisites
- Docker + docker-compose
- Python 3.11+ (for local dev)
- Node 18+ (for frontend dev)

### Run with Docker

```bash
cp .env.example .env
docker-compose up --build
```

- API: http://localhost:8000
- Dashboard: http://localhost:3000
- API Docs: http://localhost:8000/docs

### Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm start
```

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/simulation/start` | POST | Start simulation |
| `/simulation/stop` | POST | Stop simulation |
| `/simulation/state` | GET | Get world state |
| `/simulation/tick` | POST | Advance one tick |
| `/agents` | GET | List all agents |
| `/agents/{id}` | GET | Agent details |
| `/agents/{id}/memory` | GET | Agent memory |
| `/world/map` | GET | World grid state |
| `/world/resources` | GET | Resource distribution |
| `/economy/market` | GET | Market prices |
| `/social/graph` | GET | Social network graph |
| `/analytics/metrics` | GET | Civilization metrics |
| `/scenarios/inject` | POST | Inject scenario |
| `/events/stream` | GET | SSE event stream |

## Simulation Parameters

Configure via `.env` or API:

- `WORLD_SIZE` - Grid dimensions (default: 50x50)
- `AGENT_COUNT` - Initial population (default: 200)
- `TICK_RATE` - Ticks per second (default: 10)
- `SIMULATION_SEED` - Random seed for reproducibility

## Research Features

- **Emergent analytics**: Auto-detect cooperation clusters, leadership, inequality
- **Full event logging**: Every agent decision logged with context
- **Reproducible runs**: Seed-based determinism
- **Scenario injection**: Runtime crisis events
- **Export**: Full state snapshots to JSON/CSV
