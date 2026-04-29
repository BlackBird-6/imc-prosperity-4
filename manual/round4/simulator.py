import numpy as np
import pandas as pd
import argparse
import matplotlib.pyplot as plt
import os

def get_payoff(option_name, paths, S_2w, S_3w, min_S_3w):
    """
    Calculate the payoff of a single unit of the option at expiry
    across all simulated paths.
    """
    if option_name == "AC":
        # Underlying
        return S_3w

    elif option_name == "AC_50_P":
        return np.maximum(50 - S_3w, 0)
    elif option_name == "AC_50_C":
        return np.maximum(S_3w - 50, 0)
    elif option_name == "AC_35_P":
        return np.maximum(35 - S_3w, 0)
    elif option_name == "AC_40_P":
        return np.maximum(40 - S_3w, 0)
    elif option_name == "AC_45_P":
        return np.maximum(45 - S_3w, 0)
    elif option_name == "AC_60_C":
        return np.maximum(S_3w - 60, 0)

    elif option_name == "AC_50_P_2":
        return np.maximum(50 - S_2w, 0)
    elif option_name == "AC_50_C_2":
        return np.maximum(S_2w - 50, 0)

    elif option_name == "AC_50_CO":
        # Chooser Option
        # At 2 weeks (S_2w), choose Call if Call > Put, else Put
        # Since strike is 50 for both and r=0, Call > Put iff S_2w > 50
        return np.where(S_2w > 50, np.maximum(S_3w - 50, 0), np.maximum(50 - S_3w, 0))

    elif option_name == "AC_40_BP":
        # Binary Put
        return np.where(S_3w < 40, 10.0, 0.0)

    elif option_name == "AC_45_KO":
        # Knock-Out Put. Barrier is 35.
        barrier = 35.0
        return np.where(min_S_3w < barrier, 0.0, np.maximum(45 - S_3w, 0))

    else:
        raise ValueError(f"Unknown option: {option_name}")

def main():
    parser = argparse.ArgumentParser(description="Simulate Brownian Motion and calculate PnL")
    parser.add_argument("--options", default="manual/round4/options.csv", help="Options data CSV")
    parser.add_argument("--input", default="manual/round4/in.csv", help="Input positions CSV")
    parser.add_argument("--sims", type=int, default=10000, help="Number of simulations (default 10,000)")
    
    # In python < 3.9 BooleanOptionalAction is not available, so we use string parsing or store_false
    parser.add_argument("--save-data", type=str, default="true", help="Save image to trials/date.png (true/false)")
    args = parser.parse_args()
    
    save_data = args.save_data.lower() in ('true', '1', 't', 'y', 'yes')

    # Read data
    try:
        opt_df = pd.read_csv(args.options)
        in_df = pd.read_csv(args.input)
    except Exception as e:
        print(f"Error reading CSV files: {e}")
        return

    # Create pricing dictionary
    prices = {}
    for _, row in opt_df.iterrows():
        prices[row['OPTION']] = {
            'bid': float(row['BID']), 
            'ask': float(row['ASK']),
            'size_bid': int(row['SIZE_BID']),
            'size_ask': int(row['SIZE_ASK'])
        }

    # GBM Parameters
    S0 = 50.0  # Assumed starting price based on AC mid
    sigma = 2.51
    TRADING_DAYS_PER_YEAR = 252
    STEPS_PER_DAY = 4
    dt = 1.0 / (TRADING_DAYS_PER_YEAR * STEPS_PER_DAY)

    steps_2w = 2 * 5 * STEPS_PER_DAY  # 40 steps
    steps_3w = 3 * 5 * STEPS_PER_DAY  # 60 steps

    import random
    import datetime
    seed = random.randint(1, 100000)
    np.random.seed(seed)
    
    # Generate log returns
    # dlnS = (r - 0.5*sigma^2)dt + sigma*sqrt(dt)*Z
    # r = 0
    drift = -0.5 * sigma**2 * dt
    vol = sigma * np.sqrt(dt)

    Z = np.random.randn(args.sims, steps_3w)
    log_returns = drift + vol * Z

    # Cumulative sum to generate price paths
    # paths shape: (sims, steps_3w)
    paths = S0 * np.exp(np.cumsum(log_returns, axis=1))

    # Extract key path points
    S_2w = paths[:, steps_2w - 1]
    S_3w = paths[:, steps_3w - 1]
    min_S_3w = np.min(paths, axis=1)

    total_expected_pnl = 0.0
    contract_size = 3000

    print(f"{'PRODUCT':<15} | {'ACTION':<6} | {'VOL':<5} | {'ENTRY':<8} | {'EXP PAYOFF':<10} | {'EXPECTED PNL':<15}")
    print("-" * 75)

    pnl_distributions = {}

    for _, row in in_df.iterrows():
        opt = row['OPTION']
        vol_held = int(row['VOLUME'])
        
        if vol_held == 0:
            continue
            
        if opt not in prices:
            print(f"Warning: {opt} not found in options data. Skipping.")
            continue
            
        # Sanity check volume against available sizes
        if vol_held > 0:
            max_vol = prices[opt]['size_ask']
            if vol_held > max_vol:
                print(f"Warning: Buy volume for {opt} ({vol_held}) exceeds available SIZE_ASK ({max_vol}). Capping at {max_vol}.")
                vol_held = max_vol
        else:
            max_vol = prices[opt]['size_bid']
            if abs(vol_held) > max_vol:
                print(f"Warning: Sell volume for {opt} ({abs(vol_held)}) exceeds available SIZE_BID ({max_vol}). Capping at -{max_vol}.")
                vol_held = -max_vol

        # Determine entry price per unit
        if vol_held > 0:
            action_str = "BUY"
            entry_price = prices[opt]['ask']
            cost = entry_price
        else:
            action_str = "SELL"
            entry_price = prices[opt]['bid']
            cost = entry_price

        # Calculate payoffs
        try:
            payoffs = get_payoff(opt, paths, S_2w, S_3w, min_S_3w)
        except ValueError as e:
            print(e)
            continue
            
        avg_payoff = np.mean(payoffs)

        # Calculate PnL per unit per trial
        if vol_held > 0:
            pnl_per_trial = (payoffs - cost) * vol_held * contract_size
            pnl_per_unit = avg_payoff - cost
        else:
            pnl_per_trial = (cost - payoffs) * abs(vol_held) * contract_size
            pnl_per_unit = cost - avg_payoff

        position_pnl = pnl_per_unit * abs(vol_held) * contract_size
        total_expected_pnl += position_pnl
        
        pnl_distributions[opt] = pnl_per_trial

        print(f"{opt:<15} | {action_str:<6} | {abs(vol_held):<5} | {entry_price:<8.3f} | {avg_payoff:<10.3f} | {position_pnl:>12.2f}")

    print("-" * 75)
    print(f"TOTAL EXPECTED PNL: {total_expected_pnl:,.2f}")

    # Plotting
    print("Generating plots...")
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(14, 20), gridspec_kw={'height_ratios': [3, 1, 2, 2]})
    fig.suptitle(f"Aether Crystal Options Simulation | Sims: {args.sims} | Seed: {seed}", fontsize=16, fontweight='bold')

    # Plot 1: Asset Paths (plot up to 500 to avoid freezing)
    num_paths_to_plot = min(args.sims, 500)
    plot_paths = np.hstack([np.full((num_paths_to_plot, 1), S0), paths[:num_paths_to_plot]])
    plot_time = np.arange(steps_3w + 1)
    
    ax1.plot(plot_time, plot_paths.T, color='blue', alpha=0.05)
    ax1.set_title(f"AETHER_CRYSTAL Price Paths ({num_paths_to_plot} sample paths)")
    ax1.set_xlabel("Steps (4 per day)")
    ax1.set_ylabel("Price")
    ax1.grid(True, alpha=0.3)

    # Plot 2: Input Portfolio Table
    ax2.axis('off')
    input_cell_text = []
    input_row_labels = []
    for _, row in in_df.iterrows():
        opt = row['OPTION']
        vol = int(row['VOLUME'])
        if vol != 0:
            input_cell_text.append([str(vol)])
            input_row_labels.append(opt)
    
    if not input_cell_text:
        input_cell_text = [["No active positions"]]
        input_row_labels = ["-"]

    in_table = ax2.table(cellText=input_cell_text,
                         rowLabels=input_row_labels,
                         colLabels=["VOLUME"],
                         loc='center',
                         cellLoc='center',
                         colWidths=[0.1])
    in_table.auto_set_font_size(False)
    in_table.set_fontsize(12)
    in_table.scale(1, 1.8)
    ax2.set_title("Input Portfolio (in.csv)", pad=10, fontsize=12)

    # Plot 3: Table of PnL percentiles
    ax3.axis('off')
    if pnl_distributions:
        labels = list(pnl_distributions.keys())
        data = [pnl_distributions[label] for label in labels]
        
        # Add total portfolio PnL
        total_pnl_per_trial = np.sum(data, axis=0)
        labels.append("TOTAL PORTFOLIO")
        data.append(total_pnl_per_trial)
        
        # Add BATCHED 100 TOTAL PORTFOLIO AVG
        batch_size = 100
        num_full_batches = len(total_pnl_per_trial) // batch_size
        if num_full_batches > 0:
            batched_data = np.mean(total_pnl_per_trial[:num_full_batches * batch_size].reshape(-1, batch_size), axis=1)
            labels.append("100-BATCHED PORTFOLIO AVG")
            data.append(batched_data)
        elif len(total_pnl_per_trial) > 0:
            labels.append("100-BATCHED PORTFOLIO AVG")
            data.append(np.array([np.mean(total_pnl_per_trial)]))
        
        percentile_names = ['Mean', 'Min', '1%', '10%', '25%', '50%', '75%', '90%', '99%', 'Max']
        percentiles_to_calc = [0, 1, 10, 25, 50, 75, 90, 99, 100]
        
        cell_text = []
        for d in data:
            row_vals = [f"{np.mean(d):,.0f}"]
            for p in percentiles_to_calc:
                val = np.percentile(d, p)
                row_vals.append(f"{val:,.0f}")
            cell_text.append(row_vals)
            
        table = ax3.table(cellText=cell_text,
                          rowLabels=labels,
                          colLabels=percentile_names,
                          loc='center',
                          cellLoc='right')
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 1.8)
        ax3.set_title("PnL Distribution Percentiles (Across all trials)", pad=20, fontsize=12)

        # Plot 4: Batched Mean Portfolio PnL
        ax4.axis('off')
        batch_size = 100
        max_trials_to_batch = min(args.sims, 5000)
        
        batch_labels = []
        batch_means = []
        
        for i in range(0, max_trials_to_batch, batch_size):
            end_idx = min(i + batch_size, max_trials_to_batch)
            batch_data = total_pnl_per_trial[i:end_idx]
            batch_mean = np.mean(batch_data)
            
            batch_labels.append(f"{i+1}-{end_idx}")
            batch_means.append(f"{batch_mean:,.0f}")
        
        # Reshape into multiple columns if there are many batches
        num_batches = len(batch_labels)
        cols_pairs = 5
        rows = (num_batches + cols_pairs - 1) // cols_pairs
        
        batch_cell_text = []
        for r in range(rows):
            row_data = []
            for c in range(cols_pairs):
                idx = c * rows + r
                if idx < num_batches:
                    row_data.extend([batch_labels[idx], batch_means[idx]])
                else:
                    row_data.extend(["", ""])
            batch_cell_text.append(row_data)
            
        col_labels = ["Trials", "Mean PnL"] * cols_pairs
        col_widths = [0.1, 0.15] * cols_pairs
            
        batch_table = ax4.table(cellText=batch_cell_text,
                                colLabels=col_labels,
                                loc='center',
                                cellLoc='center',
                                colWidths=col_widths)
        batch_table.auto_set_font_size(False)
        batch_table.set_fontsize(10)
        batch_table.scale(1, 1.5)
        
        # Color the Mean PnL cells
        for r in range(rows):
            for c in range(cols_pairs):
                idx = c * rows + r
                if idx < num_batches:
                    mean_val = float(batch_means[idx].replace(',', ''))
                    color = '#d4edda' if mean_val > 0 else '#f8d7da' if mean_val < 0 else 'white'
                    batch_table[(r + 1, c * 2 + 1)].set_facecolor(color)
                    
        ax4.set_title("Batched Mean Portfolio PnL (First 5000 trials)", pad=20, fontsize=12)

    else:
        ax3.text(0.5, 0.5, "No positions to plot", ha='center', va='center')
        ax4.axis('off')
        ax4.text(0.5, 0.5, "No positions to plot", ha='center', va='center')

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    if save_data:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        trials_dir = os.path.join(os.path.dirname(__file__), "trials")
        os.makedirs(trials_dir, exist_ok=True)
        plot_path = os.path.join(trials_dir, f"{timestamp}.png")
    else:
        plot_path = os.path.join(os.path.dirname(__file__), "simulation_results.png")
        
    plt.savefig(plot_path, dpi=300)
    print(f"Plot saved to: {plot_path}")

if __name__ == '__main__':
    main()
