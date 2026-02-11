/**
 * Position Sizer Implementation
 * Kelly Criterion and risk-based position sizing
 */

#include "position_sizer.hpp"
#include <cmath>
#include <algorithm>

namespace trading_engine {

PositionSizer::PositionSizer(double capital,
                             double max_risk_per_trade,
                             double max_position_pct,
                             double kelly_fraction)
    : capital_(capital),
      max_risk_per_trade_(max_risk_per_trade),
      max_position_pct_(max_position_pct),
      kelly_fraction_(kelly_fraction),
      wins_(0),
      losses_(0),
      total_win_amount_(0.0),
      total_loss_amount_(0.0) {}

void PositionSizer::update_stats(double pnl) {
    if (pnl > 0) {
        ++wins_;
        total_win_amount_ += pnl;
    } else if (pnl < 0) {
        ++losses_;
        total_loss_amount_ += std::abs(pnl);
    }
}

void PositionSizer::reset_stats() {
    wins_ = 0;
    losses_ = 0;
    total_win_amount_ = 0.0;
    total_loss_amount_ = 0.0;
}

double PositionSizer::get_win_rate() const {
    int total = wins_ + losses_;
    if (total == 0) return 0.5;  // Default 50%
    return static_cast<double>(wins_) / total;
}

double PositionSizer::get_avg_win() const {
    if (wins_ == 0) return 0.0;
    return total_win_amount_ / wins_;
}

double PositionSizer::get_avg_loss() const {
    if (losses_ == 0) return 0.0;
    return total_loss_amount_ / losses_;
}

double PositionSizer::kelly_criterion() const {
    /*
     * Kelly Criterion: f* = (p * b - q) / b
     * where:
     *   p = probability of winning
     *   q = probability of losing (1 - p)
     *   b = win/loss ratio (average win / average loss)
     */
    
    double p = get_win_rate();
    double q = 1.0 - p;
    
    double avg_win = get_avg_win();
    double avg_loss = get_avg_loss();
    
    // Need enough data for reliable estimate
    if (wins_ + losses_ < 10 || avg_loss < 1e-10) {
        return 0.0;
    }
    
    double b = avg_win / avg_loss;  // Win/loss ratio
    double kelly = (p * b - q) / b;
    
    // Clamp to reasonable range [0, 1]
    kelly = std::max(0.0, std::min(1.0, kelly));
    
    // Apply fractional Kelly for safety
    return kelly * kelly_fraction_;
}

PositionInfo PositionSizer::calculate_position_size(double price,
                                                     double stop_loss,
                                                     double confidence,
                                                     double regime_multiplier) const {
    PositionInfo result;
    result.size = 0.0;
    result.risk_amount = 0.0;
    result.stop_distance = 0.0;
    result.kelly_fraction = 0.0;
    result.method = "fixed_risk";
    
    if (price <= 0 || stop_loss <= 0) {
        return result;
    }
    
    // Calculate stop distance
    result.stop_distance = std::abs(price - stop_loss);
    double stop_pct = result.stop_distance / price;
    
    if (stop_pct < 0.001) {  // Stop too tight
        result.stop_distance = price * 0.01;  // Default 1% stop
        stop_pct = 0.01;
    }
    
    // Base risk amount
    result.risk_amount = capital_ * max_risk_per_trade_;
    
    // Adjust for confidence
    double confidence_adj = std::max(0.5, std::min(1.0, confidence));
    result.risk_amount *= confidence_adj;
    
    // Adjust for market regime
    double regime_adj = std::max(0.5, std::min(1.5, regime_multiplier));
    result.risk_amount *= regime_adj;
    
    // Kelly adjustment if we have enough data
    double kelly = kelly_criterion();
    if (kelly > 0) {
        result.kelly_fraction = kelly;
        double kelly_risk = capital_ * kelly;
        // Blend fixed risk with Kelly
        result.risk_amount = (result.risk_amount + kelly_risk) / 2.0;
        result.method = "kelly_blend";
    }
    
    // Calculate position size
    if (stop_pct > 0) {
        result.size = result.risk_amount / result.stop_distance;
    }
    
    // Apply maximum position limit
    double max_position_value = capital_ * max_position_pct_;
    double position_value = result.size * price;
    
    if (position_value > max_position_value) {
        result.size = max_position_value / price;
    }
    
    return result;
}

} // namespace trading_engine
