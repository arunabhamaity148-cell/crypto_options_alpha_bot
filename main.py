"""
Crypto Options Alpha Bot - Part 1: Core Classes
BTC + ETH + SOL with News Guard, Time Filter, Trade Monitor
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from config.settings import (
    BINANCE_API_KEY, BINANCE_API_SECRET,
    COINDCX_API_KEY, COINDCX_API_SECRET,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    TRADING_CONFIG, STEALTH_CONFIG, ASSETS_CONFIG, ASSET_THRESHOLDS
)

from core.stealth_request import StealthRequest
from core.data_aggregator import DataAggregator, AssetData
from core.multi_asset_manager import MultiAssetManager, TradingSignal
from core.time_filter import TimeFilter
from core.news_guard import news_guard, NEWS_QUICK_REFERENCE
from core.trade_monitor import TradeMonitor, ActiveTrade

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
    """Multi-Asset Alpha Bot with full protection"""
    
    def __init__(self):
        logger.info("🚀 Initializing Alpha Bot")
        logger.info(f"Assets: {TRADING_CONFIG['assets']}")
        
        # Core components
        self.stealth = StealthRequest(STEALTH_CONFIG)
        self.data_agg = DataAggregator(self.stealth)
        self.asset_manager = MultiAssetManager(TRADING_CONFIG, ASSETS_CONFIG)
        self.time_filter = TimeFilter()
        self.news_guard = news_guard
        self.greeks_engine = GreeksEngine()
        self.scorer = AlphaScorer(TRADING_CONFIG)
        self.telegram = AlphaTelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        self.trade_monitor = TradeMonitor(self.telegram)
        
        # Strategies
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
        self._alerted_events = set()
        
        logger.info("✅ Bot initialized")
    
    # ========== BACKGROUND TASKS ==========
    
    async def _news_watcher(self):
        """Continuous news monitoring"""
        logger.info("📰 News watcher started")
        
        while self.running:
            try:
                await asyncio.sleep(120)  # 2 min check
                
                # Check breaking news
                sentiment = await self.news_guard.get_news_sentiment()
                
                if sentiment.get('breaking_news'):
                    await self.telegram.send_news_alert(
                        "🚨 BREAKING NEWS",
                        sentiment.get('headline', 'Major news detected'),
                        "high",
                        "Review before trading"
                    )
                
                # Check upcoming events
                events = await self.news_guard.fetch_economic_calendar()
                
                for event in events:
                    if event.get('hours_until', 999) <= 24:
                        key = f"{event['event']}_{event['date']}"
                        
                        if key not in self._alerted_events:
                            self._alerted_events.add(key)
                            
                            await self.telegram.send_news_alert(
                                f"📅 UPCOMING: {event['event']}",
                                f"Date: {event['date']}\nImpact: {event.get('impact', 'high')}",
                                event.get('impact', 'high'),
                                f"Avoid ±2 hours of {event['event']}"
                            )
                
                # Check if trading should halt
                is_safe, reason = await self.news_guard.check_trading_allowed()
                
                if not is_safe and "just" in reason.lower():
                    await self.telegram.send_news_alert(
                        "⏸️ TRADING PAUSED",
                        reason,
                        "extreme",
                        "Bot will resume after event"
                    )
                    
                    # Alert active trades
                    active = self.trade_monitor.get_active_trades_summary()
                    if "No active" not in active:
                        await self.telegram.send_alert(
                            "⚠️ ACTIVE TRADES AT RISK",
                            f"News event!\n\n{active}\n\nConsider closing early.",
                            "high"
                        )
                        
            except Exception as e:
                logger.error(f"News watcher error: {e}")
    
    async def _trade_monitor_loop(self):
        """Background trade monitoring"""
        while self.running:
            try:
                if self.trade_monitor.active_trades:
                    await self.trade_monitor.monitor_cycle(self.data_agg)
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(10)
    
    # ========== MAIN OPERATIONS ==========
    
    async def _send_startup_message(self):
        """Send startup info"""
        upcoming = await self.news_guard.fetch_economic_calendar()
        
        events_text = ""
        for event in upcoming[:5]:
            events_text += f"• {event['event']}: {event['date']} ({event['days_until']}d)\n"
        
        message = (
            "🟢 <b>ALPHA BOT STARTED</b>\n\n"
            f"<b>Assets:</b> <code>{', '.join(TRADING_CONFIG['assets'])}</code>\n"
            f"<b>Max Signals:</b> {TRADING_CONFIG['max_signals_per_day']}/day\n"
            f"<b>Min Score:</b> {TRADING_CONFIG['min_score_threshold']}\n\n"
            f"<b>📅 Upcoming Events:</b>\n{events_text}\n"
            f"<b>🛡️ Protection:</b> News Guard | Time Filter | Trade Monitor"
        )
        
        await self.telegram.send_status(message)
    
    async def _analyze_asset(self, asset: str, data: AssetData) -> list:
        """Analyze single asset"""
        signals = []
        
        try:
            trades = await self.data_agg.get_recent_trades(
                ASSETS_CONFIG[asset]['symbol'], 100
            )
            
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
            liq = await self.strategies[asset]['liquidity'].analyze(market_dict, trades)
            if liq:
                liq['asset'] = asset
                liq['market_data'] = market_dict
                signals.append(liq)
            
            # Strategy_CONFIG['min_score_threshold']}\n\n"
            f"<b>📅 Upcoming Events:</b>\n{events_text}\n"
            f"<b>🛡️ Protection:</b> News Guard | Time Filter | Trade Monitor"
        )
        
        await self.telegram.send_status(message)
    
    async def _analyze_asset(self, asset: str, data: AssetData) -> list:
        """Analyze single asset"""
        signals = []
        
        try:
            trades = await self.data_agg.get_recent_trades(
                ASSETS_CONFIG[asset]['symbol'], 100
            )
            
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
            liq = await self.strategies[asset]['liquidity'].analyze(market_dict, trades)
            if liq:
                liq['asset'] = asset
                liq['market_data'] = market_dict
                signals.append(liq)
            
            # Strategy 2: Gamma Squeeze
            chain = self._generate_chain(asset, data.spot_price)
            gamma = await self.strategies[asset]['gamma'].analyze(market_dict, chain)
            if gamma:
                gamma['asset'] = asset
                gamma['market_data'] = market_dict
                signals.append(gamma)
                
        except Exception as e:
            logger.error(f"❌ {asset} error: {e}")
        
        return signals
    
    def _generate_chain(self, asset: str, spot: float) -> list:
        """Generate options chain"""
        import random
        random.seed(42)
        
        config = ASSETS_CONFIG[asset]
        step = config['strike_step']
        base = round(spot / step) * step
        
        chain = []
        for i in range(-10, 11):
            strike = base + (i * step)
            oi_base = max(15 - abs(i), 3) * 100
            
            chain.append({
                'strike': strike,
                'call_oi': oi_base * (0.8 + random.random() * 0.4),
                'put_oi': oi_base * (0.8 + random.random() * 0.4),
                'call_iv': 0.45 + abs(i) * 0.015,
                'put_iv': 0.45 + abs(i) * 0.015
            })
        
        return chain
    
    async def _process_signals(self, signals: list, assets_data: dict):
        """Process and send signals"""
        trading_signals = []
        
        for sig in signals:
            asset = sig['asset']
            market_data = sig.pop('market_data', {})
            time_quality = sig.pop('time_quality', 'moderate')
            news_status = sig.pop('news_status', 'safe')
            
            # Score calculation
            score_data = self.scorer.calculate_score(sig, market_data, news_status, time_quality)
            
            if score_data['total_score'] < TRADING_CONFIG['min_score_threshold']:
                logger.info(f"❌ {asset} score {score_data['total_score']} low")
                continue
            
            # Position size
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
            return
        
        # Filter and rank
        filtered = self.asset_manager.filter_correlated_signals(trading_signals)
        ranked = sorted(filtered, key=lambda x: x.confidence, reverse=True)
        
        # Send top signals
        max_send = min(len(ranked), TRADING_CONFIG['max_signals_per_day'])
        
        for i, signal in enumerate(ranked[:max_send], 1):
            await self._send_signal(signal, assets_data[signal.asset])
            self.asset_manager.record_signal(signal.asset)
            if i < max_send:
                await asyncio.sleep(3)
        
        logger.info(f"📤 Sent {max_send} signals")
    
    async def _send_signal(self, signal: TradingSignal, market_data: AssetData):
        """Send signal and add to monitor"""
        
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
        
        # Send to Telegram
        await self.telegram.send_signal(setup, score_data, {
            'orderbook': market_data.orderbook,
            'spot_price': market_data.spot_price,
            'funding_rate': market_data.funding_rate
        })
        
        # Add to monitor
        expiry_hours = 48
        if '24' in signal.expiry_suggestion:
            expiry_hours = 24
        elif '72' in signal.expiry_suggestion:
            expiry_hours = 72
        
        trade = ActiveTrade(
            asset=signal.asset,
            direction=signal.direction,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            tp1=signal.target_1,
            tp2=signal.target_2,
            strike=signal.strike_selection,
            expiry=datetime.now() + timedelta(hours=expiry_hours),
            position_size=getattr(signal, 'position_size', 0)
        )
        
        self.trade_monitor.add_trade(trade)
        logger.info(f"📨 {signal.asset} sent | Score: {signal.confidence:.1f}")
    
    def _calc_sleep(self, time_quality: str, signal_count: int) -> int:
        """Calculate sleep time"""
        if time_quality == 'excellent':
            base = 45
        elif time_quality == 'moderate':
            base = 120
        else:
            base = 300
        
        if signal_count > 0:
            base = max(30, base // 2)
        
        return base
    
    def _is_exceptional(self) -> bool:
        """Check for override"""
        return False
    
    async def stop(self):
        """Shutdown"""
        self.running = False
        self.trade_monitor.stop_monitoring()
        
        await self.telegram.send_status(
            "🔴 <b>Bot Stopped</b>\n\n"
            f"Cycles: {self.cycle_count}\n"
            f"{self.asset_manager.get_asset_status()}"
        )
        logger.info("Bot stopped")
"""
Crypto Options Alpha Bot - Part 2: Main Execution
Run this file to start the bot
"""

import asyncio
import logging
from datetime import datetime

# Import from part 1
from main_core import AlphaBot, logger

async def run_bot():
    """Main execution loop"""
    bot = AlphaBot()
    bot.running = True
    
    # Send startup
    await bot._send_startup_message()
    
    # Start background tasks
    asyncio.create_task(bot._news_watcher())
    asyncio.create_task(bot._trade_monitor_loop())
    
    # Main loop
    while bot.running:
        try:
            bot.cycle_count += 1
            current_time = datetime.now().strftime('%H:%M:%S')
            
            logger.info(f"\n{'='*60}")
            logger.info(f"🔄 Cycle #{bot.cycle_count} | {current_time}")
            logger.info(f"{'='*60}")
            
            # Step 1: News Guard
            allowed, news_reason = await bot.news_guard.check_trading_allowed()
            
            if not allowed:
                logger.warning(f"🛑 NEWS BLOCK: {news_reason}")
                
                if bot.cycle_count % 5 == 1 or "just" in news_reason.lower():
                    await bot.telegram.send_news_alert(
                        "🛑 TRADING HALTED",
                        news_reason,
                        "extreme",
                        "Wait for all-clear"
                    )
                
                await asyncio.sleep(180)
                continue
            
            if "caution" in news_reason.lower():
                logger.info(f"⚠️ NEWS: {news_reason}")
            
            # Step 2: Time Filter
            is_good, time_info = bot.time_filter.is_best_time()
            time_quality = time_info.get('quality', 'unknown')
            
            if time_quality == 'avoid' and not bot._is_exceptional():
                logger.info(f"⏰ TIME FILTER: {time_info.get('reason', 'Avoid')}")
                sleep = bot.time_filter.get_sleep_time()
                logger.info(f"😴 Sleep {sleep//60} min")
                await asyncio.sleep(sleep)
                continue
            
            logger.info(f"⏰ TIME: {time_info.get('session', 'Regular')} ({time_quality})")
            
            # Step 3: Daily reset
            if bot.asset_manager.should_reset_daily():
                bot.asset_manager.reset_daily_counters()
                await bot.telegram.send_status("🌅 Daily reset")
            
            # Step 4: Fetch data
            logger.info("📊 Fetching data...")
            assets_data = await bot.data_agg.get_all_assets_data(bot.asset_manager.assets_config)
            
            if not assets_data:
                logger.error("❌ No data")
                await asyncio.sleep(60)
                continue
            
            logger.info(f"✅ Data: {', '.join(assets_data.keys())}")
            
            # Step 5: Analyze
            all_signals = []
            
            for asset, data in assets_data.items():
                if not bot.asset_manager.can_send_signal(asset):
                    continue
                
                signals = await bot._analyze_asset(asset, data)
                
                for sig in signals:
                    should_process, reason = bot.time_filter.should_process_signal(asset, sig)
                    
                    if should_process:
                        sig['time_quality'] = time_quality
                        sig['news_status'] = news_reason
                        all_signals.append(sig)
                        logger.info(f"✅ {asset} signal: {sig['strategy']}")
                    else:
                        logger.info(f"❌ {asset} rejected: {reason}")
                
                await asyncio.sleep(1)
            
            # Step 6: Process
            if all_signals:
                await bot._process_signals(all_signals, assets_data)
            else:
                logger.info("📭 No signals")
            
            # Sleep
            sleep_time = bot._calc_sleep(time_quality, len(all_signals))
            logger.info(f"⏳ Sleep {sleep_time}s")
            await asyncio.sleep(sleep_time)
            
        except KeyboardInterrupt:
            logger.info("🛑 Shutdown")
            await bot.stop()
            break
            
        except Exception as e:
            logger.error(f"❌ Error: {e}", exc_info=True)
            await asyncio.sleep(60)

async def main():
    """Entry point"""
    try:
        await run_bot()
    except Exception as e:
        logger.critical(f"Fatal: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main())
