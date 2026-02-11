/**
 * Kalman Filter Implementation
 * Linear Kalman filter for price prediction and smoothing
 */

#include "kalman_filter.hpp"
#include <cmath>
#include <algorithm>

namespace trading_engine {

KalmanFilter::KalmanFilter(double process_noise,
                           double measurement_noise,
                           double initial_estimate,
                           double initial_error)
    : process_noise_(process_noise),
      measurement_noise_(measurement_noise),
      estimate_(initial_estimate),
      error_estimate_(initial_error),
      velocity_(0.0),
      prev_estimate_(initial_estimate) {}

KalmanState KalmanFilter::update(double measurement) {
    // Save previous estimate for velocity calculation
    prev_estimate_ = estimate_;
    
    // Prediction step
    double predicted_estimate = estimate_ + velocity_;
    double predicted_error = error_estimate_ + process_noise_;
    
    // Update step (Kalman gain)
    double kalman_gain = predicted_error / (predicted_error + measurement_noise_);
    
    // Update estimate
    estimate_ = predicted_estimate + kalman_gain * (measurement - predicted_estimate);
    
    // Update error estimate
    error_estimate_ = (1.0 - kalman_gain) * predicted_error;
    
    // Update velocity estimate (simple difference)
    velocity_ = estimate_ - prev_estimate_;
    
    return get_state();
}

double KalmanFilter::predict() const {
    return estimate_ + velocity_;
}

KalmanState KalmanFilter::get_state() const {
    return {estimate_, error_estimate_, velocity_};
}

void KalmanFilter::reset(double initial_estimate, double initial_error) {
    estimate_ = initial_estimate;
    error_estimate_ = initial_error;
    velocity_ = 0.0;
    prev_estimate_ = initial_estimate;
}

std::vector<double> KalmanFilter::filter_series(const std::vector<double>& data,
                                                 double process_noise,
                                                 double measurement_noise) {
    std::vector<double> result(data.size(), 0.0);
    if (data.empty()) return result;
    
    KalmanFilter filter(process_noise, measurement_noise, data[0], 1.0);
    result[0] = data[0];
    
    for (size_t i = 1; i < data.size(); ++i) {
        auto state = filter.update(data[i]);
        result[i] = state.estimate;
    }
    
    return result;
}

KalmanFilter::Prediction KalmanFilter::predict_with_confidence(int steps_ahead) const {
    Prediction pred;
    
    // Linear extrapolation using velocity
    pred.value = estimate_ + velocity_ * steps_ahead;
    
    // Uncertainty grows with prediction horizon
    double uncertainty = std::sqrt(error_estimate_ * steps_ahead + 
                                   process_noise_ * steps_ahead * steps_ahead);
    
    // 95% confidence interval (approximately 2 standard deviations)
    pred.lower_bound = pred.value - 2.0 * uncertainty;
    pred.upper_bound = pred.value + 2.0 * uncertainty;
    
    // Confidence decreases with uncertainty
    double base_confidence = 1.0 / (1.0 + error_estimate_);
    pred.confidence = base_confidence / std::sqrt(static_cast<double>(steps_ahead));
    pred.confidence = std::max(0.0, std::min(1.0, pred.confidence));
    
    return pred;
}

// Extended Kalman Filter implementation
ExtendedKalmanFilter::ExtendedKalmanFilter(double process_noise,
                                           double measurement_noise)
    : price_filter_(process_noise, measurement_noise),
      volume_filter_(process_noise * 10, measurement_noise * 10),  // Volume is noisier
      trend_accumulator_(0.0) {}

KalmanState ExtendedKalmanFilter::update(double price, double volume) {
    auto price_state = price_filter_.update(price);
    
    if (volume > 0) {
        volume_filter_.update(volume);
    }
    
    // Update trend accumulator
    // Positive velocity with high volume = stronger bullish trend
    double velocity = price_state.velocity;
    double vol_factor = 1.0;
    
    if (volume > 0) {
        auto vol_state = volume_filter_.get_state();
        if (vol_state.estimate > 0) {
            vol_factor = volume / vol_state.estimate;
            vol_factor = std::max(0.5, std::min(2.0, vol_factor));
        }
    }
    
    // Exponential moving average of trend signal
    double trend_signal = velocity * vol_factor;
    trend_accumulator_ = 0.9 * trend_accumulator_ + 0.1 * trend_signal;
    
    return price_state;
}

int ExtendedKalmanFilter::predict_direction() const {
    // Use velocity and trend accumulator
    double velocity = price_filter_.get_velocity();
    
    // Strong signal requires both agreeing
    if (velocity > 0 && trend_accumulator_ > 0) {
        return 1;  // Up
    } else if (velocity < 0 && trend_accumulator_ < 0) {
        return -1;  // Down
    }
    
    return 0;  // Neutral
}

double ExtendedKalmanFilter::get_trend_strength() const {
    // Normalize trend accumulator to 0-1 range
    // Use sigmoid-like transformation
    double raw = std::abs(trend_accumulator_) * 100.0;  // Scale up
    double strength = raw / (1.0 + raw);  // Sigmoid transform
    return std::min(1.0, strength);
}

} // namespace trading_engine
