# C++ Trading Engine

High-performance trading engine with Python bindings via pybind11.

## Components

| Component | Description |
|-----------|-------------|
| **PatternRecognition** | Candlestick pattern detection (Doji, Hammer, Engulfing, etc.) |
| **OrderBook** | Real-time order book with imbalance calculation |
| **Indicators** | RSI, MACD, EMA, SMA, ADX, Bollinger Bands, ATR, Stochastic, VWAP, OBV |
| **PositionSizer** | Kelly Criterion and risk-based position sizing |
| **KalmanFilter** | Price prediction and smoothing |

## Expected Performance

| Component | Speedup vs Python |
|-----------|------------------|
| Pattern Recognition | 10-50x |
| Order Book | 20-50x |
| Indicators | 10-20x |
| Kalman Filter | 20-50x |

## Prerequisites

1. **Visual Studio 2022** (or Build Tools) with C++ workload
2. **CMake 3.15+** - [Download](https://cmake.org/download/)
3. **Python 3.8+** with pip
4. **pybind11**: `pip install pybind11`

## Build Instructions

### PowerShell (Recommended)

```powershell
# From Bot_Algo directory
.\scripts\build_cpp_engine.ps1
```

### Manual Build

```powershell
cd cpp_engine
mkdir build
cd build

# Configure
cmake .. -G "Visual Studio 17 2022" -A x64 -Dpybind11_DIR=$(python -c "import pybind11; print(pybind11.get_cmake_dir())")

# Build
cmake --build . --config Release

# Copy to cpp_engine folder
copy Release\trading_engine*.pyd ..
```

## Usage

### Direct C++ Module

```python
from cpp_engine import trading_engine

# Pattern Recognition
pr = trading_engine.PatternRecognition()
patterns = pr.detect_all(open_arr, high_arr, low_arr, close_arr, lookback=100)

# Indicators
rsi = trading_engine.Indicators.rsi(close_arr, period=14)
macd = trading_engine.Indicators.macd(close_arr, 12, 26, 9)

# Order Book
book = trading_engine.OrderBook("BTCUSDT", depth_levels=20)
book.update(bids, asks)
obi = book.get_order_book_imbalance()

# Kalman Filter
smoothed = trading_engine.KalmanFilter.filter_series(prices, 0.01, 0.1)
```

### Python Wrapper (with fallback)

```python
from core.cpp_wrapper import FastIndicators, detect_patterns, is_cpp_available

# Automatically uses C++ if available, otherwise Python
if is_cpp_available():
    print("Using C++ engine")

# Detect patterns
patterns = detect_patterns(df, lookback=100)

# Calculate indicators
rsi = FastIndicators.rsi(close, period=14)
ema = FastIndicators.ema(close, period=20)
```

## Benchmark

```powershell
python scripts\benchmark_cpp_vs_python.py
```

## Directory Structure

```
cpp_engine/
├── CMakeLists.txt           # Build configuration
├── README.md                # This file
├── include/
│   ├── common.hpp           # Shared types
│   ├── pattern_recognition.hpp
│   ├── order_book.hpp
│   ├── indicators.hpp
│   ├── position_sizer.hpp
│   └── kalman_filter.hpp
├── src/
│   ├── pattern_recognition.cpp
│   ├── order_book.cpp
│   ├── indicators.cpp
│   ├── position_sizer.cpp
│   └── kalman_filter.cpp
└── bindings/
    └── python_bindings.cpp  # pybind11 bindings
```

## Troubleshooting

### CMake can't find pybind11
```powershell
pip install pybind11
# Then explicitly pass the path:
cmake .. -Dpybind11_DIR=$(python -c "import pybind11; print(pybind11.get_cmake_dir())")
```

### Visual Studio not found
Install Visual Studio 2022 Build Tools with C++ workload:
https://visualstudio.microsoft.com/downloads/

### Module won't import
Make sure the built `trading_engine.pyd` is in the `cpp_engine` folder or in your Python path.
