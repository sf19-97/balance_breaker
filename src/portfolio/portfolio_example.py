"""
Portfolio Management System Example Usage

This example demonstrates how to use the portfolio management system to:
1. Create and configure a portfolio orchestrator
2. Process trading signals into allocation instructions
3. Apply risk management and constraints
4. Execute trades and rebalance the portfolio
5. Track performance metrics
"""

import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Any

# Import portfolio management system
from balance_breaker.src.portfolio import (
    create_orchestrator, 
    PortfolioTracker,
    BasicMetricsCalculator,
    AdvancedMetricsCalculator,
    DrawdownConstraint,
    InstrumentConstraint,
    RiskParityAllocator
)

# Import risk management
from balance_breaker.src.risk_management.orchestrator import RiskManager


def generate_sample_signals() -> Dict[str, Dict[str, Any]]:
    """Generate some sample trading signals for demonstration"""
    current_time = datetime.datetime.now()
    
    # Sample signals for different instruments
    signals = {
        'EURUSD': {
            'instrument': 'EURUSD',
            'direction': 1,  # Long
            'strength': 0.8,
            'price': 1.1250,
            'strategy': 'TrendFollowing',
            'timestamp': current_time,
            'pip_factor': 10000
        },
        'USDJPY': {
            'instrument': 'USDJPY',
            'direction': -1,  # Short
            'strength': 0.7,
            'price': 151.50,
            'strategy': 'MeanReversion',
            'timestamp': current_time,
            'pip_factor': 100
        },
        'GBPUSD': {
            'instrument': 'GBPUSD',
            'direction': 1,  # Long
            'strength': 0.6,
            'price': 1.2450,
            'strategy': 'BreakoutSystem',
            'timestamp': current_time,
            'pip_factor': 10000
        },
        'AUDUSD': {
            'instrument': 'AUDUSD',
            'direction': 0,  # No signal
            'strength': 0.0,
            'price': 0.6480,
            'strategy': 'TrendFollowing',
            'timestamp': current_time,
            'pip_factor': 10000
        }
    }
    
    return signals


def create_custom_orchestrator() -> Any:
    """Create a customized portfolio orchestrator"""
    
    # Configuration parameters
    config = {
        'portfolio_name': 'Example Portfolio',
        'initial_capital': 100000.0,
        'base_currency': 'USD',
        'max_positions': 10,
        'max_exposure': 0.5,  # 50% max exposure
        'max_position_risk': 0.05,  # 5% max per position
        'allocation_mode': 'risk_parity',
        'rebalance_mode': 'threshold'
    }
    
    # Create orchestrator with default components
    orchestrator = create_orchestrator(config)
    
    # Add custom components
    
    # Custom risk parity allocator
    risk_parity = RiskParityAllocator({
        'min_weight': 0.1,
        'max_weight': 0.3,
        'risk_target': 0.12
    })
    orchestrator.register_allocator('risk_parity', risk_parity)
    
    # Custom drawdown constraint
    drawdown_constraint = DrawdownConstraint({
        'max_drawdown': 0.2,
        'scaling_threshold': 0.1,
        'scaling_method': 'exponential',
        'min_scale_factor': 0.3
    })
    orchestrator.register_constraint('drawdown', drawdown_constraint)
    
    # Custom instrument constraint
    instrument_constraint = InstrumentConstraint({
        'max_instrument_exposure': 0.2,
        'group_limits': {
            'forex_major': 0.7,
            'forex_cross': 0.4
        },
        'instrument_groups': {
            'EURUSD': 'forex_major',
            'USDJPY': 'forex_major',
            'GBPUSD': 'forex_major',
            'AUDUSD': 'forex_major',
            'EURJPY': 'forex_cross',
            'GBPJPY': 'forex_cross'
        }
    })
    orchestrator.register_constraint('instrument', instrument_constraint)
    
    return orchestrator


def run_portfolio_example():
    """Run the portfolio management example"""
    print("Starting Portfolio Management Example")
    print("-" * 50)
    
    # Create orchestrator and tracker
    orchestrator = create_custom_orchestrator()
    portfolio_tracker = PortfolioTracker()
    
    # Create risk manager
    risk_manager = RiskManager()
    
    # Initial portfolio state
    portfolio = orchestrator.get_portfolio_state()
    print(f"Initial Portfolio: {portfolio.name}")
    print(f"Initial Capital: ${portfolio.initial_capital:,.2f}")
    print(f"Positions: {portfolio.position_count}")
    print("-" * 50)
    
    # Process signals to generate allocation instructions
    signals = generate_sample_signals()
    print(f"Processing {len(signals)} signals...")
    
    timestamp = datetime.datetime.now()
    instructions = orchestrator.process_signals(signals, risk_manager, timestamp)
    
    print(f"Generated {len(instructions)} allocation instructions:")
    for instr in instructions:
        print(f"  {instr.action.value.capitalize()} {instr.instrument}: "
             f"Direction={instr.direction}, Size={instr.target_size:.2f}, "
             f"Price={instr.entry_price:.4f}")
    print("-" * 50)
    
    # Execute instructions
    print("Executing instructions...")
    current_prices = {s['instrument']: s['price'] for s in signals.values()}
    orchestrator.execute_instructions(instructions, current_prices, timestamp)
    
    # Track portfolio state
    portfolio = orchestrator.get_portfolio_state()
    portfolio_tracker.update(portfolio, timestamp)
    
    print(f"Portfolio after execution:")
    print(f"  Positions: {portfolio.position_count}")
    print(f"  Equity: ${portfolio.current_equity:,.2f}")
    print(f"  Cash: ${portfolio.cash:,.2f}")
    print("-" * 50)
    
    # Simulate market changes
    print("Simulating market changes...")
    new_prices = {}
    for instrument, signal in signals.items():
        # Random price change (±0.5%)
        change_pct = np.random.uniform(-0.005, 0.005)
        new_price = signal['price'] * (1 + change_pct)
        new_prices[instrument] = new_price
        print(f"  {instrument}: {signal['price']:.4f} -> {new_price:.4f} ({change_pct*100:+.2f}%)")
    
    # Update portfolio state with new prices
    timestamp = datetime.datetime.now()
    orchestrator.update_portfolio_state(new_prices, timestamp)
    
    # Track updated portfolio state
    portfolio = orchestrator.get_portfolio_state()
    portfolio_tracker.update(portfolio, timestamp)
    
    print(f"Portfolio after price changes:")
    print(f"  Equity: ${portfolio.current_equity:,.2f}")
    print(f"  Unrealized P&L: ${portfolio.unrealized_pnl:,.2f}")
    print("-" * 50)
    
    # Check for rebalancing
    print("Checking for rebalancing needs...")
    rebalance_instructions = orchestrator.rebalance(new_prices, risk_manager, timestamp)
    
    if rebalance_instructions:
        print(f"Generated {len(rebalance_instructions)} rebalancing instructions:")
        for instr in rebalance_instructions:
            print(f"  {instr.action.value.capitalize()} {instr.instrument}: "
                 f"Size={instr.target_size:.2f}, Price={instr.entry_price:.4f}")
        
        # Execute rebalancing
        print("Executing rebalance instructions...")
        orchestrator.execute_instructions(rebalance_instructions, new_prices, timestamp)
    else:
        print("No rebalancing needed at this time.")
    print("-" * 50)
    
    # Generate some additional portfolio history for better metrics
    print("Simulating additional portfolio history...")
    
    # Simulate a series of daily portfolio values over 90 days
    start_date = datetime.datetime.now() - datetime.timedelta(days=90)
    dates = [start_date + datetime.timedelta(days=i) for i in range(91)]
    
    # Create a somewhat realistic equity curve (with some randomness and trend)
    initial_equity = portfolio.initial_capital
    equity_values = [initial_equity]
    
    # Parameters for simulation
    daily_drift = 0.0003  # Small positive drift
    daily_vol = 0.007     # Daily volatility
    drawdown_period = (30, 60)  # Period for a drawdown
    
    # Generate equity curve
    for i in range(1, len(dates)):
        # Determine if in drawdown period
        in_drawdown = drawdown_period[0] <= i <= drawdown_period[1]
        
        # Adjust drift for drawdown
        if in_drawdown:
            period_drift = -0.0015  # Negative drift during drawdown
        else:
            period_drift = daily_drift
        
        # Generate daily return (random with drift)
        daily_return = np.random.normal(period_drift, daily_vol)
        
        # Calculate new equity
        new_equity = equity_values[-1] * (1 + daily_return)
        equity_values.append(new_equity)
    
    # Create equity series
    equity_series = pd.Series(equity_values, index=dates)
    
    # Create some simulated trades
    num_trades = 25
    trade_history = []
    
    for i in range(num_trades):
        # Random trade parameters
        instrument = np.random.choice(['EURUSD', 'USDJPY', 'GBPUSD', 'AUDUSD'])
        direction = np.random.choice([1, -1])
        entry_date = dates[np.random.randint(0, 70)]  # Ensure trade completes before end
        hold_days = np.random.randint(1, 15)
        exit_date = entry_date + datetime.timedelta(days=hold_days)
        
        # Determine if winning or losing trade
        is_winner = np.random.random() < 0.6  # 60% win rate
        
        # Determine P&L
        if is_winner:
            pnl = np.random.uniform(100, 800)
        else:
            pnl = -np.random.uniform(100, 500)
        
        # Create trade record
        trade = {
            'type': 'close_position',
            'instrument': instrument,
            'direction': direction,
            'timestamp': exit_date,
            'realized_pnl': pnl
        }
        
        trade_history.append(trade)
    
    # Sort trades by date
    trade_history.sort(key=lambda x: x['timestamp'])
    
    # Calculate performance metrics
    print("Calculating performance metrics...")
    basic_calculator = BasicMetricsCalculator()
    advanced_calculator = AdvancedMetricsCalculator()
    
    # Calculate benchmark returns (just for example)
    benchmark_values = [initial_equity]
    for i in range(1, len(dates)):
        # Simple benchmark with less volatility and no drawdown
        bench_return = np.random.normal(0.0002, 0.005)
        benchmark_values.append(benchmark_values[-1] * (1 + bench_return))
    
    benchmark_series = pd.Series(benchmark_values, index=dates)
    benchmark_returns = benchmark_series.pct_change().dropna()
    
    # Calculate metrics
    basic_metrics = basic_calculator.calculate(equity_series, trade_history)
    advanced_metrics = advanced_calculator.calculate(
        equity_series, trade_history, 0.02, benchmark_returns.pct_change()
    )
    
    # Print key metrics
    print("Performance Metrics:")
    print(f"  Total Return: {basic_metrics['total_return']:.2%}")
    print(f"  Annualized Return: {basic_metrics['annualized_return']:.2%}")
    print(f"  Win Rate: {basic_metrics['win_rate']:.2%}")
    print(f"  Profit Factor: {basic_metrics['profit_factor']:.2f}")
    print(f"  Max Drawdown: {basic_metrics['max_drawdown']:.2%}")
    print()
    print(f"  Sharpe Ratio: {basic_metrics['sharpe_ratio']:.2f}")
    print(f"  Sortino Ratio: {advanced_metrics['sortino_ratio']:.2f}")
    print(f"  Calmar Ratio: {advanced_metrics['calmar_ratio']:.2f}")
    print(f"  Beta: {advanced_metrics['beta']:.2f}")
    print(f"  Alpha (annual): {advanced_metrics['alpha']:.2%}")
    print("-" * 50)
    
    # Plot equity curve
    print("Plotting equity curve...")
    plt.figure(figsize=(12, 6))
    plt.plot(equity_series.index, equity_series, label='Portfolio Equity')
    plt.plot(benchmark_series.index, benchmark_series, label='Benchmark', alpha=0.7)
    plt.title('Portfolio Equity Curve')
    plt.xlabel('Date')
    plt.ylabel('Equity ($)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    # Add annotations for key metrics
    plt.annotate(f"Return: {basic_metrics['total_return']:.2%}", 
               xy=(0.02, 0.95), xycoords='axes fraction')
    plt.annotate(f"Sharpe: {basic_metrics['sharpe_ratio']:.2f}", 
               xy=(0.02, 0.91), xycoords='axes fraction')
    plt.annotate(f"Max DD: {basic_metrics['max_drawdown']:.2%}", 
               xy=(0.02, 0.87), xycoords='axes fraction')
    
    plt.tight_layout()
    plt.savefig("portfolio_equity_curve.png")
    plt.show()
    
    print("Example completed successfully!")
    print(f"Equity curve plot saved to portfolio_equity_curve.png")


if __name__ == "__main__":
    run_portfolio_example()