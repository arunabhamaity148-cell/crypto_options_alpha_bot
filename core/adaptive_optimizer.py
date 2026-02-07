"""
Adaptive Optimizer - FREE Upgrade
Learns from trade history and improves over time
"""

import json
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class SetupPerformance:
    setup_key: str
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    last_updated: str = ""

class AdaptiveOptimizer:
    """Self-improving trading optimizer"""
    
    DATA_FILE = "data/setup_performance.json"
    MIN_SAMPLES = 3  # Minimum trades before trusting stats
    
    def __init__(self):
        self.performance: Dict[str, SetupPerformance] = {}
        self.recent_trades: List[Dict] = []
        self.load_data()
    
    def load_data(self):
        """Load historical performance"""
        try:
            path = Path(self.DATA_FILE)
            if path.exists():
                with open(path, 'r') as f:
                    data = json.load(f)
                    for key, val in data.items():
                        self.performance[key] = SetupPerformance(**val)
                logger.info(f"Loaded {len(self.performance)} setup profiles")
        except Exception as e:
            logger.error(f"Failed to load performance data: {e}")
    
    def save_data(self):
        """Save performance data"""
        try:
            Path(self.DATA_FILE).parent.mkdir(parents=True, exist_ok=True)
            with open(self.DATA_FILE, 'w') as f:
                data = {k: asdict(v) for k, v in self.performance.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save performance data: {e}")
    
    def extract_setup_key(self, setup: Dict) -> str:
        """Create unique key for setup type"""
        strategy = setup.get('strategy', 'unknown')
        direction = setup.get('direction', 'unknown')
        asset = setup.get('asset', 'unknown')
        
        # Add regime if available
        regime = setup.get('regime', 'unknown')
        
        # Add time of day (session)
        hour = datetime.now(timezone.utc).hour
        if 13 <= hour < 16:  # US Open
            session = 'us_open'
        elif 19 <= hour < 22:  # US Active
            session = 'us_active'
        elif 0 <= hour < 4:  # Asia
            session = 'asia'
        else:
            session = 'other'
        
        return f"{strategy}_{direction}_{asset}_{regime}_{session}"
    
    def should_take_signal(self, setup: Dict) -> Tuple[bool, float, str]:
        """Decide whether to take signal and position size"""
        key = self.extract_setup_key(setup)
        perf = self.performance.get(key)
        
        if not perf or (perf.wins + perf.losses) < self.MIN_SAMPLES:
            # Not enough data - take with caution
            return True, 0.8, "insufficient_data"
        
        total = perf.wins + perf.losses
        win_rate = perf.wins / total
        
        # Calculate profit factor
        avg_profit = perf.avg_profit if perf.avg_profit > 0 else 1
        avg_loss = abs(perf.avg_loss) if perf.avg_loss < 0 else 1
        profit_factor = avg_profit / avg_loss if avg_loss > 0 else 1
        
        # Decision logic
        if win_rate >= 0.75 and profit_factor >= 2.0:
            return True, 1.3, f"excellent_{win_rate:.2f}_pf_{profit_factor:.1f}"
        
        elif win_rate >= 0.65 and profit_factor >= 1.5:
            return True, 1.1, f"good_{win_rate:.2f}_pf_{profit_factor:.1f}"
        
        elif win_rate >= 0.55 and profit_factor >= 1.2:
            return True, 1.0, f"acceptable_{win_rate:.2f}_pf_{profit_factor:.1f}"
        
        elif win_rate < 0.4 or profit_factor < 0.8:
            logger.warning(f"Poor performance for {key}: WR={win_rate:.2f}, PF={profit_factor:.1f}")
            return False, 0.0, f"poor_{win_rate:.2f}_pf_{profit_factor:.1f}"
        
        else:
            # Marginal - reduce size
            return True, 0.7, f"marginal_{win_rate:.2f}_pf_{profit_factor:.1f}"
    
    def record_trade(self, setup: Dict, result: Dict):
        """Record trade outcome for learning"""
        key = self.extract_setup_key(setup)
        
        if key not in self.performance:
            self.performance[key] = SetupPerformance(setup_key=key)
        
        perf = self.performance[key]
        pnl = result.get('pnl_percent', 0)
        
        # Update stats
        if pnl > 0:
            perf.wins += 1
            perf.total_pnl += pnl
            # Update avg profit
            perf.avg_profit = ((perf.avg_profit * (perf.wins - 1)) + pnl) / perf.wins
        else:
            perf.losses += 1
            perf.total_pnl += pnl
            # Update avg loss
            perf.avg_loss = ((perf.avg_loss * (perf.losses - 1)) + pnl) / perf.losses
        
        perf.last_updated = datetime.now(timezone.utc).isoformat()
        
        # Keep recent trades in memory
        self.recent_trades.append({
            'key': key,
            'pnl': pnl,
            'time': perf.last_updated
        })
        
        # Trim if too many
        if len(self.recent_trades) > 1000:
            self.recent_trades = self.recent_trades[-500:]
        
        # Save periodically
        if (perf.wins + perf.losses) % 5 == 0:
            self.save_data()
        
        logger.info(f"Recorded trade for {key}: {pnl:+.2f}% | "
                   f"Total: {perf.wins}W/{perf.losses}L | "
                   f"Cumulative: {perf.total_pnl:+.2f}%")
    
    def get_setup_stats(self, setup: Dict) -> Optional[Dict]:
        """Get statistics for a setup type"""
        key = self.extract_setup_key(setup)
        perf = self.performance.get(key)
        
        if not perf:
            return None
        
        total = perf.wins + perf.losses
        return {
            'setup_key': key,
            'total_trades': total,
            'wins': perf.wins,
            'losses': perf.losses,
            'win_rate': perf.wins / total if total > 0 else 0,
            'total_pnl': perf.total_pnl,
            'avg_profit': perf.avg_profit,
            'avg_loss': perf.avg_loss,
            'profit_factor': abs(perf.avg_profit / perf.avg_loss) if perf.avg_loss != 0 else 0
        }
    
    def get_best_setups(self, min_trades: int = 5) -> List[Dict]:
        """Get top performing setup types"""
        qualified = []
        
        for key, perf in self.performance.items():
            total = perf.wins + perf.losses
            if total >= min_trades:
                win_rate = perf.wins / total
                pf = abs(perf.avg_profit / perf.avg_loss) if perf.avg_loss != 0 else 0
                score = win_rate * pf  # Composite score
                
                qualified.append({
                    'setup_key': key,
                    'win_rate': win_rate,
                    'profit_factor': pf,
                    'total_trades': total,
                    'score': score
                })
        
        return sorted(qualified, key=lambda x: x['score'], reverse=True)[:10]
    
    def get_global_stats(self) -> Dict:
        """Get overall performance statistics"""
        total_wins = sum(p.wins for p in self.performance.values())
        total_losses = sum(p.losses for p in self.performance.values())
        total_pnl = sum(p.total_pnl for p in self.performance.values())
        
        return {
            'total_setups_tracked': len(self.performance),
            'total_trades': total_wins + total_losses,
            'total_wins': total_wins,
            'total_losses': total_losses,
            'overall_win_rate': total_wins / (total_wins + total_losses) if (total_wins + total_losses) > 0 else 0,
            'total_pnl': total_pnl,
            'best_setups': self.get_best_setups(min_trades=3)
        }

# Global instance
adaptive_optimizer = AdaptiveOptimizer()
