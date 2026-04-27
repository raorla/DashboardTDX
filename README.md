# iExec TDX Dashboard

Real-time analytics dashboard for iExec TDX (Trustless Data Exchange) workerpools on Arbitrum Mainnet and Sepolia.

## Features

- **Live Data**: Direct GraphQL queries to iExec subgraphs (no manual data refresh)
- **Smart Caching**: 5-minute cache for performance optimization
- **Multiple Time Ranges**: Today, 7 Days, 1 Month, 3 Months, 6 Months, or Custom date range
- **Network Switching**: Toggle between Arbitrum Mainnet and Sepolia
- **Rich Visualizations**:
  - Tasks per day (stacked bar chart)
  - Apps breakdown (horizontal bar)
  - Status distribution (doughnut)
  - Top requesters & apps tables
- **Data Export**: Download filtered tasks as CSV
- **Source Indicator**: Shows whether data is from Live (🟢 green), Cache (🟡 yellow), or CSV fallback (🔴 red)

## Local Setup

### Requirements

- Python 3.8+
- pip

### Installation

```bash
cd tdx_dashboard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running Locally

```bash
.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8050 --reload
```

Then open http://127.0.0.1:8050

## Deployment on Vercel

### Prerequisites

- GitHub repo containing the code
- Vercel account

### Steps

1. **Push to GitHub** (ensure `tdx_dashboard/` folder is in the repo)
2. **Connect Vercel**:
   - Go to [vercel.com](https://vercel.com)
   - Import your repository
   - Set **Root Directory** to `tdx_dashboard`
   - Click Deploy

Vercel automatically detects:

- `vercel.json` (routing config)
- `requirements.txt` (Python dependencies)

### Post-Deployment

- Live URL will be provided (e.g., `https://yourproject.vercel.app`)
- Dashboard runs in serverless mode (no persistent cache, no CSV fallback)
- All data fetched from iExec subgraphs in real-time

## Project Structure

```
tdx_dashboard/
├── app.py                 # FastAPI backend (GraphQL queries, API endpoints)
├── templates/
│   └── index.html        # Frontend (HTML + Chart.js + JS)
├── static/
│   └── style.css         # iExec brand styling
├── requirements.txt      # Python dependencies
├── vercel.json          # Vercel routing config
└── .venv/               # Python virtual environment (local only)
```

## API Endpoints

### GET `/api/summary`

Global statistics (total, completed, failed, success rate, etc.)

**Parameters:**

- `network` (mainnet | sepolia) — default: mainnet
- `date_from` (YYYY-MM-DD) — optional
- `date_to` (YYYY-MM-DD) — optional

**Response:**

```json
{
  "source": "live",
  "total": 108,
  "completed": 87,
  "failed": 21,
  "success_rate": 80.6,
  "apps": 9,
  "requesters": 6,
  "datasets": 65
}
```

### GET `/api/tasks_per_day`

Tasks grouped by day and status.

### GET `/api/apps_breakdown`

Task counts per app with status breakdown.

### GET `/api/requesters`

Top requesters with task stats.

### GET `/api/export_csv`

Download filtered tasks as CSV file.

### GET `/api/cache_status`

Inspect cache entries and TTL status.

### POST `/api/clear_cache`

Force refresh by clearing in-memory cache.

## Data Source

- **Subgraph URLs:**
  - Arbitrum Mainnet: `https://thegraph.arbitrum.iex.ec/api/subgraphs/id/B1comLe9...`
  - Arbitrum Sepolia: `https://thegraph.arbitrum-sepolia-testnet.iex.ec/api/subgraphs/id/2GCj8gzL...`

- **Workerpools:**
  - Mainnet TDX: `0x8ef2ec3ef9535d4b4349bfec7d8b31a580e60244`
  - Sepolia TDX: `0x2956f0cb779904795a5f30d3b3ea88b714c3123f`

## Status Mapping

- **COMPLETED**: Task successfully finished
- **FAILED**: Task failed, claimed but not finished, or in revealing phase
- **OTHER**: Other statuses

## Styling

Uses iExec brand colors:

- Yellow: `#FCD15A`
- Dark: `#1D1D2C`
- Success Green: `#4ADE80`
- Fail Red: `#F87171`

Dark mode by default with responsive layout.

## Development

### Modifying Endpoints

Edit `app.py` — all endpoints are async and filter by workerpool + date range.

### Modifying Frontend

Edit `templates/index.html` (HTML + CSS + JavaScript together).

### Styling

Edit `static/style.css` (CSS variables at root).

## Troubleshooting

### "Live" source but no data?

- Check network (mainnet vs sepolia)
- Verify date range is correct (date_to must be ≥ date_from)
- Subgraph might be temporarily down → fallback to cache

### Cache not clearing?

- Click **"↻ Refresh"** button (calls `/api/clear_cache`)
- Or manually: `curl -X POST http://127.0.0.1:8050/api/clear_cache`

### Dates off by one day?

- Dashboard uses local timezone for date calculations
- Subgraph timestamps are UTC

## License

Part of iExec Platform Analysis tools.
