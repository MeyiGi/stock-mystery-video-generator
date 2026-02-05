import customtkinter as ctk
import pandas as pd
import numpy as np
import matplotlib
# FIX 1: Set backend to non-interactive 'Agg' to prevent threading crashes
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.dates as mdates
import matplotlib.patheffects as path_effects
import os
import re
import threading
import subprocess
from datetime import datetime, timedelta

# Check for optional libraries
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

try:
    from scipy.interpolate import make_interp_spline
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# ==========================================
# CONFIGURATION
# ==========================================
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30

# VISUAL IDENTITY
COLOR_BG = "#050505"         # Deep Black
COLOR_GRID = "#1A1A1A"       # Subtle Grid
COLOR_LINE = "#00FF88"       # Matrix/Crypto Green
COLOR_ACCENT = "#00FF88"     
COLOR_TEXT_MAIN = "#FFFFFF"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

class MysteryChartAnimator:
    
    def _create_smooth_curve(self, df, points=600):
        # Fallback if too few points or scipy missing
        if not SCIPY_AVAILABLE or len(df) < 4: 
            return df
            
        try:
            dates = mdates.date2num(df.index)
            prices = df['Price'].values
            
            # Use k=2 (Quadratic) for safer curves on volatile crypto data
            spline = make_interp_spline(dates, prices, k=2) 
            
            smooth_dates_num = np.linspace(dates.min(), dates.max(), points)
            smooth_prices = spline(smooth_dates_num)
            smooth_prices = np.maximum(smooth_prices, 0) # No negative prices
            
            smooth_dates = mdates.num2date(smooth_dates_num)
            smooth_dates = [d.replace(tzinfo=None) for d in smooth_dates]
            return pd.Series(smooth_prices, index=smooth_dates)
        except:
            return df # Return original if smoothing fails

    def create_animation(self, data, answer_text, reveal_answer, output_path, 
                         duration_sec, start_idle_sec, end_idle_sec, 
                         log_callback=print):
        
        log_callback(f"Rendering chart...")
        
        # 1. Smooth Data
        smooth_data = self._create_smooth_curve(data, points=int(duration_sec * FPS))

        # 2. Setup Figure
        dpi = 120
        fig, ax = plt.subplots(figsize=(VIDEO_WIDTH/dpi, VIDEO_HEIGHT/dpi), dpi=dpi)
        fig.patch.set_facecolor(COLOR_BG)
        ax.set_facecolor(COLOR_BG)

        # 3. Text Overlays 
        # Hook (Start) - MODIFIED TEXT
        t_hook1 = fig.text(0.5, 0.85, "CAN YOU GUESS", ha='center', fontsize=55, fontweight='bold', color='white', alpha=0, fontfamily='sans-serif')
        t_hook2 = fig.text(0.5, 0.81, "THE STOCK?", ha='center', fontsize=65, fontweight='bold', color=COLOR_ACCENT, alpha=0, fontfamily='sans-serif')
        
        # CTA (Comment logic)
        t_cta = fig.text(0.5, 0.20, "COMMENT YOUR GUESS", ha='center', fontsize=45, fontweight='bold', color='white', alpha=0, fontfamily='sans-serif')
        t_cta.set_path_effects([path_effects.withStroke(linewidth=4, foreground=COLOR_ACCENT, alpha=0.5)])

        # Answer Reveal
        t_answer_label = fig.text(0.5, 0.55, "IT WAS:", ha='center', fontsize=40, color='gray', alpha=0, fontfamily='sans-serif')
        t_answer_main = fig.text(0.5, 0.50, answer_text.upper(), ha='center', fontsize=70, fontweight='bold', color=COLOR_ACCENT, alpha=0, fontfamily='sans-serif')
        t_answer_main.set_path_effects([path_effects.withStroke(linewidth=5, foreground="white", alpha=0.8)])

        # 5. Chart Elements
        line, = ax.plot([], [], color=COLOR_LINE, lw=6, solid_capstyle='round', zorder=10)
        line.set_path_effects([path_effects.SimpleLineShadow(offset=(0,0), alpha=0.3, rho=5, linewidth=15, shadow_color=COLOR_LINE), path_effects.Normal()])

        head, = ax.plot([], [], 'o', color='white', markersize=8, zorder=12)
        head_glow, = ax.plot([], [], 'o', color=COLOR_LINE, markersize=30, alpha=0.3, zorder=11)

        # 6. Fill Area
        # Initialize empty fill
        ax.fill_between([], [], color=COLOR_LINE, alpha=0.2, zorder=5)

        # 7. Axis Styling
        x_vals_all = mdates.date2num(smooth_data.index)
        y_vals_all = smooth_data.values
        x_min, x_max = x_vals_all[0], x_vals_all[-1]
        y_min, y_max = y_vals_all.min(), y_vals_all.max()
        
        # Padding
        y_pad = (y_max - y_min) * 0.2
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min - y_pad, y_max + y_pad)
        
        # Grid
        ax.grid(axis='y', color=COLOR_GRID, linestyle='-', linewidth=2, alpha=0.5)
        ax.grid(axis='x', color=COLOR_GRID, linestyle='-', linewidth=1, alpha=0.3)
        
        # --- NEW AXIS SETTINGS (SHOW DATES) ---
        # Hide Spines (Border box)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_color(COLOR_GRID) # Keep bottom line subtle
        
        # Hide Price Numbers (Y-Axis) but keep Dates (X-Axis)
        ax.get_yaxis().set_visible(False)
        
        # Style Date Labels
        ax.tick_params(axis='x', colors='gray', labelsize=18, rotation=0)
        
        # Date Format (Year only or Mon-Year depending on range)
        # Using auto locator to prevent crowding
        locator = mdates.AutoDateLocator(maxticks=5)
        formatter = mdates.ConciseDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)

        plt.subplots_adjust(left=0.05, right=0.95, top=0.9, bottom=0.15)

        # 8. Animation Logic
        frames_draw = int(duration_sec * FPS)
        frames_pre = int(start_idle_sec * FPS)
        frames_post = int(end_idle_sec * FPS)
        total_frames = frames_pre + frames_draw + frames_post
        
        indices = np.linspace(0, len(smooth_data)-1, frames_draw, dtype=int)
        
        def update(frame):
            # Phase 1: Hook
            if frame < frames_pre:
                alpha = 1.0 if (frame // 15) % 2 == 0 else 0.8
                t_hook1.set_alpha(alpha); t_hook2.set_alpha(alpha)
                return []
            
            # Phase 2: Drawing
            elif frame < (frames_pre + frames_draw):
                t_hook1.set_visible(False); t_hook2.set_visible(False)
                
                curr_i = frame - frames_pre
                idx = indices[curr_i]
                
                current_x = x_vals_all[:idx+1]
                current_y = y_vals_all[:idx+1]
                
                if len(current_x) < 2: return []
                
                line.set_data(current_x, current_y)
                
                cx, cy = current_x[-1], current_y[-1]
                head.set_data([cx], [cy])
                head_glow.set_data([cx], [cy])
                
                # FIX 2: Safely remove previous fill collections
                for coll in list(ax.collections):
                    coll.remove()
                    
                ax.fill_between(current_x, current_y, y_min-y_pad, color=COLOR_LINE, alpha=0.2, zorder=5)
                
                # Zoom/Pan
                zoom_strength = 0.15 * (curr_i / frames_draw)
                center_x = (x_min + x_max) / 2
                current_span = (x_max - x_min) * (1 - zoom_strength)
                pan_offset = (x_max - x_min) * 0.1 * (curr_i / frames_draw)
                
                ax.set_xlim(center_x - current_span/2 + pan_offset, center_x + current_span/2 + pan_offset)
                
                return [line, head]
            
            # Phase 3: End / Reveal
            else:
                prog = (frame - (frames_pre + frames_draw)) / frames_post
                
                if reveal_answer:
                    # Fade out line
                    line.set_alpha(1 - prog)
                    if ax.collections:
                        ax.collections[0].set_alpha((1-prog)*0.2)
                    head.set_alpha(1 - prog)
                    
                    # Fade In Answer
                    t_answer_label.set_alpha(prog)
                    t_answer_main.set_alpha(prog)
                    t_cta.set_visible(False)
                    return [t_answer_main, line]
                else:
                    # Just show CTA
                    t_cta.set_alpha(min(prog*2, 1))
                    t_cta.set_position((0.5, 0.20 + prog*0.01))
                    return [t_cta]

            if frame % 15 == 0:
                log_callback(f"Render: {int(frame/total_frames*100)}%")

        writer = animation.FFMpegWriter(fps=FPS, bitrate=8000, extra_args=['-vcodec', 'libx264', '-pix_fmt', 'yuv420p'])
        ani = animation.FuncAnimation(fig, update, frames=total_frames, blit=False)
        ani.save(output_path, writer=writer)
        plt.close(fig)

class StockQuizApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Mystery Chart Generator v4.2")
        self.geometry("700x900")
        self.resizable(False, False)
        
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(self.main_frame, text="MYSTERY CHART GENERATOR", font=("Impact", 24), text_color=COLOR_LINE).pack(pady=(10, 20))

        # TABS
        self.tabview = ctk.CTkTabview(self.main_frame, height=350)
        self.tabview.pack(fill="x", padx=10)
        self.tab_api = self.tabview.add("Download Data")
        self.tab_manual = self.tabview.add("Manual Paste")

        # --- TAB 1: API ---
        ctk.CTkLabel(self.tab_api, text="Ticker Symbol:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.entry_ticker = ctk.CTkEntry(self.tab_api, placeholder_text="BTC-USD")
        self.entry_ticker.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(self.tab_api, text="Start Date:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.entry_start = ctk.CTkEntry(self.tab_api)
        self.entry_start.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(self.tab_api, text="End Date:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.entry_end = ctk.CTkEntry(self.tab_api)
        self.entry_end.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        
        today = datetime.now()
        self.entry_end.insert(0, today.strftime("%Y-%m-%d"))
        self.entry_start.insert(0, (today - timedelta(days=365*5)).strftime("%Y-%m-%d"))

        # --- TAB 2: MANUAL ---
        ctk.CTkLabel(self.tab_manual, text="Paste Data (Date Price):", anchor="w").pack(fill="x", padx=10)
        self.txt_manual = ctk.CTkTextbox(self.tab_manual, height=200)
        self.txt_manual.pack(fill="both", expand=True, padx=10, pady=5)
        # Your specific data as default
        self.txt_manual.insert("0.0", "2021-01-01 29000\n2021-02-01 35000\n2021-03-01 55000\n2021-04-15 64000\n2021-05-20 35000\n2021-07-20 29000\n2021-09-01 50000\n2021-11-10 69000\n2022-01-01 47000\n2022-05-01 30000\n2022-06-15 17000\n2022-11-01 16000\n2023-01-01 22000\n2023-04-01 30000\n2023-10-01 27000\n2024-01-01 45000\n2024-03-01 65000")

        # --- SETTINGS ---
        self.sets_frame = ctk.CTkFrame(self.main_frame)
        self.sets_frame.pack(fill="x", padx=10, pady=10)

        # Answer Reveal Options
        ctk.CTkLabel(self.sets_frame, text="Correct Answer (e.g. BITCOIN):").pack(anchor="w", padx=10, pady=(10,0))
        self.entry_answer = ctk.CTkEntry(self.sets_frame, placeholder_text="Enter Stock Name Here")
        self.entry_answer.pack(fill="x", padx=10, pady=5)

        self.reveal_var = ctk.BooleanVar(value=False)
        self.chk_reveal = ctk.CTkCheckBox(self.sets_frame, text="Reveal Answer at End of Video?", variable=self.reveal_var)
        self.chk_reveal.pack(anchor="w", padx=10, pady=5)
        
        # Audio
        self.use_audio = ctk.BooleanVar(value=True)
        self.chk_audio = ctk.CTkCheckBox(self.sets_frame, text="Use Audio (audio/background.mp3)", variable=self.use_audio)
        self.chk_audio.pack(anchor="w", padx=10, pady=5)

        self.btn_gen = ctk.CTkButton(self.main_frame, text="GENERATE VIDEO", height=50, 
                                     fg_color=COLOR_LINE, text_color="black", hover_color="#20bd54",
                                     font=("Arial", 16, "bold"), command=self.start)
        self.btn_gen.pack(fill="x", padx=10, pady=10)
        
        self.log_box = ctk.CTkTextbox(self.main_frame, height=80, font=("Consolas", 10))
        self.log_box.pack(fill="x", padx=10)

        os.makedirs("videos", exist_ok=True)
        os.makedirs("audio", exist_ok=True)

    def log(self, msg):
        self.log_box.insert("end", f"> {msg}\n")
        self.log_box.see("end")

    def parse_manual(self, text):
        lines = text.strip().split('\n')
        dates, prices = [], []
        # Robust Regex
        regex = r"(\d{4}[-.]\d{1,2}[-.]\d{1,2})[\s,\t;]+([\d,.]+)"
        
        for line in lines:
            match = re.search(regex, line)
            if match:
                d_str, p_str = match.groups()
                d_str = d_str.replace('.', '-')
                try:
                    dt = datetime.strptime(d_str, "%Y-%m-%d")
                    price = float(p_str.replace(',', ''))
                    dates.append(dt)
                    prices.append(price)
                except ValueError:
                    self.log(f"Skipping line: {line}")
        
        if not dates: return pd.DataFrame()
        return pd.DataFrame({'Price': prices}, index=dates).sort_index()

    def start(self):
        threading.Thread(target=self.process).start()

    def process(self):
        self.btn_gen.configure(state="disabled")
        try:
            mode = self.tabview.get()
            df = None
            answer_text = self.entry_answer.get().strip()
            
            if mode == "Download Data":
                if not YFINANCE_AVAILABLE:
                    self.log("YFinance not installed."); return
                ticker = self.entry_ticker.get().strip().upper()
                if not answer_text: answer_text = ticker # Auto-fill answer if empty
                
                start = self.entry_start.get().strip()
                end = self.entry_end.get().strip()
                
                self.log(f"Downloading {ticker}...")
                df = yf.download(ticker, start=start, end=end, progress=False)
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
                col = 'Close' if 'Close' in df.columns else 'Adj Close'
                df = df[[col]].rename(columns={col: 'Price'})
                
            else:
                raw_text = self.txt_manual.get("0.0", "end")
                df = self.parse_manual(raw_text)
                if df.empty:
                    self.log("No valid manual data found."); return
                if not answer_text: answer_text = "MYSTERY ASSET"

            # Create Animation
            clean_name = re.sub(r'[^a-zA-Z0-9]', '', answer_text)
            temp_path = os.path.join("videos", "temp_render.mp4")
            final_path = os.path.join("videos", f"Mystery_{clean_name}.mp4")
            
            anim = MysteryChartAnimator()
            anim.create_animation(
                data=df, 
                answer_text=answer_text,
                reveal_answer=self.reveal_var.get(),
                output_path=temp_path, 
                duration_sec=15, 
                start_idle_sec=2, 
                end_idle_sec=5, 
                log_callback=self.log
            )
            
            # Audio
            if self.use_audio.get():
                audio_f = os.path.join("audio", "background.mp3")
                if os.path.exists(audio_f):
                    self.log("Mixing Audio...")
                    ffmpeg = "ffmpeg.exe" if os.path.exists("ffmpeg.exe") else "ffmpeg"
                    
                    cmd = [
                        ffmpeg, '-y', 
                        '-i', temp_path,
                        '-i', audio_f, 
                        '-c:v', 'copy', '-c:a', 'aac',
                        '-map', '0:v:0', '-map', '1:a:0',
                        '-shortest', final_path
                    ]
                    
                    startupinfo = None
                    if os.name == 'nt':
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    
                    subprocess.run(cmd, startupinfo=startupinfo)
                    os.remove(temp_path)
                    self.log(f"Finished: {final_path}")
                else:
                    self.log("Audio missing. Saved video only.")
                    if os.path.exists(final_path): os.remove(final_path)
                    os.rename(temp_path, final_path)
            else:
                if os.path.exists(final_path): os.remove(final_path)
                os.rename(temp_path, final_path)
                self.log(f"Finished: {final_path}")

        except Exception as e:
            self.log(f"Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.btn_gen.configure(state="normal")

if __name__ == "__main__":
    app = StockQuizApp()
    app.mainloop()