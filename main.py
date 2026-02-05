"""
Crypto Options Alpha Bot - Multi Asset
BTC + ETH + SOL with News Guard and Time Filter
"""

import asyncio
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Config
from config.settings import (
    BINANCE_API_KEY, BINANCE_API_SECRET,
    COINDCX_API_KEY, COINDCX_API_SECRET,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    TRADING_CONFIG, STEALTH_CONFIG, ASSETS_CONFIG, ASSET_THRESHOLDS
)

# Core
from core.stealth_request import StealthRequest
from core.data_aggregator import DataAggregator, AssetData
from core.multi_asset_manager import MultiAssetManager, TradingSignal
from core.time_filter import TimeFilter
from core.news_guard import news_guard, NEWS_QUICK_REFERENCE

# Indicators
from indicators.greeks_engine import GreeksEngine

# Strategies
from strategies.liquidity_hunt import LiquidityHuntStrategy
from strategies.gamma_squeeze import GammaSqueezeStrategy

# Signals
from signals.scorer import AlphaScorer

# Telegram
from telegram.bot import AlphaTelegramBot

# Setup logging
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
    """Multi-Asset Alpha Bot with full protection"""
    
    def __init__(self):
        logger.info("🚀 Initializing Multi-Asset Alpha Bot")
        logger.info(f"Assets: {TRADING_CONFIG['assets']}")
        logger.info("Features: News Guard + Time Filter + Multi-Strategy")
        
        # Core components
        self.stealth = StealthRequest(STEALTH_CONFIG)
        self.data_agg = DataAggregator(self.stealth)
        self.asset_manager = MultiAssetManager(TRADING_CONFIG, ASSETS_CONFIG)
        self.time_filter = TimeFilter()
        self.news_guard = news_guard
        self.greeks_engine = GreeksEngine()
        self.scorer = AlphaScorer(TRADING_CONFIG)
        self.telegram = AlphaTelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        
        # Asset-specific strategies
        self.strategies = {}
        for asset in TRADING_CONFIG['assets']:
            thresholds = ASSET_THRESHOLDS.get(asset, ASSET_THRESHOLDS['BTC'])
            config = {**ASSETS_CONFIG[asset], **thresholds}
            self.strategies[asset] = {
                'liquidity': LiquidityHuntStrategy(asset, config),
                'gamma': GammaSqueezeStrategy(asset, config, self.greeks_engine)
            }
        
        # State
        self.running = False
        self.cycle_count = 0
        
        logger.info("✅ Bot initialized successfully")
    
    async def run(self):
        """Main loop with full protection"""
        self.running = True
        
        # Startup message
        await self._send_startup_message()
        
        while self.running:
            try:
                self.cycle_count += 1
                logger.info(f"\n{'='*50}")
                logger.info(f"🔄 Cycle #{self.cycle_count} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'='*50}")
                
                # Step 1: Check News Guard (highest priority)
                trading_allowed, news_reason = await self.news_guard.check_trading_allowed()
                
                if not trading_allowed:
                    logger.warning(f"🛑 NEWS GUARD: {news_reason}")
                    if self.cycle_count % 10 == 1:  # Send alert every 10 cycles
                        await self.telegram.send_status(
                            f"⏸️ TRADING HALTED\n\n"
                            f"Reason: {news_reason}\n"
                            f"Next check: 5 minutes"
                        )
                    await asyncio.sleep(300)  # 5 minute sleep during events
                    continue
                
                if "caution" in news_reason.lower():
                    logger.info(f"⚠️ NEWS GUARD: {news_reason}")
                
                # Step 2: Check Time Filter
                is_good_time, time_info = self.time_filter.is_best_time()
                time_quality = time_info.get('quality', 'unknown')
                
                if time_quality == 'avoid' and not self._is_exceptional_opportunity_expected():
                    logger.info(f"⏰ TIME FILTER: {time_info.get('reason', 'Avoid time')}")
                    sleep_time = self.time_filter.get_sleep_time()
                    logger.info(f"😴 Sleeping {sleep_time//60} minutes...")
                    await asyncio.sleep(sleep_time)
                    continue
                
                logger.info(f"⏰ TIME FILTER: {time_info.get('session', 'Regular')} ({time_quality})")
                
                # Step 3: Check daily reset
                if self.asset_manager.should_reset_daily():
                    self.asset_manager.reset_daily_counters()
                    await self.telegram.send_status("🌅 Daily counters reset")
                
                # Step 4: Fetch market data for all assets
                logger.info("📊 Fetching market data...")
                assets_data = await self.data_agg.get_all_assets_data(ASSETS_CONFIG)
                
                if not assets_data:
                    logger.error("❌ No market data received")
                    await asyncio.sleep(60)
                    continue
                
                logger.info(f"✅ Data received for: {', '.join(assets_data.keys())}")
                
                # Step 5: Analyze each asset
                all_signals = []
                
                for asset, data in assets_data.items():
                    if not self.asset_manager.can_send_signal(asset):
                        logger.info(f"⏭️ {asset}: Daily limit reached")
                        continue
                    
                    asset_signals = await self._analyze_asset(asset, data)
                    
                    # Apply time filter to each signal
                    for sig in asset_signals:
                        should_process, filter_reason = self.time_filter.should_process_signal(asset, sig)
                        
                        if should_process:
                            # Add metadata
                            sig['time_quality'] = time_quality
                            sig['news_status'] = news_reason
                            all_signals.append(sig)
                            logger.info(f"✅ {asset} signal ACCEPTED: {filter_reason}")
                        else:
                            logger.info(f"❌ {asset} signal REJECTED: {filter_reason}")
                    
                    # Small delay between assets
                    await asyncio.sleep(1)
                
                # Step 6: Process signals
                if all_signals:
                    await self._process_signals(all_signals, assets_data)
                else:
                    logger.info("📭 No signals this cycle")
                
                # Step 7: Dynamic sleep
                sleep_time = self._calculate_sleep_time(time_quality, len(all_signals))
                logger.info(f"⏳ Sleeping {sleep_time} seconds...")
                await asyncio.sleep(sleep_time)
                
            except KeyboardInterrupt:
                logger.info("🛑 Shutdown requested")
                await self.stop()
                break
                
            except Exception as e:
                logger.error(f"❌ Main loop error: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _send_startup_message(self):
        """Send comprehensive startup message"""
        
        # Get upcoming events
        upcoming = await self.news_guard.fetch_economic_calendar()
        calendar_text = "📅 UPCOMING EVENTS:\n"
        
        if upcoming:
            for event in upcoming:
                calendar_text += f"• {event['event']}: {event['date']} ({event['days_until']} days)\n"
        else:
            calendar_text += "• No major events in next 7 days\n"
        
        # Get time filter schedule
        schedule = self.time_filter.format_schedule()
        
        message = (
            "🟢 <b>ALPHA BOT STARTED</b>\n\n"
            f"<b>Assets:</b> <code>{', '.join(TRADING_CONFIG['assets'])}</code>\n"
            f"<b>Max Signals:</b> {TRADING_CONFIG['max_signals_per_day']}/day\n"
            f"<b>Min Score:</b> {TRADING_CONFIG['min_score_threshold']}\n\n"
            f"{calendar_text}\n"
            f"<pre>{schedule}</pre>\n\n"
            f"<b>Protection Active:</b>\n"
            f"✅ News Guard (FOMC/CPI/NFP)\n"
            f"✅ Time Filter (Market hours)\n"
            f"✅ Correlation Filter\n"
            f"✅ Volatility Spike Detection"
        )
        
        await self.telegram.send_status(message)
        logger.info("Startup message sent")
    
    async def _analyze_asset(self, asset: str, data: AssetData) -> list:
        """Analyze single asset with all strategies"""
        
        signals = []
        
        try:
            # Get recent trades for CVD
            trades = await self.data_agg.get_recent_trades(
                ASSETS_CONFIG[asset]['symbol'],
                limit=100
            )
            
            # Prepare market data dict
            market_dict = {
                'orderbook': data.orderbook,
                'spot_price': data.spot_price,
                'perp_price': data.perp_price,
                'funding_rate': data.funding_rate,
                'open_interest': data.open_interest,
                'volume_24h': data.volume_24h,
                'timestamp': data.timestamp
            }
            
            # Strategy 1: Liquidity Hunt
            liq_signal = await self.strategies[asset]['liquidity'].analyze(market_dict, trades)
            
            if liq_signal:
                liq_signal['asset'] = asset
                liq_signal['market_data'] = market_dict
                signals.append(liq_signal)
                logger.info(f"🎯 {asset} Liquidity Hunt: {liq_signal['direction']} @ {liq_signal['entry_price']}")
            
            # Strategy 2: Gamma Squeeze
            chain = self._generate_mock_chain(asset, data.spot_price)
            gamma_signal = await self.strategies[asset]['gamma'].analyze(market_dict, chain)
            
            if gamma_signal:
                gamma_signal['asset'] = asset
                gamma_signal['market_data'] = market_dict
                signals.append(gamma_signal)
                logger.info(f"🎯 {asset} Gamma Squeeze: {gamma_signal['direction']} @ {gamma_signal['entry_price']}")
            
        except Exception as e:
            logger.error(f"❌ Error analyzing {asset}: {e}")
        
        return signals
    
    def _generate_mock_chain(self, asset: str, spot: float) -> list:
        """Generate realistic options chain"""
        
        import random
        random.seed(42)  # Reproducible
        
        config = ASSETS_CONFIG[asset]
        step = config['strike_step']
        base = round(spot / step) * step
        
        chain = []
        for i in range(-10, 11):
            strike = base + (i * step)
            distance = abs(i)
            
            # OI higher near ATM
            oi_base = max(15 - distance, 3) * 100
            
            chain.append({
                'strike': strike,
                'call_oi': oi_base * (0.8 + random.random() * 0.4),
                'put_oi': oi_base * (0.8 + random.random() * 0.4),
                'call_iv': 0.45 + distance * 0.015 + random.random() * 0.02,
                'put_iv': 0.45 + distance * 0.015 + random.random() * 0.02
            })
        
        return chain
    
    async def _process_signals(self, signals: list, assets_data: dict):
        """Process and rank all signals"""
        
        # Convert to TradingSignal objects with full scoring
        trading_signals = []
        
        for sig in signals:
            asset = sig['asset']
            market_data = sig.pop('market_data', {})
            
            # Get time and news status
            time_quality = sig.pop('time_quality', 'moderate')
            news_status = sig.pop('news_status', 'safe')
            
            # Calculate comprehensive score
            score_data = self.scorer.calculate_score(sig, market_data, news_status, time_quality)
            
            # Skip if below threshold
            if score_data['total_score'] < TRADING_CONFIG['min_score_threshold']:
                logger.info(f"❌ {asset} score {score_data['total_score']} below threshold")
                continue
            
            # Calculate position size
            pos_size = self.asset_manager.calculate_position_size(
                asset, sig['entry_price'], sig['stop_loss']
            )
            
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
                confidence=score_data['total_score'],
                score_breakdown=score_data,
                rationale={
                    **sig.get('rationale', {}),
                    'score_components': score_data['component_scores'],
                    'time_note': score_data.get('time_adjustment', ''),
                    'news_note': score_data.get('news_adjustment', '')
                },
                timestamp=datetime.now()
            ))
        
        if not trading_signals:
            logger.info("No signals passed scoring")
            return
        
        # Filter correlated signals
        filtered = self.asset_manager.filter_correlated_signals(trading_signals)
        
        # Rank by score
        ranked = sorted(filtered, key=lambda x: x.confidence, reverse=True)
        
        # Send top signals
        max_to_send = min(len(ranked), TRADING_CONFIG['max_signals_per_day'])
        
        for i, signal in enumerate(ranked[:max_to_send], 1):
            await self._send_signal(signal, assets_data[signal.asset])
            self.asset_manager.record_signal(signal.asset)
            
            if i < max_to_send:
                await asyncio.sleep(3)  # Small delay between messages
        
        logger.info(f"📤 Sent {min(max_to_send, len(ranked))} signals")
    
    async def _send_signal(self, signal: TradingSignal, market_data: AssetData):
        """Send formatted signal to Telegram"""
        
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
            'position_size': getattr(signal, 'position_size', 0),
            'confidence': signal.confidence
        }
        
        score_data = signal.score_breakdown
        
        await self.telegram.send_signal(setup, score_data, {
            'orderbook': market_data.orderbook,
            'spot_price': market_data.spot_price,
            'funding_rate': market_data.funding_rate
        })
        
        logger.info(f"📨 Signal sent: {signal.asset} {signal.strategy} | Score: {signal.confidence:.1f}")
    
    def _calculate_sleep_time(self, time_quality: str, signal_count: int) -> int:
        """Calculate dynamic sleep time"""
        
        base_sleep = 60  # Default 1 minute
        
        if time_quality == 'excellent':
            base_sleep = 45  # Check more frequently
        elif time_quality == 'moderate':
            base_sleep = 120  # 2 minutes
        elif time_quality == 'avoid':
            base_sleep = 600  # 10 minutes
        
        # If we found signals, check sooner
        if signal_count > 0:
            base_sleep = max(30, base_sleep // 2)
        
        return base_sleep
    
    def _is_exceptional_opportunity_expected(self) -> bool:
        """Check if we should override avoid time for exceptional setup"""
        # Could check for extreme volatility indicating opportunity
        return False
    
    async def send_status_update(self):
        """Send periodic status"""
        status = (
            f"📊 <b>Bot Status</b>\n\n"
            f"Cycles: {self.cycle_count}\n"
            f"{self.asset_manager.get_asset_status()}\n\n"
            f"Next events:\n{await self.news_guard.fetch_economic_calendar()}"
        )
        await self.telegram.send_status(status)
    
    async def stop(self):
        """Graceful shutdown"""
        self.running = False
        await self.telegram.send_status(
            "🔴 <b>Bot Stopped</b>\n\n"
            f"Total cycles: {self.cycle_count}\n"
            f"Final status:\n{self.asset_manager.get_asset_status()}"
        )
        logger.info("Bot stopped gracefully")

async def main():
    """Entry point"""
    bot = AlphaBot()
    
    try:
        await bot.run()
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main())
