#pragma once

/**
 * Order Book Header
 * Real-time order book management with fast imbalance calculations
 */

#include "common.hpp"
#include <map>
#include <vector>
#include <string>

namespace trading_engine {

class OrderBook {
public:
    OrderBook(const std::string& symbol, int depth_levels = 20);

    // Update order book from depth data
    void update(const std::vector<PriceLevel>& bids, 
                const std::vector<PriceLevel>& asks,
                long long event_time = 0);

    // Price queries
    double get_best_bid() const;
    double get_best_ask() const;
    double get_mid_price() const;
    double get_spread() const;
    double get_spread_pct() const;
    double get_weighted_mid_price(int levels = 5) const;

    // Volume queries
    double get_bid_depth(int levels = -1) const;
    double get_ask_depth(int levels = -1) const;

    // Order Book Imbalance (OBI)
    // Returns value between -1 and +1
    // > 0.3: Strong buy pressure
    // < -0.3: Strong sell pressure
    double get_order_book_imbalance(int levels = -1) const;

    // Statistics
    std::map<std::string, double> get_stats() const;

    // Getters
    std::string get_symbol() const { return symbol_; }
    int get_depth_levels() const { return depth_levels_; }
    long long get_last_update() const { return last_update_time_; }

private:
    std::string symbol_;
    int depth_levels_;
    long long last_update_time_;
    
    // Sorted by price: bids descending, asks ascending
    std::map<double, double, std::greater<double>> bids_;
    std::map<double, double> asks_;
};

class OrderBookManager {
public:
    OrderBookManager(const std::vector<std::string>& symbols, int depth_levels = 20);

    void update(const std::string& symbol, 
                const std::vector<PriceLevel>& bids,
                const std::vector<PriceLevel>& asks,
                long long event_time = 0);

    OrderBook& get_book(const std::string& symbol);
    const OrderBook& get_book(const std::string& symbol) const;
    
    std::map<std::string, std::map<std::string, double>> get_all_stats() const;

private:
    std::map<std::string, OrderBook> books_;
};

} // namespace trading_engine
