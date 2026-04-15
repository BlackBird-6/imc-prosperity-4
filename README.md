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

To run the interactive visualizer:
1. Navigate to `imc4-visualizer/`.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Open your browser at **http://localhost:8050**.
