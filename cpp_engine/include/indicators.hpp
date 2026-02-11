#pragma once

/**
 * Technical Indicators Header
 * Fast implementations of common trading indicators
 */

#include "common.hpp"
#include <vector>

namespace trading_engine {

class Indicators {
public:
    // Moving Averages
    static std::vector<double> sma(const std::vector<double>& data, int period);
    static std::vector<double> ema(const std::vector<double>& data, int period);
    static std::vector<double> wma(const std::vector<double>& data, int period);

    // RSI - Relative Strength Index
    static std::vector<double> rsi(const std::vector<double>& close, int period = 14);

    // MACD - Moving Average Convergence Divergence
    struct MACDResult {
        std::vector<double> macd_line;
        std::vector<double> signal_line;
        std::vector<double> histogram;
    };
    static MACDResult macd(const std::vector<double>& close, 
                           int fast_period = 12, 
                           int slow_period = 26, 
                           int signal_period = 9);

    // ADX - Average Directional Index
    struct ADXResult {
        std::vector<double> adx;
        std::vector<double> plus_di;
        std::vector<double> minus_di;
    };
    static ADXResult adx(const std::vector<double>& high,
                         const std::vector<double>& low,
                         const std::vector<double>& close,
                         int period = 14);

    // Bollinger Bands
    struct BollingerResult {
        std::vector<double> upper;
        std::vector<double> middle;
        std::vector<double> lower;
        std::vector<double> bandwidth;
    };
    static BollingerResult bollinger_bands(const std::vector<double>& close, 
                                           int period = 20, 
                                           double std_dev = 2.0);

    // ATR - Average True Range
    static std::vector<double> atr(const std::vector<double>& high,
                                   const std::vector<double>& low,
                                   const std::vector<double>& close,
                                   int period = 14);

    // Stochastic Oscillator
    struct StochasticResult {
        std::vector<double> k;
        std::vector<double> d;
    };
    static StochasticResult stochastic(const std::vector<double>& high,
                                       const std::vector<double>& low,
                                       const std::vector<double>& close,
                                       int k_period = 14,
                                       int d_period = 3);

    // VWAP - Volume Weighted Average Price
    static std::vector<double> vwap(const std::vector<double>& high,
                                    const std::vector<double>& low,
                                    const std::vector<double>& close,
                                    const std::vector<double>& volume);

    // OBV - On Balance Volume
    static std::vector<double> obv(const std::vector<double>& close,
                                   const std::vector<double>& volume);

private:
    // Helper functions
    static double true_range(double high, double low, double prev_close);
};

} // namespace trading_engine
