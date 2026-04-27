# iExec TDX Dashboard

Real-time analytics dashboard for iExec TDX workerpools on Arbitrum Mainnet and Sepolia.

## Features

- **Live Data**: Real-time GraphQL queries from iExec subgraphs
- **Smart Caching**: 5-minute cache for performance
- **Time Filtering**: Today, 7d, 1m, 3m, 6m, or custom date range
- **Network Tabs**: Switch between Arbitrum Mainnet and Sepolia
- **Visualizations**: Tasks per day, apps breakdown, status distribution
- **Data Export**: Download filtered tasks as CSV
- **Source Indicator**: Shows data source (Live/Cache/CSV)

## Quick Start

### Local Setup

```bash
cd tdx_dashboard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Customize if needed
.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8050 --reload
```

Open http://127.0.0.1:8050

## Configuration

Create a `.env` file (copy from `.env.example`):

```env
URL_ARB_MAINNET=https://thegraph.arbitrum.iex.ec/api/subgraphs/id/...
URL_ARB_SEPOLIA=https://thegraph.arbitrum-sepolia-testnet.iex.ec/api/subgraphs/id/...
WORKERPOOL_TDX_MAINNET=0x8ef2ec3ef9535d4b4349bfec7d8b31a580e60244
WORKERPOOL_TDX_SEPOLIA=0x2956f0cb779904795a5f30d3b3ea88b714c3123f
CACHE_TTL=300
```

**Note**: `.env` is in `.gitignore` — never commit it.

## Deploy to Vercel

1. Push to GitHub
2. Go to [vercel.com](https://vercel.com) → Import Repository
3. Set **Root Directory** to `tdx_dashboard` → Deploy
4. Add environment variables in **Settings → Environment Variables**
5. Redeploy

## Project Structure

```
tdx_dashboard/
├── app.py              # FastAPI backend
├── templates/index.html # Frontend (HTML + Chart.js)
├── static/style.css     # Styling
├── requirements.txt     # Dependencies
└── vercel.json         # Vercel config
```

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/summary` | Total, completed, failed, success rate |
| `GET /api/tasks_per_day` | Tasks grouped by day |
| `GET /api/apps_breakdown` | Task counts per app |
| `GET /api/requesters` | Top requesters |
| `GET /api/export_csv` | Download tasks as CSV |
| `POST /api/clear_cache` | Force cache refresh |

All endpoints accept: `?network=mainnet|sepolia&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`

## Status Mapping

- **COMPLETED**: Task finished successfully
- **FAILED**: Task failed, claimed but not finished, or in revealing phase
- **OTHER**: Other statuses

## Troubleshooting

**No data displayed?**
- Check date range is valid
- Verify network (mainnet vs sepolia)
- Try clicking **Refresh** button to clear cache

**Dates off by one day?**
- Dashboard uses local browser timezone
- Subgraph timestamps are UTC

## License

Part of iExec Platform Analysis tools.

