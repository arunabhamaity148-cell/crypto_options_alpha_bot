"""
Performance Tracker with Circuit Breaker
"""

import logging
from typing import Dict, List
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)

class PerformanceTracker:
    def __init__(self):
        self.trades = []
        self.daily_trades = []
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.max_consecutive_losses = 3
        self.max_daily_losses = 5
        self.win_rate_threshold = 0.55
        self.profit_factor_threshold = 1.2
        
    def add_trade(self, result: str, pnl: float, asset: str = ''):
        """Record trade result"""
        trade = {
            'result': result,
            'pnl': pnl,
            'asset': asset,
            'time': datetime.now(),
            'date': datetime.now().date()
        }
        
        self.trades.append(trade)
        self.daily_trades.append(trade)
        
        # Update consecutive counters
        if result == 'win':
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        
        # Log performance
        logger.info(f"Trade recorded: {result} | PnL: {pnl:.2f}% | "
                   f"Consecutive losses: {self.consecutive_losses}")
        
        # Check circuit breaker
        if self.consecutive_losses >= self.max_consecutive_losses:
            return {
                'action': 'circuit_breaker',
                'message': f'{self.max_consecutive_losses} consecutive losses',
                'cooldown_minutes': 60
            }
        
        # Check daily loss limit
        daily_losses = sum(1 for t in self.daily_trades if t['result'] == 'loss')
        if daily_losses >= self.max_daily_losses:
            return {
                'action': 'daily_limit',
                'message': f'{self.max_daily_losses} losses today',
                'cooldown_minutes': 240  # 4 hours
            }
        
        return {'action': 'continue'}
    
    def get_stats(self) -> Dict:
        """Get overall performance stats"""
        if not self.trades:
            return {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'profit_factor': 0
            }
        
        wins = sum(1 for t in self.trades if t['result'] == 'win')
        losses = len(self.trades) - wins
        
        win_trades = [t for t in self.trades if t['result'] == 'win']
        loss_trades = [t for t in self.trades if t['result'] == 'loss']
        
        total_profit = sum(t['pnl'] for t in win_trades) if win_trades else 0
        total_loss = abs(sum(t['pnl'] for t in loss_trades)) if loss_trades else 1
        
        return {
            'total_trades': len(self.trades),
            'wins': wins,
            'losses': losses,
            'win_rate': wins / len(self.trades),
            'profit_factor': total_profit / total_loss if total_loss > 0 else 0,
            'total_pnl': sum(t['pnl'] for t in self.trades),
            'consecutive_losses': self.consecutive_losses,
            'consecutive_wins': self.consecutive_wins
        }
    
    def today_stats(self) -> Dict:
        """Get today's stats"""
        today = datetime.now().date()
        today_trades = [t for t in self.daily_trades if t['date'] == today]
        
        if not today_trades:
            return {'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0}
        
        wins = sum(1 for t in today_trades if t['result'] == 'win')
        
        return {
            'trades': len(today_trades),
            'wins': wins,
            'losses': len(today_trades) - wins,
            'pnl': sum(t['pnl'] for t in today_trades)
        }
    
    def get_win_rate(self) -> float:
        """Get current win rate"""
        if not self.trades:
            return 0
        wins = sum(1 for t in self.trades if t['result'] == 'win')
        return wins / len(self.trades)
    
    def get_profit_factor(self) -> float:
        """Get profit factor"""
        win_trades = [t for t in self.trades if t['result'] == 'win']
        loss_trades = [t for t in self.trades if t['result'] == 'loss']
        
        total_profit = sum(t['pnl'] for t in win_trades)
        total_loss = abs(sum(t['pnl'] for t in loss_trades))
        
        return total_profit / total_loss if total_loss > 0 else 0
    
    def reset_daily(self):
        """Reset daily counters"""
        self.daily_trades = []
        logger.info("Daily performance counters reset")
    
    def should_reduce_size(self) -> Tuple[bool, float]:
        """Check if position size should be reduced"""
        stats = self.get_stats()
        
        # Reduce size if win rate dropping
        if stats['win_rate'] < self.win_rate_threshold and len(self.trades) > 10:
            return True, 0.5
        
        # Reduce size if profit factor poor
        if stats['profit_factor'] < self.profit_factor_threshold and len(self.trades) > 10:
            return True, 0.5
        
        return False, 1.0
