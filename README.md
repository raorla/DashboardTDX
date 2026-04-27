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

## Environment Variables

Configuration is managed via environment variables. Create a `.env` file in the project root (copy from `.env.example`):

```bash
cp .env.example .env
```

### Available Variables

| Variable                 | Default                                      | Purpose                               |
| ------------------------ | -------------------------------------------- | ------------------------------------- |
| `URL_ARB_MAINNET`        | Mainnet subgraph URL                         | GraphQL endpoint for Arbitrum Mainnet |
| `URL_ARB_SEPOLIA`        | Sepolia subgraph URL                         | GraphQL endpoint for Arbitrum Sepolia |
| `WORKERPOOL_TDX_MAINNET` | `0x8ef2ec3ef9535d4b4349bfec7d8b31a580e60244` | TDX workerpool address on Mainnet     |
| `WORKERPOOL_TDX_SEPOLIA` | `0x2956f0cb779904795a5f30d3b3ea88b714c3123f` | TDX workerpool address on Sepolia     |
| `CACHE_TTL`              | `300`                                        | Cache time-to-live in seconds         |
| `DEBUG`                  | `False`                                      | Enable debug mode                     |

**Note**: `.env` is in `.gitignore` and should NOT be committed. Each deployment environment (local, staging, production) has its own `.env` file.

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

### Configure Environment Variables on Vercel

1. Go to your project on [vercel.com](https://vercel.com)
2. **Settings** → **Environment Variables**
3. Add variables from `.env.example`:
   - `URL_ARB_MAINNET`
   - `URL_ARB_SEPOLIA`
   - `WORKERPOOL_TDX_MAINNET`
   - `WORKERPOOL_TDX_SEPOLIA`
   - `CACHE_TTL` (optional, defaults to 300)

4. **Redeploy** for changes to take effect

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
