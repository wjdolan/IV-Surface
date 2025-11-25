# Implied Volatility Surface (Streamlit App)

## Overview
- Streamlit app to fetch option chains from Yahoo Finance and visualize an interactive 3D implied volatility surface.
- Shows a spot-strike overlay on the surface; term structure and volatility curve plots are available in code but hidden by default.
- Currently supports only American-listed stocks (Yahoo Finance options coverage constraint).

## Requirements
- Python 3.9+
- Internet access (required for Yahoo Finance data)
- Dependencies: `yfinance`, `pandas`, `numpy`, `matplotlib`, `streamlit`, `seaborn`, `plotly`

## Setup
1) Create/activate a virtual environment (recommended).
2) Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
Run the Streamlit app:
```bash
streamlit run main.py
```
In the UI:
- Enter a ticker (U.S. listed), optionally switch option type (calls/puts).
- The IV surface renders interactively; drag to rotate/zoom.
- Spot strike is highlighted and labeled. Side plots can be enabled by uncommenting the relevant block in `main.py`.

## Notes
- Data quality/availability comes directly from Yahoo Finance; illiquid names or outages may yield empty or partial chains.
- No automated tests are included. Use a liquid ticker (e.g., AAPL, MSFT, XOM) to verify behavior.
