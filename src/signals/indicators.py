# src/signals/indicators.py
import numpy as np
import pandas as pd

def calculate_indicators(price_data, config=None):
    """
    Calculate indicators for signal generation.
    
    Parameters:
    -----------
    price_data : pd.DataFrame
        Price data with OHLCV columns
    config : dict, optional
        Configuration for indicators
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with calculated indicators
    """
    df = price_data.copy()
    
    # Default configuration
    default_config = {
        'moving_averages': ['sma_20', 'sma_50', 'sma_200'],
        'oscillators': ['rsi_14'],
        'volatility': ['atr_14', 'bbands_20'],
        'momentum': ['macd']
    }
    
    # Use provided config or default
    indicator_config = config or default_config
    
    # Calculate moving averages
    for ma in indicator_config.get('moving_averages', []):
        if ma.startswith('sma_'):
            period = int(ma.split('_')[1])
            df[ma] = df['close'].rolling(window=period).mean()
        elif ma.startswith('ema_'):
            period = int(ma.split('_')[1])
            df[ma] = df['close'].ewm(span=period, adjust=False).mean()
    
    # Calculate oscillators
    for osc in indicator_config.get('oscillators', []):
        if osc.startswith('rsi_'):
            period = int(osc.split('_')[1])
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            avg_gain = gain.rolling(window=period).mean()
            avg_loss = loss.rolling(window=period).mean()
            rs = avg_gain / avg_loss
            df[osc] = 100 - (100 / (1 + rs))
    
    # Calculate volatility indicators
    for vol in indicator_config.get('volatility', []):
        if vol.startswith('atr_'):
            period = int(vol.split('_')[1])
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift())
            low_close = abs(df['low'] - df['close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            df[vol] = true_range.rolling(window=period).mean()
        elif vol.startswith('bbands_'):
            period = int(vol.split('_')[1])
            std_dev = 2  # Standard 2 standard deviations
            middle = df['close'].rolling(window=period).mean()
            std = df['close'].rolling(window=period).std()
            df[f'bb_middle_{period}'] = middle
            df[f'bb_upper_{period}'] = middle + std_dev * std
            df[f'bb_lower_{period}'] = middle - std_dev * std
    
    # Calculate momentum indicators
    for mom in indicator_config.get('momentum', []):
        if mom == 'macd':
            # Default MACD parameters: 12, 26, 9
            ema12 = df['close'].ewm(span=12, adjust=False).mean()
            ema26 = df['close'].ewm(span=26, adjust=False).mean()
            df['macd_line'] = ema12 - ema26
            df['macd_signal'] = df['macd_line'].ewm(span=9, adjust=False).mean()
            df['macd_histogram'] = df['macd_line'] - df['macd_signal']
    
    return df

def calculate_derived_macro_indicators(macro_data, pairs=None):
    """
    Calculate derived macro economic indicators from base data.
    
    Parameters:
    -----------
    macro_data : pd.DataFrame
        Raw macro economic data
    pairs : list, optional
        List of currency pairs to calculate indicators for
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with derived indicators
    """
    derived = macro_data.copy()
    
    # Default list of pairs if none provided
    default_pairs = ['JP', 'AU', 'CA', 'EU', 'GB']
    target_pairs = pairs or default_pairs
    
    # Calculate yield curve spreads for each currency
    for curr in target_pairs:
        # Calculate yield spreads between 10Y and 2Y
        if f'US-{curr}_10Y' in derived.columns and f'US-{curr}_2Y' in derived.columns:
            derived[f'{curr}_yield_curve'] = derived[f'US-{curr}_10Y'] - derived[f'US-{curr}_2Y']
    
    # Calculate correlation between VIX and inflation
    if 'VIX' in derived.columns:
        for curr in target_pairs:
            # Check if inflation data exists
            if f'US-{curr}_CPI_YOY' in derived.columns:
                # Calculate 60-day rolling correlation
                vix_changes = derived['VIX'].diff()
                inflation_changes = derived[f'US-{curr}_CPI_YOY'].diff()
                
                derived[f'{curr}_VIX_INFLATION_CORR'] = vix_changes.rolling(60).corr(inflation_changes)
    
    return derived