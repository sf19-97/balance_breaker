config = {
    'risk_percent': 0.02,       # 2% risk
    'stop_pips': 50,            # 50 pip stop 
    'min_position': 0.01,       # Minimum position size
    'max_position': 5.0,        # Maximum position size
    'exposure': {
        'max_total_risk': 0.10,       # 10% max total risk
        'max_correlated_risk': 0.06,  # 6% max for correlated instruments
        'max_instruments': 5          # Max 5 open instruments
    },
    'take_profit': {
        'risk_reward_ratio': 2.5      # 2.5:1 reward to risk ratio
    },
    'adjuster': {
        'max_correlation_exposure': 0.10,  # 10% max for correlated instruments
        'correlation_threshold': 0.7,      # 0.7+ is considered highly correlated
        'reduction_factor': 0.5            # Reduce by 50% when correlated
    }
}

risk_manager = RiskManager(config)