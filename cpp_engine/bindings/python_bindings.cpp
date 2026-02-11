/**
 * Python Bindings for Trading Engine
 * Exposes C++ classes to Python via pybind11
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include "pattern_recognition.hpp"
#include "order_book.hpp"
#include "indicators.hpp"
#include "position_sizer.hpp"
#include "kalman_filter.hpp"

namespace py = pybind11;
using namespace trading_engine;

// Helper to convert numpy array to vector
template<typename T>
std::vector<T> numpy_to_vector(py::array_t<T> arr) {
    auto buf = arr.request();
    T* ptr = static_cast<T*>(buf.ptr);
    return std::vector<T>(ptr, ptr + buf.size);
}

// Helper to convert vector to numpy array
template<typename T>
py::array_t<T> vector_to_numpy(const std::vector<T>& vec) {
    return py::array_t<T>(vec.size(), vec.data());
}

PYBIND11_MODULE(trading_engine, m) {
    m.doc() = "High-performance Trading Engine - C++ implementation with Python bindings";

    // ==================== Pattern Recognition ====================
    py::class_<PatternResult>(m, "PatternResult")
        .def_readonly("name", &PatternResult::name)
        .def_readonly("type", &PatternResult::type)
        .def_readonly("confidence", &PatternResult::confidence)
        .def_readonly("index", &PatternResult::index)
        .def_readonly("description", &PatternResult::description)
        .def("__repr__", [](const PatternResult& r) {
            return "<PatternResult '" + r.name + "' type=" + r.type + 
                   " confidence=" + std::to_string(r.confidence) + ">";
        });

    py::class_<PatternRecognition>(m, "PatternRecognition")
        .def(py::init<double, double>(),
             py::arg("body_min_ratio") = 0.6,
             py::arg("wick_max_ratio") = 0.3)
        .def("detect_all", [](const PatternRecognition& pr,
                              py::array_t<double> open,
                              py::array_t<double> high,
                              py::array_t<double> low,
                              py::array_t<double> close,
                              size_t lookback) {
            return pr.detect_all(
                numpy_to_vector<double>(open),
                numpy_to_vector<double>(high),
                numpy_to_vector<double>(low),
                numpy_to_vector<double>(close),
                lookback
            );
        }, py::arg("open"), py::arg("high"), py::arg("low"), py::arg("close"),
           py::arg("lookback") = 100,
           "Detect all candlestick patterns in OHLC data")
        .def("aggregate_signals", &PatternRecognition::aggregate_signals,
             py::arg("patterns"), py::arg("min_confidence") = 0.7,
             "Aggregate pattern signals into trading signal");

    // ==================== Order Book ====================
    py::class_<PriceLevel>(m, "PriceLevel")
        .def(py::init<>())
        .def(py::init<double, double>())
        .def_readwrite("price", &PriceLevel::price)
        .def_readwrite("quantity", &PriceLevel::quantity);

    py::class_<OrderBook>(m, "OrderBook")
        .def(py::init<const std::string&, int>(),
             py::arg("symbol"), py::arg("depth_levels") = 20)
        .def("update", &OrderBook::update,
             py::arg("bids"), py::arg("asks"), py::arg("event_time") = 0)
        .def("get_best_bid", &OrderBook::get_best_bid)
        .def("get_best_ask", &OrderBook::get_best_ask)
        .def("get_mid_price", &OrderBook::get_mid_price)
        .def("get_spread", &OrderBook::get_spread)
        .def("get_spread_pct", &OrderBook::get_spread_pct)
        .def("get_bid_depth", &OrderBook::get_bid_depth, py::arg("levels") = -1)
        .def("get_ask_depth", &OrderBook::get_ask_depth, py::arg("levels") = -1)
        .def("get_weighted_mid_price", &OrderBook::get_weighted_mid_price, py::arg("levels") = 5)
        .def("get_order_book_imbalance", &OrderBook::get_order_book_imbalance, py::arg("levels") = -1)
        .def("get_stats", &OrderBook::get_stats)
        .def_property_readonly("symbol", &OrderBook::get_symbol)
        .def_property_readonly("depth_levels", &OrderBook::get_depth_levels);

    py::class_<OrderBookManager>(m, "OrderBookManager")
        .def(py::init<const std::vector<std::string>&, int>(),
             py::arg("symbols"), py::arg("depth_levels") = 20)
        .def("update", &OrderBookManager::update)
        .def("get_book", py::overload_cast<const std::string&>(&OrderBookManager::get_book),
             py::return_value_policy::reference_internal)
        .def("get_all_stats", &OrderBookManager::get_all_stats);

    // ==================== Indicators ====================
    py::class_<Indicators::MACDResult>(m, "MACDResult")
        .def_readonly("macd_line", &Indicators::MACDResult::macd_line)
        .def_readonly("signal_line", &Indicators::MACDResult::signal_line)
        .def_readonly("histogram", &Indicators::MACDResult::histogram);

    py::class_<Indicators::ADXResult>(m, "ADXResult")
        .def_readonly("adx", &Indicators::ADXResult::adx)
        .def_readonly("plus_di", &Indicators::ADXResult::plus_di)
        .def_readonly("minus_di", &Indicators::ADXResult::minus_di);

    py::class_<Indicators::BollingerResult>(m, "BollingerResult")
        .def_readonly("upper", &Indicators::BollingerResult::upper)
        .def_readonly("middle", &Indicators::BollingerResult::middle)
        .def_readonly("lower", &Indicators::BollingerResult::lower)
        .def_readonly("bandwidth", &Indicators::BollingerResult::bandwidth);

    py::class_<Indicators::StochasticResult>(m, "StochasticResult")
        .def_readonly("k", &Indicators::StochasticResult::k)
        .def_readonly("d", &Indicators::StochasticResult::d);

    py::class_<Indicators>(m, "Indicators")
        .def_static("sma", [](py::array_t<double> data, int period) {
            return vector_to_numpy(Indicators::sma(numpy_to_vector<double>(data), period));
        }, py::arg("data"), py::arg("period"))
        .def_static("ema", [](py::array_t<double> data, int period) {
            return vector_to_numpy(Indicators::ema(numpy_to_vector<double>(data), period));
        }, py::arg("data"), py::arg("period"))
        .def_static("wma", [](py::array_t<double> data, int period) {
            return vector_to_numpy(Indicators::wma(numpy_to_vector<double>(data), period));
        }, py::arg("data"), py::arg("period"))
        .def_static("rsi", [](py::array_t<double> close, int period) {
            return vector_to_numpy(Indicators::rsi(numpy_to_vector<double>(close), period));
        }, py::arg("close"), py::arg("period") = 14)
        .def_static("macd", [](py::array_t<double> close, int fast, int slow, int signal) {
            auto result = Indicators::macd(numpy_to_vector<double>(close), fast, slow, signal);
            py::dict ret;
            ret["macd_line"] = vector_to_numpy(result.macd_line);
            ret["signal_line"] = vector_to_numpy(result.signal_line);
            ret["histogram"] = vector_to_numpy(result.histogram);
            return ret;
        }, py::arg("close"), py::arg("fast_period") = 12, 
           py::arg("slow_period") = 26, py::arg("signal_period") = 9)
        .def_static("adx", [](py::array_t<double> high, py::array_t<double> low, 
                              py::array_t<double> close, int period) {
            auto result = Indicators::adx(
                numpy_to_vector<double>(high),
                numpy_to_vector<double>(low),
                numpy_to_vector<double>(close),
                period
            );
            py::dict ret;
            ret["adx"] = vector_to_numpy(result.adx);
            ret["plus_di"] = vector_to_numpy(result.plus_di);
            ret["minus_di"] = vector_to_numpy(result.minus_di);
            return ret;
        }, py::arg("high"), py::arg("low"), py::arg("close"), py::arg("period") = 14)
        .def_static("bollinger_bands", [](py::array_t<double> close, int period, double std_dev) {
            auto result = Indicators::bollinger_bands(numpy_to_vector<double>(close), period, std_dev);
            py::dict ret;
            ret["upper"] = vector_to_numpy(result.upper);
            ret["middle"] = vector_to_numpy(result.middle);
            ret["lower"] = vector_to_numpy(result.lower);
            ret["bandwidth"] = vector_to_numpy(result.bandwidth);
            return ret;
        }, py::arg("close"), py::arg("period") = 20, py::arg("std_dev") = 2.0)
        .def_static("atr", [](py::array_t<double> high, py::array_t<double> low,
                              py::array_t<double> close, int period) {
            return vector_to_numpy(Indicators::atr(
                numpy_to_vector<double>(high),
                numpy_to_vector<double>(low),
                numpy_to_vector<double>(close),
                period
            ));
        }, py::arg("high"), py::arg("low"), py::arg("close"), py::arg("period") = 14)
        .def_static("stochastic", [](py::array_t<double> high, py::array_t<double> low,
                                     py::array_t<double> close, int k_period, int d_period) {
            auto result = Indicators::stochastic(
                numpy_to_vector<double>(high),
                numpy_to_vector<double>(low),
                numpy_to_vector<double>(close),
                k_period, d_period
            );
            py::dict ret;
            ret["k"] = vector_to_numpy(result.k);
            ret["d"] = vector_to_numpy(result.d);
            return ret;
        }, py::arg("high"), py::arg("low"), py::arg("close"), 
           py::arg("k_period") = 14, py::arg("d_period") = 3)
        .def_static("vwap", [](py::array_t<double> high, py::array_t<double> low,
                               py::array_t<double> close, py::array_t<double> volume) {
            return vector_to_numpy(Indicators::vwap(
                numpy_to_vector<double>(high),
                numpy_to_vector<double>(low),
                numpy_to_vector<double>(close),
                numpy_to_vector<double>(volume)
            ));
        }, py::arg("high"), py::arg("low"), py::arg("close"), py::arg("volume"))
        .def_static("obv", [](py::array_t<double> close, py::array_t<double> volume) {
            return vector_to_numpy(Indicators::obv(
                numpy_to_vector<double>(close),
                numpy_to_vector<double>(volume)
            ));
        }, py::arg("close"), py::arg("volume"));

    // ==================== Position Sizer ====================
    py::class_<PositionInfo>(m, "PositionInfo")
        .def_readonly("size", &PositionInfo::size)
        .def_readonly("risk_amount", &PositionInfo::risk_amount)
        .def_readonly("stop_distance", &PositionInfo::stop_distance)
        .def_readonly("kelly_fraction", &PositionInfo::kelly_fraction)
        .def_readonly("method", &PositionInfo::method);

    py::class_<PositionSizer>(m, "PositionSizer")
        .def(py::init<double, double, double, double>(),
             py::arg("capital") = 1000.0,
             py::arg("max_risk_per_trade") = 0.02,
             py::arg("max_position_pct") = 0.20,
             py::arg("kelly_fraction") = 0.25)
        .def("update_stats", &PositionSizer::update_stats, py::arg("pnl"))
        .def("reset_stats", &PositionSizer::reset_stats)
        .def("kelly_criterion", &PositionSizer::kelly_criterion)
        .def("calculate_position_size", &PositionSizer::calculate_position_size,
             py::arg("price"), py::arg("stop_loss"),
             py::arg("confidence") = 1.0, py::arg("regime_multiplier") = 1.0)
        .def_property("capital", &PositionSizer::get_capital, &PositionSizer::set_capital)
        .def_property_readonly("win_rate", &PositionSizer::get_win_rate)
        .def_property_readonly("avg_win", &PositionSizer::get_avg_win)
        .def_property_readonly("avg_loss", &PositionSizer::get_avg_loss)
        .def_property_readonly("total_trades", &PositionSizer::get_total_trades);

    // ==================== Kalman Filter ====================
    py::class_<KalmanState>(m, "KalmanState")
        .def_readonly("estimate", &KalmanState::estimate)
        .def_readonly("error_estimate", &KalmanState::error_estimate)
        .def_readonly("velocity", &KalmanState::velocity);

    py::class_<KalmanFilter::Prediction>(m, "KalmanPrediction")
        .def_readonly("value", &KalmanFilter::Prediction::value)
        .def_readonly("lower_bound", &KalmanFilter::Prediction::lower_bound)
        .def_readonly("upper_bound", &KalmanFilter::Prediction::upper_bound)
        .def_readonly("confidence", &KalmanFilter::Prediction::confidence);

    py::class_<KalmanFilter>(m, "KalmanFilter")
        .def(py::init<double, double, double, double>(),
             py::arg("process_noise") = 0.01,
             py::arg("measurement_noise") = 0.1,
             py::arg("initial_estimate") = 0.0,
             py::arg("initial_error") = 1.0)
        .def("update", &KalmanFilter::update, py::arg("measurement"))
        .def("predict", &KalmanFilter::predict)
        .def("get_state", &KalmanFilter::get_state)
        .def("reset", &KalmanFilter::reset,
             py::arg("initial_estimate") = 0.0, py::arg("initial_error") = 1.0)
        .def("predict_with_confidence", &KalmanFilter::predict_with_confidence,
             py::arg("steps_ahead") = 1)
        .def_property_readonly("velocity", &KalmanFilter::get_velocity)
        .def_static("filter_series", [](py::array_t<double> data, double pn, double mn) {
            return vector_to_numpy(KalmanFilter::filter_series(
                numpy_to_vector<double>(data), pn, mn
            ));
        }, py::arg("data"), py::arg("process_noise") = 0.01, 
           py::arg("measurement_noise") = 0.1);

    py::class_<ExtendedKalmanFilter>(m, "ExtendedKalmanFilter")
        .def(py::init<double, double>(),
             py::arg("process_noise") = 0.01,
             py::arg("measurement_noise") = 0.1)
        .def("update", &ExtendedKalmanFilter::update,
             py::arg("price"), py::arg("volume") = 0.0)
        .def("predict_direction", &ExtendedKalmanFilter::predict_direction)
        .def("get_trend_strength", &ExtendedKalmanFilter::get_trend_strength);

    // Module version
    m.attr("__version__") = "1.0.0";
}
