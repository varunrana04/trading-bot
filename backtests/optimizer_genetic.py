# backtests/optimizer_genetic.py
"""
GENETIC ALGORITHM OPTIMIZER - Uses evolutionary algorithms (DEAP) for parameter search

Alternative to Bayesian optimization:
- Population-based evolution
- Good for multi-modal optimization (multiple good solutions)
- Mutation and crossover operators
- Less likely to get stuck in local optima

Uses DEAP (Distributed Evolutionary Algorithms in Python)
"""

import os
import sys
import argparse
import pandas as pd
import random
from pathlib import Path
from multiprocessing import Pool, cpu_count
from deap import base, creator, tools, algorithms
from tqdm import tqdm

sys.path.append(str(Path(__file__).parent.parent))

from backtests.realistic_backtest import RealisticBacktest
from backtests.optimization_utils import (
    load_data, 
    evaluate_configuration,
)

# Import bot logic
try:
    from bots.crypto.trade_crypto_futures_aggressive import generate_signal as crypto_signal
except ImportError:
    print("Warning: Could not import crypto bot logic.")
    crypto_signal = None


# Bot definitions
BOT_DEFINITIONS = [
    {
        "name": "Crypto Futures Aggressive",
        "symbol": "BTCUSDT",
        "data_path_template": "data/historical/BTC_USDT_{timeframe}_{lookback}d.csv",
        "strategy_func": crypto_signal,
        "param_ranges": {
            "position_pct": (0.03, 0.15),
            "profit_target": (0.02, 0.10),
            "stop_loss": (0.002, 0.012),
        },
    },
]

TIMEFRAMES = ["5m", "15m", "30m", "1h"]
LOOKBACK_DAYS = [30, 365, 1825]


class GeneticOptimizer:
    """Genetic Algorithm optimizer using DEAP"""
    
    def __init__(self, population_size=20, generations=10, mutation_rate=0.2):
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.setup_deap()
    
    def setup_deap(self):
        """Setup DEAP genetic algorithm components"""
        # Create fitness class (maximize net P/L)
        if not hasattr(creator, "FitnessMax"):
            creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        if not hasattr(creator, "Individual"):
            creator.create("Individual", list, fitness=creator.FitnessMax)
        
        self.toolbox = base.Toolbox()
    
    def create_individual(self, param_ranges):
        """Create random individual (parameter set)"""
        return [
            random.uniform(param_ranges['position_pct'][0], param_ranges['position_pct'][1]),
            random.uniform(param_ranges['profit_target'][0], param_ranges['profit_target'][1]),
            random.uniform(param_ranges['stop_loss'][0], param_ranges['stop_loss'][1]),
        ]
    
    def evaluate_individual(self, individual, df, strategy_func):
        """Evaluate fitness of an individual"""
        params = {
            'position_pct': individual[0],
            'profit_target': individual[1],
            'stop_loss': individual[2],
        }
        
        try:
            bt = RealisticBacktest(initial_capital=10000)
            bt.position_pct = params['position_pct']
            bt.profit_target = params['profit_target']
            bt.stop_loss = params['stop_loss']
            
            metrics = evaluate_configuration(bt, df, strategy_func)
            
            # Fitness = net P/L with penalties
            fitness = metrics['net_pnl']
            
            if metrics['trades'] < 10:
                fitness *= 0.5
            if not metrics['valid']:
                fitness *= 0.7
            
            return (fitness,)  # DEAP expects tuple
            
        except Exception as e:
            return (-10000.0,)
    
    def optimize_configuration(self, bot_config, timeframe, lookback):
        """Run genetic algorithm for specific configuration"""
        
        # Load data
        try:
            data_path = bot_config["data_path_template"].format(
                symbol=bot_config["symbol"], 
                timeframe=timeframe, 
                lookback=lookback
            )
        except KeyError:
            data_path = bot_config["data_path_template"].format(
                symbol=bot_config["symbol"], 
                lookback=lookback
            )
        
        try:
            df = load_data(data_path)
        except Exception as e:
            print(f"  Skipping {timeframe} {lookback}d - data not found")
            return None
        
        print(f"\nOptimizing {timeframe} {lookback}d data ({len(df)} candles)...")
        print(f"  Population: {self.population_size}, Generations: {self.generations}")
        
        param_ranges = bot_config["param_ranges"]
        strategy_func = bot_config["strategy_func"]
        
        # Setup genetic algorithm
        self.toolbox.register("individual", tools.initIterate, creator.Individual,
                            lambda: self.create_individual(param_ranges))
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)
        self.toolbox.register("evaluate", self.evaluate_individual, df=df, strategy_func=strategy_func)
        self.toolbox.register("mate", tools.cxBlend, alpha=0.5)
        self.toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=0.01, indpb=self.mutation_rate)
        self.toolbox.register("select", tools.selTournament, tournsize=3)
        
        # Create initial population
        population = self.toolbox.population(n=self.population_size)
        
        # Statistics
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", lambda x: sum(v[0] for v in x) / len(x) if x else 0)
        stats.register("max", lambda x: max(v[0] for v in x) if x else 0)
        
        # Run evolution with progress bar
        print("  Running genetic algorithm...")
        hall_of_fame = tools.HallOfFame(1)
        
        total_evals = self.population_size * self.generations
        with tqdm(total=total_evals, desc="  Progress", unit="eval") as pbar:
            for gen in range(self.generations):
                # Select next generation
                offspring = self.toolbox.select(population, len(population))
                offspring = list(map(self.toolbox.clone, offspring))
                
                # Apply crossover and mutation
                for child1, child2 in zip(offspring[::2], offspring[1::2]):
                    if random.random() < 0.7:  # 70% crossover rate
                        self.toolbox.mate(child1, child2)
                        del child1.fitness.values
                        del child2.fitness.values
                
                for mutant in offspring:
                    if random.random() < self.mutation_rate:
                        self.toolbox.mutate(mutant)
                        del mutant.fitness.values
                
                # Evaluate individuals with invalid fitness
                invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
                fitnesses = map(self.toolbox.evaluate, invalid_ind)
                for ind, fit in zip(invalid_ind, fitnesses):
                    ind.fitness.values = fit
                
                population[:] = offspring
                hall_of_fame.update(population)
                
                pbar.update(len(population))
        
        # Get best individual
        best_ind = hall_of_fame[0]
        best_params = {
            'position_pct': best_ind[0],
            'profit_target': best_ind[1],
            'stop_loss': best_ind[2],
        }
        
        print(f"  Best Fitness: {best_ind.fitness.values[0]:.2f}")
        print(f"  Best params: {best_params}")
        
        return {
            'bot': bot_config['name'],
            'timeframe': timeframe,
            'lookback': lookback,
            'params': best_params,
            'fitness': best_ind.fitness.values[0],
            'total_evaluations': total_evals,
        }


def main():
    parser = argparse.ArgumentParser(description='Genetic Algorithm Optimizer')
    parser.add_argument('--population', type=int, default=20,
                       help='Population size (default: 20)')
    parser.add_argument('--generations', type=int, default=10,
                       help='Number of generations (default: 10)')
    parser.add_argument('--mutation', type=float, default=0.2,
                       help='Mutation rate (default: 0.2)')
    args = parser.parse_args()
    
    print("=" * 80)
    print("GENETIC ALGORITHM OPTIMIZER (DEAP)")
    print("=" * 80)
    print(f"Population size: {args.population}")
    print(f"Generations: {args.generations}")
    print(f"Mutation rate: {args.mutation}")
    print(f"Total evaluations: {args.population * args.generations}")
    print("=" * 80)
    
    optimizer = GeneticOptimizer(
        population_size=args.population,
        generations=args.generations,
        mutation_rate=args.mutation
    )
    
    all_results = []
    
    for bot in BOT_DEFINITIONS:
        print(f"\n{'=' * 80}")
        print(f"Bot: {bot['name']} ({bot['symbol']})")
        print(f"{'=' * 80}")
        
        strategy_func = bot.get("strategy_func")
        if strategy_func is None:
            print("Strategy function not implemented, skipping...")
            continue
        
        timeframes = TIMEFRAMES if bot["name"].startswith("Crypto") else ["1d"]
        
        for timeframe in timeframes:
            for lookback in LOOKBACK_DAYS:
                result = optimizer.optimize_configuration(bot, timeframe, lookback)
                if result:
                    all_results.append(result)
    
    # Save results
    if all_results:
        df_results = pd.DataFrame(all_results)
        csv_path = Path("backtests/genetic_optimizer_results.csv")
        df_results.to_csv(csv_path, index=False)
        print(f"\n{'=' * 80}")
        print(f"Results saved to: {csv_path.resolve()}")
        print("=" * 80)


if __name__ == "__main__":
    main()
