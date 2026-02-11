#pragma once

/**
 * Position Sizer Header
 * Kelly Criterion and risk-based position sizing
 */

#include "common.hpp"
#include <vector>

namespace trading_engine {

class PositionSizer {
public:
    PositionSizer(double capital = 1000.0,
                  double max_risk_per_trade = 0.02,
                  double max_position_pct = 0.20,
                  double kelly_fraction = 0.25);

    // Update win/loss statistics for Kelly calculation
    void update_stats(double pnl);
    void reset_stats();

    // Kelly Criterion calculation
    // f* = (p * b - q) / b
    double kelly_criterion() const;

    // Calculate optimal position size
    PositionInfo calculate_position_size(double price,
                                         double stop_loss,
                                         double confidence = 1.0,
                                         double regime_multiplier = 1.0) const;

    // Getters
    double get_capital() const { return capital_; }
    double get_win_rate() const;
    double get_avg_win() const;
    double get_avg_loss() const;
    int get_total_trades() const { return wins_ + losses_; }

    // Setters
    void set_capital(double capital) { capital_ = capital; }
    void set_max_risk(double risk) { max_risk_per_trade_ = risk; }

private:
    double capital_;
    double max_risk_per_trade_;
    double max_position_pct_;
    double kelly_fraction_;

    // Trade statistics for Kelly
    int wins_;
    int losses_;
    double total_win_amount_;
    double total_loss_amount_;
};

} // namespace trading_engine
