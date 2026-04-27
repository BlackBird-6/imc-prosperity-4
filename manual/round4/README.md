# Round 4 Options Simulator

Geometric Brownian Motion (GBM) Monte Carlo simulator as specified in the initial challenge prompt designed to price and risk-manage exotic options for the Aether Crystal manual trading challenge. 

Because the Round 4 environment features massive volatility (251% annualized), naive expected value calculations are insufficient. This simulator models the discrete price steps to accurately value path-dependent exotics (Knock-Out, Chooser, Binary) and provides deep insights into the tail-risk distributions of your portfolio.

## Getting Started

### 1. Configure your Portfolio (`in.csv`)
Edit the `in.csv` file to define the positions you want to simulate.
*   **Positive Volume**: Simulates a `BUY` order (executes at the `ASK` price).
*   **Negative Volume**: Simulates a `SELL` order (executes at the `BID` price).
*   *Note: The simulator automatically caps your volume based on the available liquidity (`SIZE_BID` / `SIZE_ASK`) found in `options.csv`.*

### 2. Run the Simulation
Execute the simulator from the command line:

```bash
python manual/round4/simulator.py
```

### 3. Analyze the Results
The simulator provides two main outputs:
1.  **Terminal Summary**: A quick overview of your Expected PnL based on the mean average of all simulated trials.
2.  **Graphical Report**: A high-resolution image saved automatically to the `manual/round4/trials/` directory. This image contains:
    *   Visual traces of the discrete price paths.
    *   A summary of your active input portfolio.
    *   A comprehensive percentile distribution table (Min, 1%, 10%, 25%, Median, 75%, 90%, 99%, Max) mapping the exact tail-risk profile of your trades.

## CLI Arguments

You can customize the simulation using the following flags:

*   `--sims <int>`: The number of Monte Carlo trials to run. Default is `10000`. (Higher numbers provide more stable means, lower numbers render faster).
*   `--save-data <true|false>`: Whether to save the graphical report with a timestamp to the `trials/` folder. Default is `true`. If set to `false`, it overwrites `simulation_results.png` in the current directory.
*   `--options <path>`: Path to the options data CSV. Default is `options.csv`.
*   `--input <path>`: Path to your portfolio configuration CSV. Default is `in.csv`.

**Example:**
```bash
python manual/round4/simulator.py --save-data false --sims 50000 
```
