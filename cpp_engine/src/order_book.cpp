/**
 * Order Book Implementation
 * Fast order book management with imbalance calculations
 */

#include "order_book.hpp"
#include <cmath>
#include <algorithm>
#include <stdexcept>

namespace trading_engine {

OrderBook::OrderBook(const std::string& symbol, int depth_levels)
    : symbol_(symbol), depth_levels_(depth_levels), last_update_time_(0) {}

void OrderBook::update(const std::vector<PriceLevel>& bids,
                       const std::vector<PriceLevel>& asks,
                       long long event_time) {
    // Clear existing data
    bids_.clear();
    asks_.clear();
    
    // Add bids (sorted descending by price)
    int count = 0;
    for (const auto& level : bids) {
        if (count >= depth_levels_) break;
        if (level.quantity > 0) {
            bids_[level.price] = level.quantity;
            ++count;
        }
    }
    
    // Add asks (sorted ascending by price)
    count = 0;
    for (const auto& level : asks) {
        if (count >= depth_levels_) break;
        if (level.quantity > 0) {
            asks_[level.price] = level.quantity;
            ++count;
        }
    }
    
    last_update_time_ = event_time;
}

double OrderBook::get_best_bid() const {
    if (bids_.empty()) return 0.0;
    return bids_.begin()->first;
}

double OrderBook::get_best_ask() const {
    if (asks_.empty()) return 0.0;
    return asks_.begin()->first;
}

double OrderBook::get_mid_price() const {
    double bid = get_best_bid();
    double ask = get_best_ask();
    if (bid == 0.0 || ask == 0.0) return 0.0;
    return (bid + ask) / 2.0;
}

double OrderBook::get_spread() const {
    double bid = get_best_bid();
    double ask = get_best_ask();
    if (bid == 0.0 || ask == 0.0) return 0.0;
    return ask - bid;
}

double OrderBook::get_spread_pct() const {
    double mid = get_mid_price();
    if (mid == 0.0) return 0.0;
    return (get_spread() / mid) * 100.0;
}

double OrderBook::get_bid_depth(int levels) const {
    double total = 0.0;
    int count = 0;
    int max_levels = (levels < 0) ? depth_levels_ : levels;
    
    for (const auto& [price, qty] : bids_) {
        if (count >= max_levels) break;
        total += qty;
        ++count;
    }
    
    return total;
}

double OrderBook::get_ask_depth(int levels) const {
    double total = 0.0;
    int count = 0;
    int max_levels = (levels < 0) ? depth_levels_ : levels;
    
    for (const auto& [price, qty] : asks_) {
        if (count >= max_levels) break;
        total += qty;
        ++count;
    }
    
    return total;
}

double OrderBook::get_weighted_mid_price(int levels) const {
    if (bids_.empty() || asks_.empty()) return 0.0;
    
    double bid_weighted = 0.0;
    double ask_weighted = 0.0;
    double bid_qty = 0.0;
    double ask_qty = 0.0;
    
    int count = 0;
    for (const auto& [price, qty] : bids_) {
        if (count >= levels) break;
        bid_weighted += price * qty;
        bid_qty += qty;
        ++count;
    }
    
    count = 0;
    for (const auto& [price, qty] : asks_) {
        if (count >= levels) break;
        ask_weighted += price * qty;
        ask_qty += qty;
        ++count;
    }
    
    double total_qty = bid_qty + ask_qty;
    if (total_qty == 0.0) return get_mid_price();
    
    // Weight by opposite side's quantity (more selling pressure = closer to bid)
    return (bid_weighted / bid_qty * ask_qty + ask_weighted / ask_qty * bid_qty) / total_qty;
}

double OrderBook::get_order_book_imbalance(int levels) const {
    double bid_depth = get_bid_depth(levels);
    double ask_depth = get_ask_depth(levels);
    double total = bid_depth + ask_depth;
    
    if (total == 0.0) return 0.0;
    
    // OBI = (Bid - Ask) / (Bid + Ask)
    // Range: -1 (all selling) to +1 (all buying)
    return (bid_depth - ask_depth) / total;
}

std::map<std::string, double> OrderBook::get_stats() const {
    return {
        {"best_bid", get_best_bid()},
        {"best_ask", get_best_ask()},
        {"mid_price", get_mid_price()},
        {"spread", get_spread()},
        {"spread_pct", get_spread_pct()},
        {"bid_depth", get_bid_depth()},
        {"ask_depth", get_ask_depth()},
        {"obi", get_order_book_imbalance()},
        {"weighted_mid", get_weighted_mid_price()},
        {"last_update", static_cast<double>(last_update_time_)}
    };
}

// OrderBookManager implementation
OrderBookManager::OrderBookManager(const std::vector<std::string>& symbols, int depth_levels) {
    for (const auto& symbol : symbols) {
        books_.emplace(symbol, OrderBook(symbol, depth_levels));
    }
}

void OrderBookManager::update(const std::string& symbol,
                              const std::vector<PriceLevel>& bids,
                              const std::vector<PriceLevel>& asks,
                              long long event_time) {
    auto it = books_.find(symbol);
    if (it != books_.end()) {
        it->second.update(bids, asks, event_time);
    }
}

OrderBook& OrderBookManager::get_book(const std::string& symbol) {
    auto it = books_.find(symbol);
    if (it == books_.end()) {
        throw std::runtime_error("Symbol not found: " + symbol);
    }
    return it->second;
}

const OrderBook& OrderBookManager::get_book(const std::string& symbol) const {
    auto it = books_.find(symbol);
    if (it == books_.end()) {
        throw std::runtime_error("Symbol not found: " + symbol);
    }
    return it->second;
}

std::map<std::string, std::map<std::string, double>> OrderBookManager::get_all_stats() const {
    std::map<std::string, std::map<std::string, double>> result;
    for (const auto& [symbol, book] : books_) {
        result[symbol] = book.get_stats();
    }
    return result;
}

} // namespace trading_engine
