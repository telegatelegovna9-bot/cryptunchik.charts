# monitor/charts.py
import io
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import mplfinance as mpf
from monitor.logger import log
import traceback
import pandas_ta as ta  # Работает с Python 3.10


def create_chart(df_plot, symbol, timeframe='5m'):
    try:
        log(f"Создание графика для {symbol}, свечей: {len(df_plot)}")
        if len(df_plot) < 2:
            log(f"Недостаточно данных для графика {symbol}")
            return None

        df_plot = df_plot.copy()
        df_plot.index = pd.to_datetime(df_plot['timestamp'])

        # --- MACD ---
        try:
            macd = ta.macd(df_plot['close'], fast=12, slow=26, signal=9)
            if macd is not None and not macd.empty:
                df_plot['macd'] = macd['MACD_12_26_9']
                df_plot['signal'] = macd['MACDs_12_26_9']
                df_plot['macd_hist'] = macd['MACDh_12_26_9']
            else:
                raise ValueError("MACD вернул пустой результат")
        except Exception as e:
            log(f"Ошибка MACD для {symbol}: {e}")
            df_plot['macd'] = df_plot['signal'] = df_plot['macd_hist'] = np.nan

        # --- RSI ---
        try:
            rsi = ta.rsi(df_plot['close'], length=14)
            df_plot['rsi'] = rsi if rsi is not None else np.nan
        except Exception as e:
            log(f"Ошибка RSI для {symbol}: {e}")
            df_plot['rsi'] = np.nan

        # --- Bollinger Bands ---
        try:
            bb = ta.bbands(df_plot['close'], length=20, std=2)
            if bb is not None and not bb.empty:
                df_plot['sma20'] = bb['BBM_20_2.0']
                df_plot['upper'] = bb['BBU_20_2.0']
                df_plot['lower'] = bb['BBL_20_2.0']
            else:
                raise ValueError("BBANDS вернул пустой результат")
        except Exception as e:
            log(f"Ошибка Bollinger для {symbol}: {e}")
            df_plot['sma20'] = df_plot['upper'] = df_plot['lower'] = np.nan

        add_plots = []

        # Bollinger
        if not df_plot[['sma20', 'upper', 'lower']].isna().all().all():
            add_plots.extend([
                mpf.make_addplot(df_plot['sma20'], color='orange', linestyle='--', width=1),
                mpf.make_addplot(df_plot['upper'], color='purple', linestyle=':', width=0.8),
                mpf.make_addplot(df_plot['lower'], color='purple', linestyle=':', width=0.8)
            ])

        # RSI → панель 1
        if 'rsi' in df_plot and not df_plot['rsi'].isna().all():
            add_plots.append(mpf.make_addplot(df_plot['rsi'], panel=1, color='blue', ylabel='RSI'))

        # MACD → панель 2
        if not df_plot[['macd', 'signal', 'macd_hist']].isna().all().all():
            add_plots.extend([
                mpf.make_addplot(df_plot['macd'], panel=2, color='#1f77b4', width=1.0),
                mpf.make_addplot(df_plot['signal'], panel=2, color='#ff7f0e', linestyle='--', width=1.0),
                mpf.make_addplot(df_plot['macd_hist'], type='bar', panel=2, color='gray', alpha=0.6, width=0.7)
            ])

        # --- Фибоначчи ---
        fib_high = df_plot['high'].max()
        fib_low = df_plot['low'].min()
        fib_diff = max(fib_high - fib_low, 1e-8)
        fib_ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 1.0]
        fib_levels = [fib_high - r * fib_diff for r in fib_ratios]

        # --- Панели ---
        panel_ratios = [5]
        volume_panel = 0
        if any(getattr(ap, 'panel', None) == 1 for ap in add_plots):
            panel_ratios.append(1); volume_panel += 1
        if any(getattr(ap, 'panel', None) == 2 for ap in add_plots):
            panel_ratios.append(1); volume_panel += 1
        panel_ratios.append(1.5); volume_panel += 1

        # --- График ---
        plot_kwargs = {
            'type': 'candle',
            'style': 'yahoo',
            'title': f"{symbol} ({timeframe})",
            'ylabel': 'Price (USDT)',
            'volume': True,
            'volume_panel': volume_panel,
            'panel_ratios': tuple(panel_ratios),
            'figsize': (14, 10),
            'returnfig': True,
            'hlines': dict(hlines=fib_levels, colors=['purple']*6, linestyle='--', linewidths=[1.2]*6, alpha=0.7),
            'tight_layout': True
        }
        if add_plots:
            plot_kwargs['addplot'] = add_plots

        fig, axes = mpf.plot(df_plot, **plot_kwargs)

        # --- Метки Фибоначчи ---
        if axes and len(axes) > 0:
            ax = axes[0]
            price_decimals = max(4, -int(np.log10(abs(fib_high) or 1)) + 2) if fib_high > 0 else 8
            fib_labels = [f"{r*100:.1f}% — {lvl:.{price_decimals}f}" for r, lvl in zip(fib_ratios, fib_levels)]
            for label, level in zip(fib_labels, fib_levels):
                ax.text(0.02, level, label, fontsize=8, color='purple', fontweight='bold',
                        va='center', ha='left', transform=ax.get_yaxis_transform(),
                        bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8))

        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', dpi=120, facecolor='white')
        plt.close('all')
        buf.seek(0)
        log(f"График {symbol} создан")
        return buf

    except Exception as e:
        log(f"ОШИБКА create_chart({symbol}): {e}")
        log(f"Traceback: {traceback.format_exc()}")
        plt.close('all')
        return None

