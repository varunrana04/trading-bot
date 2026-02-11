#pragma once

/**
 * Common header with shared types and utilities
 * Used across all trading engine components
 */

#include <vector>
#include <string>
#include <map>
#include <cmath>
#include <algorithm>
#include <numeric>
#include <stdexcept>

namespace trading_engine {

// Price bar structure (OHLCV)
struct Bar {
    double open;
    double high;
    double low;
    double close;
    double volume;
    long long timestamp;
};

// Pattern detection result
struct PatternResult {
    std::string name;
    std::string type;      // "bullish", "bearish", "neutral"
    double confidence;
    int index;             // Bar index where pattern detected
    std::string description;
};

// Order book level
struct PriceLevel {
    double price;
    double quantity;
};

// Position sizing result
struct PositionInfo {
    double size;
    double risk_amount;
    double stop_distance;
    double kelly_fraction;
    std::string method;
};

// Kalman filter state
struct KalmanState {
    double estimate;
    double error_estimate;
    double velocity;
};

// Utility functions
inline double safe_divide(double a, double b, double default_val = 0.0) {
    return (std::abs(b) > 1e-10) ? a / b : default_val;
}

inline double clamp(double value, double min_val, double max_val) {
    return std::max(min_val, std::min(max_val, value));
}

inline double sign(double value) {
    return (value > 0) ? 1.0 : (value < 0) ? -1.0 : 0.0;
}

} // namespace trading_engine
