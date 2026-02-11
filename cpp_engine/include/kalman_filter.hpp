#pragma once

/**
 * Kalman Filter Header
 * Linear Kalman filter for price prediction
 */

#include "common.hpp"
#include <vector>

namespace trading_engine {

class KalmanFilter {
public:
    KalmanFilter(double process_noise = 0.01,
                 double measurement_noise = 0.1,
                 double initial_estimate = 0.0,
                 double initial_error = 1.0);

    // Update filter with new measurement
    KalmanState update(double measurement);

    // Predict next state without updating
    double predict() const;

    // Get current state
    KalmanState get_state() const;

    // Reset filter
    void reset(double initial_estimate = 0.0, double initial_error = 1.0);

    // Batch processing - filter entire series
    static std::vector<double> filter_series(const std::vector<double>& data,
                                              double process_noise = 0.01,
                                              double measurement_noise = 0.1);

    // Get velocity (rate of change)
    double get_velocity() const { return velocity_; }

    // Prediction with confidence interval
    struct Prediction {
        double value;
        double lower_bound;
        double upper_bound;
        double confidence;
    };
    Prediction predict_with_confidence(int steps_ahead = 1) const;

private:
    double process_noise_;      // Q
    double measurement_noise_;  // R
    double estimate_;           // x
    double error_estimate_;     // P
    double velocity_;           // dx/dt estimate
    double prev_estimate_;
};

// Extended Kalman Filter for non-linear price dynamics
class ExtendedKalmanFilter {
public:
    ExtendedKalmanFilter(double process_noise = 0.01,
                         double measurement_noise = 0.1);

    // Update with price and optional volume
    KalmanState update(double price, double volume = 0.0);

    // Predict trend direction: 1 (up), -1 (down), 0 (neutral)
    int predict_direction() const;

    // Get trend strength (0 to 1)
    double get_trend_strength() const;

private:
    KalmanFilter price_filter_;
    KalmanFilter volume_filter_;
    double trend_accumulator_;
};

} // namespace trading_engine
