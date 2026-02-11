#pragma once

/**
 * Pattern Recognition Header
 * Candlestick pattern detection with high performance
 */

#include "common.hpp"
#include <vector>
#include <string>

namespace trading_engine {

class PatternRecognition {
public:
    PatternRecognition(double body_min_ratio = 0.6, double wick_max_ratio = 0.3);

    // Single pattern detection
    bool is_doji(const Bar& bar) const;
    bool is_hammer(const std::vector<Bar>& bars, size_t idx) const;
    bool is_shooting_star(const std::vector<Bar>& bars, size_t idx) const;
    int is_engulfing(const std::vector<Bar>& bars, size_t idx) const;  // 1=bullish, -1=bearish, 0=none
    bool is_three_soldiers(const std::vector<Bar>& bars, size_t idx) const;
    bool is_three_crows(const std::vector<Bar>& bars, size_t idx) const;
    bool is_morning_star(const std::vector<Bar>& bars, size_t idx) const;
    bool is_evening_star(const std::vector<Bar>& bars, size_t idx) const;

    // Batch detection - detects all patterns in the data
    std::vector<PatternResult> detect_all(
        const std::vector<double>& open,
        const std::vector<double>& high,
        const std::vector<double>& low,
        const std::vector<double>& close,
        size_t lookback = 100
    ) const;

    // Aggregate patterns into trading signal
    // Returns: signal (-1 to 1), confidence (0 to 1)
    std::pair<double, double> aggregate_signals(
        const std::vector<PatternResult>& patterns,
        double min_confidence = 0.7
    ) const;

private:
    double body_min_ratio_;
    double wick_max_ratio_;

    // Helper functions
    double body_size(const Bar& bar) const;
    double upper_wick(const Bar& bar) const;
    double lower_wick(const Bar& bar) const;
    double total_range(const Bar& bar) const;
    bool is_bullish(const Bar& bar) const;
    bool is_bearish(const Bar& bar) const;
};

} // namespace trading_engine
