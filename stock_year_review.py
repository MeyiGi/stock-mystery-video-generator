import customtkinter as ctk
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
import os
import shutil
import re
import threading
import subprocess
from datetime import datetime

# Optional: Try importing yfinance
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

# ==========================================
# CONFIGURATION
# ==========================================
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30

# Colors
BACKGROUND_COLOR = "#121212"
STOCK_COLOR = "#1DB954" # Spotify Green
FONT_LIGHT_COLOR = "#FFFFFF"
FONT_MUTED_COLOR = "#A0A0A0"

# Set GUI Theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

class YearInReviewAnimator:
    """
    Handles the plotting and video generation logic.
    """
    def _format_currency(self, x, pos):
        if x >= 1_000_000: return f'${x/1_000_000:.1f}M'
        if x >= 1_000: return f'${x/1_000:.0f}K'
        return f'${x:,.0f}'

    def _get_adaptive_fontsize(self, text, base=80, max_chars=6):
        if len(text) > max_chars:
            factor = max_chars / len(text)
            return int(base * factor)
        return base

    def create_animation(self, data, stock_name, year, output_path,
                         duration_sec, start_idle_sec, end_idle_sec,
                         quiz_mode=False,
                         quiz_title=None,
                         quiz_subtitle=None,
                         quiz_reveal_name=None,
                         log_callback=print):

        log_callback(f"Init Animation: {stock_name} | {duration_sec}s draw | {start_idle_sec}s start | {end_idle_sec}s end")

        # 1. Prepare Data
        if 'Price' not in data.columns:
            raise ValueError("Dataframe must have a 'Price' column")

        year_data_daily = data['Price'].resample('D').interpolate(method='linear')

        # Calculate Stats
        start_p = year_data_daily.iloc[0].item() if hasattr(year_data_daily.iloc[0], 'item') else float(year_data_daily.iloc[0])
        end_p = year_data_daily.iloc[-1].item() if hasattr(year_data_daily.iloc[-1], 'item') else float(year_data_daily.iloc[-1])
        high_date = year_data_daily.idxmax()
        high_p = year_data_daily.max().item() if hasattr(year_data_daily.max(), 'item') else float(year_data_daily.max())
        low_date = year_data_daily.idxmin()
        low_p = year_data_daily.min().item() if hasattr(year_data_daily.min(), 'item') else float(year_data_daily.min())
        pct_change = ((end_p - start_p) / start_p) * 100

        # 2. Setup Figure
        dpi = 120
        fig, ax = plt.subplots(figsize=(VIDEO_WIDTH/dpi, VIDEO_HEIGHT/dpi), dpi=dpi)
        fig.patch.set_facecolor(BACKGROUND_COLOR)
        ax.set_facecolor(BACKGROUND_COLOR)

        # 3. Header Text (Conditional)
        if quiz_mode:
            fig.text(0.5, 0.93, quiz_title if quiz_title else "Can you guess this stock?",
                     ha='center', va='center', fontsize=40, fontweight='bold',
                     color=FONT_LIGHT_COLOR, fontfamily='sans-serif')

            subtitle = fig.text(0.5, 0.89, quiz_subtitle if quiz_subtitle else "answer in comments",
                     ha='center', va='center', fontsize=24, color=FONT_MUTED_COLOR, fontfamily='sans-serif')
        else:
            fig.text(0.5, 0.93, f"{stock_name}",
                     ha='center', va='center', fontsize=40, fontweight='bold',
                     color=FONT_LIGHT_COLOR, fontfamily='sans-serif')

            subtitle = fig.text(0.5, 0.89, f"{year} PERFORMANCE",
                     ha='center', va='center', fontsize=24, color=FONT_MUTED_COLOR, fontfamily='sans-serif')

        # 4. FOOTER
        fig.text(0.5, 0.08, "FINJOVI.COM", fontsize=50, color="black", fontweight="bold",
                 ha="center", va="center", fontfamily="serif",
                 bbox=dict(facecolor="#D3D3D3", edgecolor="none", boxstyle="round,pad=0.4", alpha=1.0))

        # 5. Plot Elements (Line & Head)
        line, = ax.plot([], [], color=STOCK_COLOR, lw=4.5, solid_capstyle='round')
        head, = ax.plot([], [], 'o', color=STOCK_COLOR, markersize=12, markeredgecolor='white', markeredgewidth=2)
        date_label = ax.text(0, 0, "", color=FONT_LIGHT_COLOR, fontsize=18,
                             ha='center', va='bottom', fontweight='bold', fontfamily='sans-serif')

        # 6. Final Result Elements (Conditional)
        if quiz_mode:
            reveal_name = quiz_reveal_name if quiz_reveal_name else ""
            
            if reveal_name:
                # Show the answer at the end
                adaptive_size = self._get_adaptive_fontsize(reveal_name, base=80, max_chars=6)
                final_text = fig.text(0.5, 0.82, reveal_name, ha='center', va='center',
                                            fontsize=adaptive_size, fontweight='bold',
                                            color=FONT_LIGHT_COLOR, visible=False)
                final_sub = fig.text(0.5, 0.78, "The Answer!", ha='center', va='center',
                                           fontsize=20, color=FONT_MUTED_COLOR, visible=False)
            else:
                # No reveal - keep answer hidden for maximum engagement
                final_text = fig.text(0.5, 0.82, "", ha='center', va='center',
                                            fontsize=80, fontweight='bold',
                                            color=FONT_LIGHT_COLOR, visible=False)
                final_sub = fig.text(0.5, 0.78, "", ha='center', va='center',
                                           fontsize=20, color=FONT_MUTED_COLOR, visible=False)
        else:
            change_color = 'limegreen' if pct_change >= 0 else 'tomato'
            sign = '+' if pct_change >= 0 else ''
            pct_str = f"{sign}{pct_change:.1f}%"
            adaptive_size = self._get_adaptive_fontsize(pct_str, base=80, max_chars=6)

            final_text = fig.text(0.5, 0.82, pct_str, ha='center', va='center',
                                        fontsize=adaptive_size, fontweight='bold', color=change_color, visible=False)

            final_sub = fig.text(0.5, 0.78, "Yearly Change", ha='center', va='center',
                                       fontsize=20, color=FONT_MUTED_COLOR, visible=False)

        high_marker, = ax.plot([], [], 'o', color='gold', markersize=10, visible=False, zorder=10)
        low_marker, = ax.plot([], [], 'o', color='deepskyblue', markersize=10, visible=False, zorder=10)

        # 7. Axis Config
        ax.set_xlim(year_data_daily.index[0], year_data_daily.index[-1])
        
        # Convert Series to scalar values for ylim
        y_min_val = year_data_daily.min()
        y_max_val = year_data_daily.max()
        y_min = y_min_val.item() if hasattr(y_min_val, 'item') else float(y_min_val)
        y_max = y_max_val.item() if hasattr(y_max_val, 'item') else float(y_max_val)
        ax.set_ylim(y_min * 0.95, y_max * 1.05)
        
        # Smart x-axis formatting based on date range
        date_range_days = (year_data_daily.index[-1] - year_data_daily.index[0]).days
        if date_range_days > 400:
            # Multi-year data: show months with years
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        else:
            # Single year or less: show months only
            ax.xaxis.set_major_locator(mdates.MonthLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
        
        ax.yaxis.set_major_formatter(FuncFormatter(self._format_currency))
        ax.tick_params(colors=FONT_MUTED_COLOR, labelsize=16, pad=10)
        ax.grid(axis='y', linestyle='--', linewidth=0.5, color='#444444')
        for spine in ax.spines.values(): spine.set_visible(False)
        plt.subplots_adjust(top=0.75, bottom=0.15, left=0.18, right=0.95)

        # 8. Animation Frames Logic
        frames_main = int(duration_sec * FPS)
        frames_start = int(start_idle_sec * FPS)
        frames_end = int(end_idle_sec * FPS)
        total_frames = frames_start + frames_main + frames_end

        idx_main = np.linspace(0, len(year_data_daily) - 1, frames_main, dtype=int)
        all_indices = np.concatenate([
            np.zeros(frames_start, dtype=int),
            idx_main,
            np.full(frames_end, len(year_data_daily) - 1, dtype=int)
        ])

        def update(frame_index):
            idx = all_indices[frame_index]
            cur_data = year_data_daily.iloc[:idx + 1]
            cur_date = cur_data.index[-1]
            cur_price = cur_data.iloc[-1]

            line.set_data(cur_data.index, cur_data)
            head.set_data([cur_date], [cur_price])

            date_label.set_position((cur_date, cur_price + (ax.get_ylim()[1] * 0.05)))
            date_label.set_text(cur_date.strftime("%b %d"))

            # End phase: show results
            if frame_index >= (frames_start + frames_main):
                date_label.set_visible(False)
                head.set_visible(False)
                subtitle.set_visible(False)

                final_text.set_visible(True)
                final_sub.set_visible(True)
                high_marker.set_data([high_date], [high_p]); high_marker.set_visible(True)
                low_marker.set_data([low_date], [low_p]); low_marker.set_visible(True)

            if frame_index % 30 == 0:
                pct = int(frame_index/total_frames * 100)
                log_callback(f"Rendering frame {frame_index}/{total_frames} ({pct}%)...")

            return [line, head, date_label, final_text, final_sub, high_marker, low_marker]

        # 9. Save Video
        if not shutil.which("ffmpeg") and not os.path.exists("ffmpeg.exe"):
            log_callback("ERROR: ffmpeg not found. Install it or place ffmpeg.exe here.")
            return

        writer = animation.FFMpegWriter(fps=FPS, bitrate=8000, extra_args=['-vcodec', 'libx264', '-pix_fmt', 'yuv420p'])
        ani = animation.FuncAnimation(fig, update, frames=total_frames, blit=False)
        ani.save(output_path, writer=writer)
        plt.close(fig)


class StockReviewApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Stock Video Generator")
        self.geometry("600x850")
        self.resizable(False, False)

        # Main Container
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        self.lbl_title = ctk.CTkLabel(self.main_frame, text="STOCK VIDEO GENERATOR", font=("Arial", 22, "bold"))
        self.lbl_title.pack(pady=(10, 15))

        # --- MODE SELECTION TABS ---
        self.mode_tabview = ctk.CTkTabview(self.main_frame, height=400)
        self.mode_tabview.pack(fill="x", padx=10)
        self.tab_review = self.mode_tabview.add("Year in Review")
        self.tab_quiz = self.mode_tabview.add("Quiz Mode")

        # --- DATA INPUT TABS (Nested) ---
        self.review_datainput_tab = ctk.CTkTabview(self.tab_review, height=300)
        self.review_datainput_tab.pack(fill="x", padx=5, pady=5)
        self.review_manual_tab = self.review_datainput_tab.add("Manual Input")
        self.review_symbol_tab = self.review_datainput_tab.add("Symbol Input")

        self.quiz_datainput_tab = ctk.CTkTabview(self.tab_quiz, height=300)
        self.quiz_datainput_tab.pack(fill="x", padx=5, pady=5)
        self.quiz_manual_tab = self.quiz_datainput_tab.add("Manual Input")
        self.quiz_symbol_tab = self.quiz_datainput_tab.add("Symbol Input")

        self._setup_manual_tab(self.review_manual_tab)
        self._setup_symbol_tab(self.review_symbol_tab)
        self._setup_manual_tab(self.quiz_manual_tab, is_quiz=True)
        self._setup_symbol_tab(self.quiz_symbol_tab, is_quiz=True)

        self._setup_quiz_fields()

        # --- SETTINGS FRAME ---
        self.settings_frame = ctk.CTkFrame(self.main_frame)
        self.settings_frame.pack(fill="x", padx=10, pady=10)

        self.lbl_duration = ctk.CTkLabel(self.settings_frame, text="Animation Duration: 10s", font=("Arial", 12))
        self.lbl_duration.pack(pady=(5,0))
        self.slider_duration = ctk.CTkSlider(self.settings_frame, from_=5, to=30, number_of_steps=25, command=self.update_duration_label)
        self.slider_duration.set(10)
        self.slider_duration.pack(fill="x", padx=20, pady=(0, 10))

        self.idle_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.idle_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.lbl_start_idle = ctk.CTkLabel(self.idle_frame, text="Start Idle (s):")
        self.lbl_start_idle.pack(side="left", padx=(10, 5))
        self.entry_start_idle = ctk.CTkEntry(self.idle_frame, width=50); self.entry_start_idle.pack(side="left")
        self.entry_start_idle.insert(0, "1.0")
        self.lbl_end_idle = ctk.CTkLabel(self.idle_frame, text="End Idle (s):"); self.lbl_end_idle.pack(side="left", padx=(20, 5))
        self.entry_end_idle = ctk.CTkEntry(self.idle_frame, width=50); self.entry_end_idle.pack(side="left")
        self.entry_end_idle.insert(0, "4.0")

        # --- AUDIO ---
        self.use_audio_var = ctk.BooleanVar(value=True)
        self.chk_use_audio = ctk.CTkCheckBox(self.main_frame, text="Use Audio (merge audio/background.mp3)", variable=self.use_audio_var, font=("Arial", 12))
        self.chk_use_audio.pack(pady=(5, 5))

        # --- GENERATE BUTTON & LOG ---
        self.btn_gen = ctk.CTkButton(self.main_frame, text="GENERATE VIDEO", height=50, fg_color="#39FF14", text_color="black", hover_color="#2cc712", font=("Arial", 16, "bold"), command=self.start_generation)
        self.btn_gen.pack(fill="x", padx=10, pady=10)

        self.log_box = ctk.CTkTextbox(self.main_frame, height=100, font=("Consolas", 12))
        self.log_box.pack(fill="x", padx=10, pady=(0, 10))

        os.makedirs("videos", exist_ok=True)
        os.makedirs("audio", exist_ok=True)

    def _setup_manual_tab(self, parent_tab, is_quiz=False):
        # Unique identifiers for widgets
        name_key = 'quiz_manual_name' if is_quiz else 'review_manual_name'
        text_key = 'quiz_manual_text' if is_quiz else 'review_manual_text'
        
        ctk.CTkLabel(parent_tab, text="Stock/Asset Name:", anchor="w").pack(fill="x", padx=10, pady=(10,0))
        setattr(self, name_key, ctk.CTkEntry(parent_tab, placeholder_text="My Portfolio"))
        getattr(self, name_key).pack(fill="x", padx=10, pady=(5,10))

        ctk.CTkLabel(parent_tab, text="Data (DD.MM.YYYY - Price):", anchor="w").pack(fill="x", padx=10)
        setattr(self, text_key, ctk.CTkTextbox(parent_tab, height=150))
        getattr(self, text_key).pack(fill="both", expand=True, padx=10, pady=5)
        getattr(self, text_key).insert("0.0", "01.01.2023 - 500\n15.06.2023 - 700\n31.12.2023 - 1200")

    def _setup_symbol_tab(self, parent_tab, is_quiz=False):
        # Unique identifiers
        sym_key = 'quiz_sym' if is_quiz else 'review_sym'
        year_key = 'quiz_year' if is_quiz else 'review_year'

        if YFINANCE_AVAILABLE:
            ctk.CTkLabel(parent_tab, text="Stock Symbol (e.g. TSLA, BTC-USD):").pack(pady=(20,5))
            setattr(self, sym_key, ctk.CTkEntry(parent_tab, placeholder_text="AAPL"))
            getattr(self, sym_key).pack(pady=5)

            ctk.CTkLabel(parent_tab, text="Year (e.g. 2023):").pack(pady=(20,5))
            setattr(self, year_key, ctk.CTkEntry(parent_tab, placeholder_text="2023"))
            getattr(self, year_key).pack(pady=5)
            getattr(self, year_key).insert(0, str(datetime.now().year - 1))
        else:
            ctk.CTkLabel(parent_tab, text="Required: pip install yfinance", text_color="tomato").pack(pady=50)

    def _setup_quiz_fields(self):
        # Quiz-specific text fields in the quiz tab
        quiz_frame = ctk.CTkFrame(self.tab_quiz, fg_color="transparent")
        quiz_frame.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(quiz_frame, text="Quiz Title:", font=("Arial", 12, "bold")).pack(anchor="w", padx=10)
        self.entry_quiz_title = ctk.CTkEntry(quiz_frame, placeholder_text="Can you guess this stock from the chart?")
        self.entry_quiz_title.pack(fill="x", padx=10, pady=(0, 5))

        ctk.CTkLabel(quiz_frame, text="Quiz Subtitle:", font=("Arial", 12, "bold")).pack(anchor="w", padx=10)
        self.entry_quiz_subtitle = ctk.CTkEntry(quiz_frame, placeholder_text="answer in comments")
        self.entry_quiz_subtitle.pack(fill="x", padx=10, pady=(0, 5))
        self.entry_quiz_subtitle.insert(0, "answer in comments")

        ctk.CTkLabel(quiz_frame, text="Stock Name (for reveal - optional, leave empty to hide answer):", font=("Arial", 12, "bold")).pack(anchor="w", padx=10)
        self.entry_quiz_reveal = ctk.CTkEntry(quiz_frame, placeholder_text="e.g., BAC, AAPL, or Apple")
        self.entry_quiz_reveal.pack(fill="x", padx=10, pady=(0, 5))

    def update_duration_label(self, value):
        self.lbl_duration.configure(text=f"Animation Duration: {int(value)}s")

    def log(self, msg):
        self.log_box.insert("end", f"> {msg}\n")
        self.log_box.see("end")

    def start_generation(self):
        self.btn_gen.configure(state="disabled")

        bundle = {}
        # Get global settings
        bundle['duration'] = int(self.slider_duration.get())
        bundle['use_audio'] = self.use_audio_var.get()
        try:
            bundle['start_idle'] = float(self.entry_start_idle.get())
            bundle['end_idle'] = float(self.entry_end_idle.get())
        except ValueError:
            self.log("Error: Idle times must be numbers."); self.btn_gen.configure(state="normal"); return

        # Determine mode (Review or Quiz)
        mode = self.mode_tabview.get()
        bundle['quiz_mode'] = (mode == "Quiz Mode")
        
        # Determine data source (Manual or Symbol)
        data_source_tab = self.review_datainput_tab if not bundle['quiz_mode'] else self.quiz_datainput_tab
        data_mode = data_source_tab.get()

        if bundle['quiz_mode']:
            bundle['quiz_title'] = self.entry_quiz_title.get().strip()
            bundle['quiz_subtitle'] = self.entry_quiz_subtitle.get().strip()
            bundle['quiz_reveal_name'] = self.entry_quiz_reveal.get().strip()
            # Reveal name is now optional - if empty, no answer will be shown (for maximum engagement)

        if data_mode == "Symbol Input":
            if not YFINANCE_AVAILABLE: self.log("Error: yfinance not available."); self.btn_gen.configure(state="normal"); return
            sym_entry = self.quiz_sym if bundle['quiz_mode'] else self.review_sym
            year_entry = self.quiz_year if bundle['quiz_mode'] else self.review_year
            bundle['ticker'] = sym_entry.get().strip().upper()
            try: bundle['year'] = int(year_entry.get().strip())
            except: self.log("Error: Invalid year."); self.btn_gen.configure(state="normal"); return
        else: # Manual Input
            name_entry = self.quiz_manual_name if bundle['quiz_mode'] else self.review_manual_name
            text_entry = self.quiz_manual_text if bundle['quiz_mode'] else self.review_manual_text
            bundle['name'] = name_entry.get().strip()
            bundle['text'] = text_entry.get("0.0", "end").strip()
            if not bundle['name']: self.log("Error: Enter an asset name."); self.btn_gen.configure(state="normal"); return
        
        threading.Thread(target=self.run_process, args=(bundle,)).start()

    def run_process(self, bundle):
        try:
            df, stock_name, year = None, "", 0
            is_symbol_mode = 'ticker' in bundle

            if is_symbol_mode:
                stock_name, year = bundle['ticker'], bundle['year']
                self.log(f"Downloading {stock_name} for {year}...")
                raw = yf.download(stock_name, start=f"{year}-01-01", end=f"{year+1}-01-05", progress=False)
                if raw.empty: self.log("Error: No data found."); return
                col = 'Close' if 'Close' in raw.columns else 'Adj Close'
                if col not in raw.columns: self.log(f"Error: Price column not found. Cols: {raw.columns}"); return
                df = raw[[col]].rename(columns={col: 'Price'})
            else: # Manual
                stock_name = bundle['name']
                self.log("Parsing manual data...")
                lines, dates, prices = bundle['text'].split('\n'), [], []
                pattern = r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s*[-–]\s*([\d\.,]+)"
                for line in lines:
                    if not line.strip(): continue
                    match = re.search(pattern, line.strip())
                    if match:
                        d, m, y, p_str = match.groups()
                        try:
                            dates.append(datetime(int(y), int(m), int(d)))
                            prices.append(float(p_str.replace(',', '')))
                        except Exception as e: self.log(f"Skipping invalid line: {line} ({e})")
                    else: self.log(f"Format mismatch: {line}")
                if len(dates) < 2: self.log("Error: Need at least 2 valid data points."); return
                df = pd.DataFrame({'Price': prices}, index=dates).sort_index()
                year = df.index[0].year

            clean_name = re.sub(r'[^a-zA-Z0-9]', '', stock_name)
            temp_path = os.path.join("videos", f"temp_{clean_name}.mp4")
            
            # FILENAME LOGIC
            if bundle.get('quiz_mode'):
                final_path = os.path.join("videos", f"{clean_name}_Quiz.mp4")
            else:
                final_path = os.path.join("videos", f"{clean_name}_{year}_Review.mp4")
            
            animator = YearInReviewAnimator()
            animator.create_animation(
                data=df, stock_name=stock_name, year=year, output_path=temp_path,
                duration_sec=bundle['duration'],
                start_idle_sec=bundle['start_idle'],
                end_idle_sec=bundle['end_idle'],
                quiz_mode=bundle.get('quiz_mode', False),
                quiz_title=bundle.get('quiz_title'),
                quiz_subtitle=bundle.get('quiz_subtitle'),
                quiz_reveal_name=bundle.get('quiz_reveal_name'),
                log_callback=self.log
            )

            # Audio Merging
            if bundle['use_audio']:
                audio_path = os.path.join("audio", "background.mp3")
                ffmpeg_exe = "ffmpeg.exe" if os.path.exists("ffmpeg.exe") else "ffmpeg"
                if os.path.exists(audio_path):
                    self.log("Merging audio...")
                    cmd = [ffmpeg_exe, '-y', '-i', temp_path, '-i', audio_path, '-c:v', 'copy', '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0', '-shortest', final_path]
                    startupinfo = None
                    if os.name == 'nt': startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
                    if os.path.exists(temp_path): os.remove(temp_path)
                    self.log(f"SUCCESS! Video with audio saved: {final_path}")
                else:
                    self.log("Audio not found. Saving video only."); os.rename(temp_path, final_path)
                    self.log(f"SUCCESS! Video saved: {final_path}")
            else:
                self.log("Skipping audio."); os.rename(temp_path, final_path)
                self.log(f"SUCCESS! Video saved: {final_path}")
        except Exception as e:
            self.log(f"CRITICAL ERROR: {e}")
            import traceback; traceback.print_exc()
        finally:
            self.btn_gen.configure(state="normal")

if __name__ == "__main__":
    app = StockReviewApp()
    app.mainloop()