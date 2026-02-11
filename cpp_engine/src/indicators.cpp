/**
 * Technical Indicators Implementation
 * Fast implementations of common trading indicators
 */

#include "indicators.hpp"
#include <cmath>
#include <algorithm>
#include <numeric>
#include <stdexcept>

namespace trading_engine {

// Simple Moving Average
std::vector<double> Indicators::sma(const std::vector<double>& data, int period) {
    std::vector<double> result(data.size(), 0.0);
    if (data.size() < static_cast<size_t>(period) || period <= 0) return result;
    
    // Calculate initial sum
    double sum = 0.0;
    for (int i = 0; i < period; ++i) {
        sum += data[i];
    }
    result[period - 1] = sum / period;
    
    // Sliding window
    for (size_t i = period; i < data.size(); ++i) {
        sum += data[i] - data[i - period];
        result[i] = sum / period;
    }
    
    return result;
}

// Exponential Moving Average
std::vector<double> Indicators::ema(const std::vector<double>& data, int period) {
    std::vector<double> result(data.size(), 0.0);
    if (data.size() < static_cast<size_t>(period) || period <= 0) return result;
    
    double multiplier = 2.0 / (period + 1);
    
    // First EMA is SMA
    double sum = 0.0;
    for (int i = 0; i < period; ++i) {
        sum += data[i];
    }
    result[period - 1] = sum / period;
    
    // Apply EMA formula
    for (size_t i = period; i < data.size(); ++i) {
        result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1];
    }
    
    return result;
}

// Weighted Moving Average
std::vector<double> Indicators::wma(const std::vector<double>& data, int period) {
    std::vector<double> result(data.size(), 0.0);
    if (data.size() < static_cast<size_t>(period) || period <= 0) return result;
    
    double weight_sum = period * (period + 1) / 2.0;
    
    for (size_t i = period - 1; i < data.size(); ++i) {
        double weighted = 0.0;
        for (int j = 0; j < period; ++j) {
            weighted += data[i - period + 1 + j] * (j + 1);
        }
        result[i] = weighted / weight_sum;
    }
    
    return result;
}

// Relative Strength Index
std::vector<double> Indicators::rsi(const std::vector<double>& close, int period) {
    std::vector<double> result(close.size(), 50.0);  // Neutral default
    if (close.size() < static_cast<size_t>(period + 1)) return result;
    
    std::vector<double> gains(close.size(), 0.0);
    std::vector<double> losses(close.size(), 0.0);
    
    // Calculate gains and losses
    for (size_t i = 1; i < close.size(); ++i) {
        double change = close[i] - close[i - 1];
        if (change > 0) {
            gains[i] = change;
        } else {
            losses[i] = -change;
        }
    }
    
    // Initial average gain/loss
    double avg_gain = 0.0, avg_loss = 0.0;
    for (int i = 1; i <= period; ++i) {
        avg_gain += gains[i];
        avg_loss += losses[i];
    }
    avg_gain /= period;
    avg_loss /= period;
    
    // First RSI
    if (avg_loss > 0) {
        double rs = avg_gain / avg_loss;
        result[period] = 100.0 - (100.0 / (1.0 + rs));
    } else {
        result[period] = 100.0;
    }
    
    // Smoothed RSI
    for (size_t i = period + 1; i < close.size(); ++i) {
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period;
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period;
        
        if (avg_loss > 0) {
            double rs = avg_gain / avg_loss;
            result[i] = 100.0 - (100.0 / (1.0 + rs));
        } else {
            result[i] = 100.0;
        }
    }
    
    return result;
}

// MACD
Indicators::MACDResult Indicators::macd(const std::vector<double>& close,
                                         int fast_period,
                                         int slow_period,
                                         int signal_period) {
    MACDResult result;
    result.macd_line.resize(close.size(), 0.0);
    result.signal_line.resize(close.size(), 0.0);
    result.histogram.resize(close.size(), 0.0);
    
    auto fast_ema = ema(close, fast_period);
    auto slow_ema = ema(close, slow_period);
    
    // MACD Line = Fast EMA - Slow EMA
    for (size_t i = 0; i < close.size(); ++i) {
        result.macd_line[i] = fast_ema[i] - slow_ema[i];
    }
    
    // Signal Line = EMA of MACD Line
    result.signal_line = ema(result.macd_line, signal_period);
    
    // Histogram = MACD Line - Signal Line
    for (size_t i = 0; i < close.size(); ++i) {
        result.histogram[i] = result.macd_line[i] - result.signal_line[i];
    }
    
    return result;
}

// True Range helper
double Indicators::true_range(double high, double low, double prev_close) {
    double hl = high - low;
    double hc = std::abs(high - prev_close);
    double lc = std::abs(low - prev_close);
    return std::max({hl, hc, lc});
}

// Average True Range
std::vector<double> Indicators::atr(const std::vector<double>& high,
                                     const std::vector<double>& low,
                                     const std::vector<double>& close,
                                     int period) {
    size_t n = std::min({high.size(), low.size(), close.size()});
    std::vector<double> result(n, 0.0);
    if (n < static_cast<size_t>(period + 1)) return result;
    
    // Calculate true ranges
    std::vector<double> tr(n, 0.0);
    tr[0] = high[0] - low[0];
    for (size_t i = 1; i < n; ++i) {
        tr[i] = true_range(high[i], low[i], close[i - 1]);
    }
    
    // First ATR is simple average
    double sum = 0.0;
    for (int i = 0; i < period; ++i) {
        sum += tr[i];
    }
    result[period - 1] = sum / period;
    
    // Smoothed ATR
    for (size_t i = period; i < n; ++i) {
        result[i] = (result[i - 1] * (period - 1) + tr[i]) / period;
    }
    
    return result;
}

// ADX - Average Directional Index
Indicators::ADXResult Indicators::adx(const std::vector<double>& high,
                                       const std::vector<double>& low,
                                       const std::vector<double>& close,
                                       int period) {
    size_t n = std::min({high.size(), low.size(), close.size()});
    ADXResult result;
    result.adx.resize(n, 0.0);
    result.plus_di.resize(n, 0.0);
    result.minus_di.resize(n, 0.0);
    
    if (n < static_cast<size_t>(period + 1)) return result;
    
    // Calculate directional movement
    std::vector<double> plus_dm(n, 0.0);
    std::vector<double> minus_dm(n, 0.0);
    std::vector<double> tr(n, 0.0);
    
    tr[0] = high[0] - low[0];
    for (size_t i = 1; i < n; ++i) {
        double up_move = high[i] - high[i - 1];
        double down_move = low[i - 1] - low[i];
        
        if (up_move > down_move && up_move > 0) {
            plus_dm[i] = up_move;
        }
        if (down_move > up_move && down_move > 0) {
            minus_dm[i] = down_move;
        }
        tr[i] = true_range(high[i], low[i], close[i - 1]);
    }
    
    // Smooth DM and TR
    auto smoothed_plus_dm = ema(plus_dm, period);
    auto smoothed_minus_dm = ema(minus_dm, period);
    auto smoothed_tr = ema(tr, period);
    
    // Calculate DI
    std::vector<double> dx(n, 0.0);
    for (size_t i = period; i < n; ++i) {
        if (smoothed_tr[i] > 0) {
            result.plus_di[i] = 100.0 * smoothed_plus_dm[i] / smoothed_tr[i];
            result.minus_di[i] = 100.0 * smoothed_minus_dm[i] / smoothed_tr[i];
        }
        
        double di_sum = result.plus_di[i] + result.minus_di[i];
        if (di_sum > 0) {
            dx[i] = 100.0 * std::abs(result.plus_di[i] - result.minus_di[i]) / di_sum;
        }
    }
    
    // ADX is smoothed DX
    result.adx = ema(dx, period);
    
    return result;
}

// Bollinger Bands
Indicators::BollingerResult Indicators::bollinger_bands(const std::vector<double>& close,
                                                         int period,
                                                         double std_dev) {
    BollingerResult result;
    size_t n = close.size();
    result.upper.resize(n, 0.0);
    result.middle.resize(n, 0.0);
    result.lower.resize(n, 0.0);
    result.bandwidth.resize(n, 0.0);
    
    if (n < static_cast<size_t>(period)) return result;
    
    result.middle = sma(close, period);
    
    for (size_t i = period - 1; i < n; ++i) {
        // Calculate standard deviation
        double sum_sq = 0.0;
        for (int j = 0; j < period; ++j) {
            double diff = close[i - j] - result.middle[i];
            sum_sq += diff * diff;
        }
        double std = std::sqrt(sum_sq / period);
        
        result.upper[i] = result.middle[i] + std_dev * std;
        result.lower[i] = result.middle[i] - std_dev * std;
        
        if (result.middle[i] > 0) {
            result.bandwidth[i] = (result.upper[i] - result.lower[i]) / result.middle[i];
        }
    }
    
    return result;
}

// Stochastic Oscillator
Indicators::StochasticResult Indicators::stochastic(const std::vector<double>& high,
                                                     const std::vector<double>& low,
                                                     const std::vector<double>& close,
                                                     int k_period,
                                                     int d_period) {
    size_t n = std::min({high.size(), low.size(), close.size()});
    StochasticResult result;
    result.k.resize(n, 50.0);
    result.d.resize(n, 50.0);
    
    if (n < static_cast<size_t>(k_period)) return result;
    
    for (size_t i = k_period - 1; i < n; ++i) {
        double highest = high[i];
        double lowest = low[i];
        
        for (int j = 1; j < k_period; ++j) {
            highest = std::max(highest, high[i - j]);
            lowest = std::min(lowest, low[i - j]);
        }
        
        double range = highest - lowest;
        if (range > 0) {
            result.k[i] = 100.0 * (close[i] - lowest) / range;
        }
    }
    
    result.d = sma(result.k, d_period);
    
    return result;
}

// VWAP
std::vector<double> Indicators::vwap(const std::vector<double>& high,
                                      const std::vector<double>& low,
                                      const std::vector<double>& close,
                                      const std::vector<double>& volume) {
    size_t n = std::min({high.size(), low.size(), close.size(), volume.size()});
    std::vector<double> result(n, 0.0);
    
    double cumulative_tp_vol = 0.0;
    double cumulative_vol = 0.0;
    
    for (size_t i = 0; i < n; ++i) {
        double typical_price = (high[i] + low[i] + close[i]) / 3.0;
        cumulative_tp_vol += typical_price * volume[i];
        cumulative_vol += volume[i];
        
        if (cumulative_vol > 0) {
            result[i] = cumulative_tp_vol / cumulative_vol;
        }
    }
    
    return result;
}

// OBV - On Balance Volume
std::vector<double> Indicators::obv(const std::vector<double>& close,
                                     const std::vector<double>& volume) {
    size_t n = std::min(close.size(), volume.size());
    std::vector<double> result(n, 0.0);
    
    if (n == 0) return result;
    
    result[0] = volume[0];
    for (size_t i = 1; i < n; ++i) {
        if (close[i] > close[i - 1]) {
            result[i] = result[i - 1] + volume[i];
        } else if (close[i] < close[i - 1]) {
            result[i] = result[i - 1] - volume[i];
        } else {
            result[i] = result[i - 1];
        }
    }
    
    return result;
}

} // namespace trading_engine
