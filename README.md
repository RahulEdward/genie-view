# Genie View

A modular trading platform with Angel One broker integration, featuring real-time market data, historical charts, and WebSocket streaming.

## Features

- **Modular Broker Architecture**: Easily extensible to support multiple brokers
- **Angel One Integration**: Full REST API integration (no SDK dependency)
- **Real-time Data**: WebSocket streaming for live quotes
- **Historical Data**: OHLC candle data with multiple timeframes
- **Option Chain**: Options data with Greeks calculation
- **OpenAlgo Compatible**: API format compatible with OpenAlgo

## Tech Stack

### Backend
- FastAPI (Python 3.12+)
- SQLAlchemy (async) with SQLite/PostgreSQL
- Redis for caching
- WebSocket support

### Frontend
- React with Vite
- TradingView Lightweight Charts
- Real-time WebSocket updates

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/           # REST API endpoints
│   │   ├── brokers/       # Broker adapters (Angel One, etc.)
│   │   ├── db/            # Database configuration
│   │   ├── models/        # SQLAlchemy models & Pydantic schemas
│   │   ├── services/      # Business logic
│   │   ├── utils/         # Utilities (cache, logger, greeks)
│   │   └── websocket/     # WebSocket handlers
│   ├── tests/             # Test suite
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── services/      # API services
│   │   └── hooks/         # Custom hooks
│   └── package.json
└── .kiro/specs/           # Feature specifications
```

## Getting Started

### Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

Create `.env` file:
```env
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///./trading.db
REDIS_URL=redis://localhost:6379/0
```

Run the server:
```bash
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

- `POST /api/v1/auth/login` - Broker login
- `GET /api/v1/history` - Historical OHLC data
- `GET /api/v1/quotes/{symbol}` - Real-time quotes
- `GET /api/v1/optionchain/{underlying}` - Option chain
- `GET /api/v1/search` - Symbol search
- `WS /ws/market` - WebSocket for live data

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| DEBUG | Enable debug mode | false |
| DATABASE_URL | Database connection string | sqlite |
| REDIS_URL | Redis connection string | localhost:6379 |
| HOST | Server host | 0.0.0.0 |
| PORT | Server port | 8000 |

## License

MIT
