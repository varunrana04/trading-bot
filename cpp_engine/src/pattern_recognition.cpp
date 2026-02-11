/**
 * Pattern Recognition Implementation
 * High-performance candlestick pattern detection
 */

#include "pattern_recognition.hpp"
#include <cmath>
#include <algorithm>

namespace trading_engine {

PatternRecognition::PatternRecognition(double body_min_ratio, double wick_max_ratio)
    : body_min_ratio_(body_min_ratio), wick_max_ratio_(wick_max_ratio) {}

// Helper functions
double PatternRecognition::body_size(const Bar& bar) const {
    return std::abs(bar.close - bar.open);
}

double PatternRecognition::upper_wick(const Bar& bar) const {
    return bar.high - std::max(bar.open, bar.close);
}

double PatternRecognition::lower_wick(const Bar& bar) const {
    return std::min(bar.open, bar.close) - bar.low;
}

double PatternRecognition::total_range(const Bar& bar) const {
    return bar.high - bar.low;
}

bool PatternRecognition::is_bullish(const Bar& bar) const {
    return bar.close > bar.open;
}

bool PatternRecognition::is_bearish(const Bar& bar) const {
    return bar.close < bar.open;
}

// Doji pattern - small body, long wicks
bool PatternRecognition::is_doji(const Bar& bar) const {
    double range = total_range(bar);
    if (range < 1e-10) return false;
    
    double body = body_size(bar);
    double body_ratio = body / range;
    
    // Doji has very small body (< 10% of range)
    return body_ratio < 0.1;
}

// Hammer - small body at top, long lower wick (bullish reversal)
bool PatternRecognition::is_hammer(const std::vector<Bar>& bars, size_t idx) const {
    if (idx < 5 || idx >= bars.size()) return false;
    
    const Bar& bar = bars[idx];
    double range = total_range(bar);
    if (range < 1e-10) return false;
    
    double body = body_size(bar);
    double lower = lower_wick(bar);
    double upper = upper_wick(bar);
    
    // Check hammer conditions
    bool small_body = body < range * 0.35;
    bool long_lower_wick = lower > body * 2.0;
    bool small_upper_wick = upper < body * 0.5;
    
    if (!(small_body && long_lower_wick && small_upper_wick)) return false;
    
    // Verify downtrend (previous 5 bars)
    double trend_sum = 0;
    for (size_t i = idx - 5; i < idx; ++i) {
        trend_sum += bars[i].close - bars[i].open;
    }
    
    return trend_sum < 0;  // Should be in a downtrend
}

// Shooting Star - small body at bottom, long upper wick (bearish reversal)
bool PatternRecognition::is_shooting_star(const std::vector<Bar>& bars, size_t idx) const {
    if (idx < 5 || idx >= bars.size()) return false;
    
    const Bar& bar = bars[idx];
    double range = total_range(bar);
    if (range < 1e-10) return false;
    
    double body = body_size(bar);
    double lower = lower_wick(bar);
    double upper = upper_wick(bar);
    
    // Check shooting star conditions
    bool small_body = body < range * 0.35;
    bool long_upper_wick = upper > body * 2.0;
    bool small_lower_wick = lower < body * 0.5;
    
    if (!(small_body && long_upper_wick && small_lower_wick)) return false;
    
    // Verify uptrend (previous 5 bars)
    double trend_sum = 0;
    for (size_t i = idx - 5; i < idx; ++i) {
        trend_sum += bars[i].close - bars[i].open;
    }
    
    return trend_sum > 0;  // Should be in an uptrend
}

// Engulfing pattern
int PatternRecognition::is_engulfing(const std::vector<Bar>& bars, size_t idx) const {
    if (idx < 1 || idx >= bars.size()) return 0;
    
    const Bar& curr = bars[idx];
    const Bar& prev = bars[idx - 1];
    
    // Bullish engulfing: prev bearish, curr bullish, curr body engulfs prev
    if (is_bearish(prev) && is_bullish(curr)) {
        if (curr.open < prev.close && curr.close > prev.open) {
            return 1;  // Bullish
        }
    }
    
    // Bearish engulfing: prev bullish, curr bearish, curr body engulfs prev
    if (is_bullish(prev) && is_bearish(curr)) {
        if (curr.open > prev.close && curr.close < prev.open) {
            return -1;  // Bearish
        }
    }
    
    return 0;
}

// Three White Soldiers - three consecutive bullish candles
bool PatternRecognition::is_three_soldiers(const std::vector<Bar>& bars, size_t idx) const {
    if (idx < 2 || idx >= bars.size()) return false;
    
    const Bar& c1 = bars[idx - 2];
    const Bar& c2 = bars[idx - 1];
    const Bar& c3 = bars[idx];
    
    // All three must be bullish with strong bodies
    if (!is_bullish(c1) || !is_bullish(c2) || !is_bullish(c3)) return false;
    
    // Each close higher than previous
    if (c2.close <= c1.close || c3.close <= c2.close) return false;
    
    // Each open within previous body
    if (c2.open < c1.open || c2.open > c1.close) return false;
    if (c3.open < c2.open || c3.open > c2.close) return false;
    
    // Small upper wicks
    double r1 = total_range(c1), r2 = total_range(c2), r3 = total_range(c3);
    if (r1 > 0 && upper_wick(c1) / r1 > 0.3) return false;
    if (r2 > 0 && upper_wick(c2) / r2 > 0.3) return false;
    if (r3 > 0 && upper_wick(c3) / r3 > 0.3) return false;
    
    return true;
}

// Three Black Crows - three consecutive bearish candles
bool PatternRecognition::is_three_crows(const std::vector<Bar>& bars, size_t idx) const {
    if (idx < 2 || idx >= bars.size()) return false;
    
    const Bar& c1 = bars[idx - 2];
    const Bar& c2 = bars[idx - 1];
    const Bar& c3 = bars[idx];
    
    // All three must be bearish
    if (!is_bearish(c1) || !is_bearish(c2) || !is_bearish(c3)) return false;
    
    // Each close lower than previous
    if (c2.close >= c1.close || c3.close >= c2.close) return false;
    
    // Each open within previous body
    if (c2.open > c1.open || c2.open < c1.close) return false;
    if (c3.open > c2.open || c3.open < c2.close) return false;
    
    // Small lower wicks
    double r1 = total_range(c1), r2 = total_range(c2), r3 = total_range(c3);
    if (r1 > 0 && lower_wick(c1) / r1 > 0.3) return false;
    if (r2 > 0 && lower_wick(c2) / r2 > 0.3) return false;
    if (r3 > 0 && lower_wick(c3) / r3 > 0.3) return false;
    
    return true;
}

// Morning Star - bullish reversal (3 candle pattern)
bool PatternRecognition::is_morning_star(const std::vector<Bar>& bars, size_t idx) const {
    if (idx < 2 || idx >= bars.size()) return false;
    
    const Bar& c1 = bars[idx - 2];  // First candle - bearish
    const Bar& c2 = bars[idx - 1];  // Second candle - small body (star)
    const Bar& c3 = bars[idx];      // Third candle - bullish
    
    // First must be bearish, third must be bullish
    if (!is_bearish(c1) || !is_bullish(c3)) return false;
    
    // Middle candle should have small body
    double r2 = total_range(c2);
    if (r2 > 0 && body_size(c2) / r2 > 0.4) return false;
    
    // Gap down from first to second
    if (c2.high > c1.low) return false;
    
    // Third candle closes above midpoint of first
    double c1_mid = (c1.open + c1.close) / 2;
    if (c3.close < c1_mid) return false;
    
    return true;
}

// Evening Star - bearish reversal (3 candle pattern)
bool PatternRecognition::is_evening_star(const std::vector<Bar>& bars, size_t idx) const {
    if (idx < 2 || idx >= bars.size()) return false;
    
    const Bar& c1 = bars[idx - 2];  // First candle - bullish
    const Bar& c2 = bars[idx - 1];  // Second candle - small body (star)
    const Bar& c3 = bars[idx];      // Third candle - bearish
    
    // First must be bullish, third must be bearish
    if (!is_bullish(c1) || !is_bearish(c3)) return false;
    
    // Middle candle should have small body
    double r2 = total_range(c2);
    if (r2 > 0 && body_size(c2) / r2 > 0.4) return false;
    
    // Gap up from first to second
    if (c2.low < c1.high) return false;
    
    // Third candle closes below midpoint of first
    double c1_mid = (c1.open + c1.close) / 2;
    if (c3.close > c1_mid) return false;
    
    return true;
}

// Batch detection
std::vector<PatternResult> PatternRecognition::detect_all(
    const std::vector<double>& open,
    const std::vector<double>& high,
    const std::vector<double>& low,
    const std::vector<double>& close,
    size_t lookback
) const {
    std::vector<PatternResult> results;
    
    size_t n = std::min({open.size(), high.size(), low.size(), close.size()});
    if (n < 3) return results;
    
    // Convert to Bar format
    std::vector<Bar> bars(n);
    for (size_t i = 0; i < n; ++i) {
        bars[i] = {open[i], high[i], low[i], close[i], 0.0, 0};
    }
    
    // Start from lookback
    size_t start = (n > lookback) ? n - lookback : 0;
    
    for (size_t i = start; i < n; ++i) {
        // Doji
        if (is_doji(bars[i])) {
            results.push_back({"Doji", "neutral", 0.7, static_cast<int>(i), 
                              "Indecision, potential reversal"});
        }
        
        // Hammer
        if (is_hammer(bars, i)) {
            results.push_back({"Hammer", "bullish", 0.75, static_cast<int>(i),
                              "Bullish reversal after downtrend"});
        }
        
        // Shooting Star
        if (is_shooting_star(bars, i)) {
            results.push_back({"Shooting Star", "bearish", 0.75, static_cast<int>(i),
                              "Bearish reversal after uptrend"});
        }
        
        // Engulfing
        int engulf = is_engulfing(bars, i);
        if (engulf == 1) {
            results.push_back({"Bullish Engulfing", "bullish", 0.8, static_cast<int>(i),
                              "Strong bullish reversal signal"});
        } else if (engulf == -1) {
            results.push_back({"Bearish Engulfing", "bearish", 0.8, static_cast<int>(i),
                              "Strong bearish reversal signal"});
        }
        
        // Three Soldiers
        if (is_three_soldiers(bars, i)) {
            results.push_back({"Three White Soldiers", "bullish", 0.85, static_cast<int>(i),
                              "Strong bullish continuation"});
        }
        
        // Three Crows
        if (is_three_crows(bars, i)) {
            results.push_back({"Three Black Crows", "bearish", 0.85, static_cast<int>(i),
                              "Strong bearish continuation"});
        }
        
        // Morning Star
        if (is_morning_star(bars, i)) {
            results.push_back({"Morning Star", "bullish", 0.85, static_cast<int>(i),
                              "Major bullish reversal"});
        }
        
        // Evening Star
        if (is_evening_star(bars, i)) {
            results.push_back({"Evening Star", "bearish", 0.85, static_cast<int>(i),
                              "Major bearish reversal"});
        }
    }
    
    return results;
}

// Aggregate signals
std::pair<double, double> PatternRecognition::aggregate_signals(
    const std::vector<PatternResult>& patterns,
    double min_confidence
) const {
    if (patterns.empty()) {
        return {0.0, 0.0};
    }
    
    double bullish_score = 0.0;
    double bearish_score = 0.0;
    int bullish_count = 0;
    int bearish_count = 0;
    
    for (const auto& p : patterns) {
        if (p.confidence < min_confidence) continue;
        
        if (p.type == "bullish") {
            bullish_score += p.confidence;
            ++bullish_count;
        } else if (p.type == "bearish") {
            bearish_score += p.confidence;
            ++bearish_count;
        }
    }
    
    double total = bullish_score + bearish_score;
    if (total < 1e-10) {
        return {0.0, 0.0};
    }
    
    // Signal: -1 to +1
    double signal = (bullish_score - bearish_score) / total;
    
    // Confidence based on count and score
    int total_count = bullish_count + bearish_count;
    double confidence = std::min(1.0, total / (total_count * 1.0));
    
    return {signal, confidence};
}

} // namespace trading_engine
