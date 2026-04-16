# IMC Prosperity 4 — Market Analysis Workspace

This repository contains tools, data, and documentation for the IMC Prosperity 4 challenge.

## Project Structure

### `/imc4-visualizer`
An interactive dashboard built with **Plotly Dash** to visualize market data.
- **`app.py`**: The main application for the dashboard.
- **`requirements.txt`**: Python dependencies for the visualizer.
- Features: Price charts, order book depth viewer, and market metrics (spread, volume profile, volatility, etc.).

### `/trading-data`
The primary data lake and scripted analysis folder.
- **`/ROUNDn`**: Subdirectories containing raw `;`-delimited CSV files (`prices_...` and `trades_...`) for each trading round.
- **`analyze.py`**: A Python script used for statistical analysis and generating preliminary market charts.
- **`analyze_backtest.py`**: Script for backtesting trading strategies against the provided data.

### `/prosperity-docs`
Reference materials and developer documentation.
- **`api-info.md`**: Technical details about the IMC Prosperity API and data formats.
- **`example.py`**: Boilerplate code and example trading strategy implementation.

## Getting Started

Install all dependencies from the project root:

```bash
pip install -r requirements.txt
```

To run the interactive visualizer:
1. Run: `python imc4-visualizer/app.py`
2. Open your browser at **http://localhost:8050**.

To run the backtester ([source](https://github.com/Xeeshan85/imc-prosperity-4-backtester)):
```bash
# Run — the number is the round number (--merge-pnl stitches all days into a continuous PnL curve)
prosperity4btest algos/ROUND<N>/<algo>.py <round> --merge-pnl
prosperity4btest algos/ROUND1/mean_reversion_v5.py 1 --merge-pnl

# Run and auto-open the visualizer (jmerle) in your browser
prosperity4btest algos/ROUND<N>/<algo>.py <round> --merge-pnl --vis
prosperity4btest algos/ROUND1/mean_reversion_v5.py 1 --merge-pnl --vis

# Save output log manually, then open at https://jmerle.github.io/imc-prosperity-3-visualizer
prosperity4btest algos/ROUND1/mean_reversion_v5.py 1 --out my_run.log
```

By default the backtester saves logs to `algos/ROUND1/logs/` — this folder is gitignored.
