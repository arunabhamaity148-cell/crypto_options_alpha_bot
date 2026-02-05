"""
Crypto Options Alpha Bot - Multi Asset
BTC + ETH + SOL
"""

import asyncio
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from config.settings import (
    BINANCE_API_KEY, BINANCE_API_SECRET,
    COINDCX_API_KEY, COINDCX_API_SECRET,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    TRADING_CONFIG, STEALTH_CONFIG, ASSETS_CONFIG, ASSET_THRESHOLDS
)

from core.stealth_request import StealthRequest
from core.data_aggregator import DataAggregator
from core.multi_asset_manager import MultiAssetManager, TradingSignal
from indicators.greeks_engine import GreeksEngine
from strategies.liquidity_hunt import LiquidityHuntStrategy
from strategies.gamma_squeeze import GammaSqueezeStrategy
from signals.scorer import AlphaScorer
from telegram.bot import AlphaTelegramBot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AlphaBot:
    """Multi-Asset Alpha Bot"""
    
    def __init__(self):
        logger.info("🚀 Starting Multi-Asset Alpha Bot (BTC+ETH+SOL)")
        
        self.stealth = StealthRequest(STEALTH_CONFIG)
        self.data_agg = DataAggregator(self.stealth)
        self.asset_manager = MultiAssetManager(TRADING_CONFIG, ASSETS_CONFIG)
        self.greeks_engine = GreeksEngine()
        self.scorer = AlphaScorer(TRADING_CONFIG)
        self.telegram = AlphaTelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        
        # Initialize strategies for each asset
        self.strategies = {}
        for asset in TRADING_CONFIG['assets']:
            thresholds = ASSET_THRESHOLDS.get(asset, ASSET_THRESHOLDS['BTC'])
            config = {**ASSETS_CONFIG[asset], **thresholds}
            self.strategies[asset] = {
                'liquidity': LiquidityHuntStrategy(asset, config),
                'gamma': GammaSqueezeStrategy(asset, config, self.greeks_engine)
            }
        
        self.running = False
        
        logger.info("✅ Bot initialized")
    
    async def run(self):
        """Main loop"""
        self.running = True
        
        await self.telegram.send_status(
            "🟢 <b>Multi-Asset Bot Started</b>\n\n"
            f"Assets: <code>{', '.join(TRADING_CONFIG['assets'])}</code>\n"
            f"Max Signals: {TRADING_CONFIG['max_signals_per_day']}/day\n"
            f"Per Asset: {TRADING_CONFIG['max_signals_per_asset']}\n"
            f"Min Score: {TRADING_CONFIG['min_score_threshold']}"
        )
        
        while self.running:
            try:
                # Check daily reset
                if self.asset_manager.should_reset_daily():
                    self.asset_manager.reset_daily_counters()
                
                # Fetch all asset data
                logger.info("📊 Fetching market data...")
                assets_data = await self.data_agg.get_all_assets_data(ASSETS_CONFIG)
                
                # Analyze each asset
                signals = []
                for asset, data in assets_data.items():
                    if not self.asset_manager.can_send_signal(asset):
                        continue
                    
                    asset_signals = await self._analyze_asset(asset, data)
                    signals.extend(asset_signals)
                
                # Filter and rank
                if signals:
                    trading_signals = self._convert_to_trading_signals(signals, assets_data)
                    filtered = self.asset_manager.filter_correlated_signals(trading_signals)
                    ranked = sorted(filtered, key=lambda x: x.confidence, reverse=True)
                    
                    # Send top signals
                    for signal in ranked[:TRADING_CONFIG['max_signals_per_day']]:
                        await self._send_signal(signal, assets_data[signal.asset])
                        self.asset_manager.record_signal(signal.asset)
                        await asyncio.sleep(5)
                
                # Status every hour
                if datetime.now().minute == 0:
                    await self.telegram.send_status(self.asset_manager.get_asset_status())
                
                logger.info("⏳ Cycle complete. Sleeping...")
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                await asyncio.sleep(60)
    
    async def _analyze_asset(self, asset: str, data) -> list:
        """Analyze single asset"""
        signals = []
        
        try:
            # Get recent trades for CVD
            trades = await self.data_agg.get_recent_trades(
                ASSETS_CONFIG[asset]['symbol'], 
                limit=100
            )
            
            # Run strategies
            liq = await self.strategies[asset]['liquidity'].analyze(
                {'orderbook': data.orderbook, 'funding_rate': data.funding_rate}, 
                trades
            )
            if liq:
                liq['asset'] = asset
                signals.append(liq)
            
            # Mock options chain for gamma
            chain = self._generate_chain(asset, data.spot_price)
            gamma = await self.strategies[asset]['gamma'].analyze(
                {'orderbook': {'mid_price': data.spot_price}, 'funding_rate': data.funding_rate},
                chain
            )
            if gamma:
                gamma['asset'] = asset
                signals.append(gamma)
            
        except Exception as e:
            logger.error(f"Error analyzing {asset}: {e}")
        
        return signals
    
    def _generate_chain(self, asset: str, spot: float) -> list:
        """Generate options chain"""
        import random
        step = ASSETS_CONFIG[asset]['strike_step']
        base = round(spot / step) * step
        
        chain = []
        for i in range(-8, 9):
            strike = base + (i * step)
            oi = max(10 - abs(i), 2) * 100
            chain.append({
                'strike': strike,
                'call_oi': oi * (1 + random.random()),
                'put_oi': oi * (1 + random.random()),
                'call_iv': 0.5 + abs(i) * 0.02,
                'put_iv': 0.5 + abs(i) * 0.02
            })
        return chain
    
    def _convert_to_trading_signals(self, signals: list, assets_data: dict) -> list:
        """Convert to TradingSignal objects"""
        trading_signals = []
        
        for sig in signals:
            asset = sig['asset']
            data = assets_data.get(asset)
            
            # Calculate position size
            pos_size = self.asset_manager.calculate_position_size(
                asset, sig['entry_price'], sig['stop_loss']
            )
            sig['position_size'] = pos_size
            
            trading_signals.append(TradingSignal(
                asset=asset,
                strategy=sig['strategy'],
                direction=sig['direction'],
                entry_price=sig['entry_price'],
                stop_loss=sig['stop_loss'],
                target_1=sig['target_1'],
                target_2=sig['target_2'],
                strike_selection=sig['strike_selection'],
                expiry_suggestion=sig['expiry_suggestion'],
                confidence=sig['confidence'],
                score_breakdown={},
                rationale=sig['rationale'],
                timestamp=datetime.now()
            ))
        
        return trading_signals
    
    async def _send_signal(self, signal: TradingSignal, market_data):
        """Send signal to Telegram"""
        
        # Build setup dict
        setup = {
            'asset': signal.asset,
            'strategy': signal.strategy,
            'direction': signal.direction,
            'entry_price': signal.entry_price,
            'stop_loss': signal.stop_loss,
            'target_1': signal.target_1,
            'target_2': signal.target_2,
            'strike_selection': signal.strike_selection,
            'expiry_suggestion': signal.expiry_suggestion,
            'rationale': signal.rationale,
            'position_size': getattr(signal, 'position_size', 0)
        }
        
        # Calculate score
        market_dict = {
            'orderbook': market_data.orderbook,
            'funding_rate': market_data.funding_rate
        }
        score_data = self.scorer.calculate_score(setup, market_dict)
        
        # Update confidence with real score
        setup['confidence'] = score_data['total_score']
        
        # Only send if passes threshold
        if score_data['total_score'] >= TRADING_CONFIG['min_score_threshold']:
            await self.telegram.send_signal(setup, score_data, market_dict)
            logger.info(f"✅ Signal sent: {signal.asset} {signal.strategy} | Score: {score_data['total_score']}")
        else:
            logger.info(f"❌ Signal rejected: {signal.asset} | Score: {score_data['total_score']}")
    
    async def stop(self):
        self.running = False
        await self.telegram.send_status("🔴 Bot stopped")

async def main():
    bot = AlphaBot()
    try:
        await bot.run()
    except KeyboardInterrupt:
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
