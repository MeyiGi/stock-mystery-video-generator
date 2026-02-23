import customtkinter as ctk
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.dates as mdates
import matplotlib.image as mpimg
from matplotlib.ticker import FuncFormatter
import os
import shutil
import re
import threading
import subprocess
from datetime import datetime
from tkinter import filedialog

# ==========================================
# CONFIGURATION
# ==========================================
VIDEO_WIDTH  = 1080
VIDEO_HEIGHT = 1920
FPS = 30

BACKGROUND_COLOR = "#121212"
STOCK_COLOR      = "#1DB954"
FONT_LIGHT_COLOR = "#FFFFFF"
FONT_MUTED_COLOR = "#A0A0A0"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")


class YearInReviewAnimator:

    def _format_currency(self, x, pos):
        sign = '-' if x < 0 else ''
        x = abs(x)
        if x >= 1_000_000: return f'{sign}${x/1_000_000:.1f}M'
        if x >= 1_000:     return f'{sign}${x/1_000:.0f}K'
        return f'{sign}${x:,.0f}'

    def _get_adaptive_fontsize(self, text, base=80, max_chars=6):
        if len(text) > max_chars:
            return int(base * (max_chars / len(text)))
        return base

    def create_animation(self, data, stock_name, year, output_path,
                         duration_sec, start_idle_sec, end_idle_sec,
                         quiz_mode=False,
                         quiz_title=None, quiz_subtitle=None, quiz_reveal_name=None,
                         logo_path=None,
                         log_callback=print,
                         progress_callback=None):

        log_callback(f"Init: {stock_name} | {duration_sec}s draw | {start_idle_sec}s start | {end_idle_sec}s end")

        # ── 1. Data ───────────────────────────────────────────────────────────────
        if 'Price' not in data.columns:
            raise ValueError("Dataframe must have a 'Price' column")

        resampled_data = data['Price'].resample('D').interpolate(method='linear')
        start_p    = float(resampled_data.iloc[0])
        end_p      = float(resampled_data.iloc[-1])
        high_date  = resampled_data.idxmax()
        high_p     = float(resampled_data.max())
        low_date   = resampled_data.idxmin()
        low_p      = float(resampled_data.min())
        pct_change = ((end_p - start_p) / start_p) * 100 if start_p != 0 else 0

        # ── 2. Figure ─────────────────────────────────────────────────────────────
        dpi = 120
        fig, ax = plt.subplots(figsize=(VIDEO_WIDTH / dpi, VIDEO_HEIGHT / dpi), dpi=dpi)
        fig.patch.set_facecolor(BACKGROUND_COLOR)
        ax.set_facecolor(BACKGROUND_COLOR)

        # ── 3. Layout constants ───────────────────────────────────────────────────
        #
        #  0.960 ── Title
        #  0.925 ── Subtitle
        #
        #  [LOGO ZONE 0.845–0.910]  reserved when logo present; hidden until reveal
        #
        #  CHART_TOP  = 0.835 (logo) | 0.905 (no logo)
        #  ... chart body ...
        #  CHART_BOTTOM = 0.115   ← large bottom margin for x-axis labels
        #
        #  0.040 ── FINJOVI.COM (big white pill)

        has_logo = bool(logo_path and os.path.exists(logo_path))

        TITLE_Y    = 0.960
        SUBTITLE_Y = 0.928

        LOGO_BOT = 0.845
        LOGO_H   = 0.065   # top of logo slot = 0.910 — clear gap below subtitle

        CHART_TOP    = 0.835 if has_logo else 0.905
        CHART_BOTTOM = 0.15
        CHART_LEFT   = 0.17
        CHART_RIGHT  = 0.95

        chart_mid    = (CHART_TOP + CHART_BOTTOM) / 2
        REVEAL_BIG_Y = chart_mid + 0.03
        REVEAL_SUB_Y = REVEAL_BIG_Y - 0.05

        # ── 4. FINJOVI.COM watermark — white rounded pill, large ─────────────────
        fig.text(0.5, 0.08, "FINJOVI.COM", fontsize=50, color="black", fontweight="bold",
                 ha="center", va="center", fontfamily="serif",
                 bbox=dict(facecolor="#D3D3D3", edgecolor="none", boxstyle="round,pad=0.4", alpha=1.0))

        # ── 5. Title + subtitle (always visible) ──────────────────────────────────
        title_str = (quiz_title or "Can you guess this stock?") if quiz_mode else stock_name
        title_fs  = min(48, max(26, int(48 * 20 / max(len(title_str), 20))))
        fig.text(0.5, TITLE_Y, title_str,
                 ha='center', va='center',
                 fontsize=title_fs, fontweight='bold',
                 color=FONT_LIGHT_COLOR, fontfamily='sans-serif')

        sub_str = ((quiz_subtitle or "answer in comments \U0001f447") if quiz_mode
                   else (f"{year} PERFORMANCE" if year else "PERFORMANCE"))
        fig.text(0.5, SUBTITLE_Y, sub_str,
                 ha='center', va='center',
                 fontsize=28, color=FONT_MUTED_COLOR, fontfamily='sans-serif')

        # ── 6. Logo axes — hidden at start, revealed at end-phase ────────────────
        logo_ax = None
        if has_logo:
            try:
                raw = mpimg.imread(logo_path)
                # Ensure RGBA so matplotlib respects transparency (no white box)
                if raw.ndim == 3 and raw.shape[2] == 3:
                    alpha_ch = np.ones((*raw.shape[:2], 1), dtype=raw.dtype)
                    raw = np.concatenate([raw, alpha_ch], axis=2)

                logo_ax = fig.add_axes([0.25, LOGO_BOT, 0.50, LOGO_H])
                logo_ax.set_facecolor('none')
                logo_ax.patch.set_alpha(0.0)
                logo_ax.imshow(raw)
                logo_ax.axis('off')
                logo_ax.set_zorder(20)
                if quiz_mode:
                    # В викторине скрываем до конца
                    logo_ax.set_visible(False)
                    log_callback("Logo loaded — will appear at reveal.")
                else:
                    # В Year in Review показываем сразу
                    logo_ax.set_visible(True)
                    log_callback("Logo loaded — visible from start.")
                log_callback("Logo loaded — will appear at reveal.")
            except Exception as e:
                log_callback(f"Warning: could not load logo: {e}")
                logo_ax  = None
                has_logo = False
                CHART_TOP    = 0.905
                chart_mid    = (CHART_TOP + CHART_BOTTOM) / 2
                REVEAL_BIG_Y = chart_mid + 0.03
                REVEAL_SUB_Y = REVEAL_BIG_Y - 0.05

        # ── 7. Chart geometry ─────────────────────────────────────────────────────
        plt.subplots_adjust(top=CHART_TOP, bottom=CHART_BOTTOM,
                            left=CHART_LEFT, right=CHART_RIGHT)

        # ── 8. End-reveal text (hidden during animation) ──────────────────────────
        if quiz_mode:
            if quiz_reveal_name:
                fs = self._get_adaptive_fontsize(quiz_reveal_name, base=90, max_chars=6)
                final_text = fig.text(0.5, REVEAL_BIG_Y, quiz_reveal_name,
                                      ha='center', va='center', fontsize=fs,
                                      fontweight='bold', color=FONT_LIGHT_COLOR,
                                      visible=False, zorder=10)
                final_sub  = fig.text(0.5, REVEAL_SUB_Y, "The Answer!",
                                      ha='center', va='center', fontsize=24,
                                      color=FONT_MUTED_COLOR, visible=False, zorder=10)
            else:
                final_text = final_sub = None
        else:
            cc   = 'limegreen' if pct_change >= 0 else 'tomato'
            sign = '+' if pct_change >= 0 else ''
            ps   = f"{sign}{pct_change:.1f}%"
            fs   = self._get_adaptive_fontsize(ps, base=90, max_chars=6)
            # final_text = fig.text(0.5, REVEAL_BIG_Y, ps,
            #                       ha='center', va='center', fontsize=fs,
            #                       fontweight='bold', color=cc,
            #                       visible=False, zorder=10)
            final_text = None
            # final_sub  = fig.text(0.5, REVEAL_SUB_Y, "Total Change",
            #                       ha='center', va='center', fontsize=24,
            #                       color=FONT_MUTED_COLOR, visible=False, zorder=10)
            final_sub = None

        # ── 9. Chart elements ─────────────────────────────────────────────────────
        line, = ax.plot([], [], color=STOCK_COLOR, lw=4.5, solid_capstyle='round')
        head, = ax.plot([], [], 'o', color=STOCK_COLOR, markersize=14,
                        markeredgecolor='white', markeredgewidth=2, zorder=6)
        date_label = ax.text(0, 0, "", color=FONT_LIGHT_COLOR, fontsize=18,
                             ha='center', va='bottom', fontweight='bold',
                             fontfamily='sans-serif', zorder=7)
        high_marker, = ax.plot([], [], 'o', color='gold',        markersize=12, visible=False, zorder=8)
        low_marker,  = ax.plot([], [], 'o', color='deepskyblue', markersize=12, visible=False, zorder=8)

        # ── 10. Axis limits ───────────────────────────────────────────────────────
        date_range_days = (resampled_data.index[-1] - resampled_data.index[0]).days
        date_span       = resampled_data.index[-1] - resampled_data.index[0]
        ax.set_xlim(resampled_data.index[0],
                    resampled_data.index[-1] + date_span * 0.02)

        y_range   = high_p - low_p if high_p != low_p else abs(high_p) * 0.1 or 1.0
        y_pad_top = y_range * 0.20
        y_pad_bot = y_range * 0.25
        ax.set_ylim(low_p - y_pad_bot, high_p + y_pad_top)

        for artist in (ax, line, head, high_marker, low_marker):
            artist.set_clip_on(False)

        # ── 11. Axis formatting ───────────────────────────────────────────────────
        if date_range_days <= 366:
            ax.xaxis.set_major_locator(mdates.MonthLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
        else:
            yrs = date_range_days / 365.25
            locator = (mdates.YearLocator(1) if yrs <= 10 else
                       mdates.YearLocator(2) if yrs <= 20 else
                       mdates.YearLocator(5))
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

        ax.yaxis.set_major_formatter(FuncFormatter(self._format_currency))
        ax.tick_params(colors=FONT_MUTED_COLOR, labelsize=16, pad=10)
        ax.grid(axis='y', linestyle='--', linewidth=0.5, color='#444444')
        for spine in ax.spines.values():
            spine.set_visible(False)

        # ── 12. Frame indices ─────────────────────────────────────────────────────
        frames_main  = int(duration_sec   * FPS)
        frames_start = int(start_idle_sec * FPS)
        frames_end   = int(end_idle_sec   * FPS)
        total_frames = frames_start + frames_main + frames_end

        idx_main    = np.linspace(0, len(resampled_data) - 1, frames_main, dtype=int)
        all_indices = np.concatenate([
            np.zeros(frames_start, dtype=int),
            idx_main,
            np.full(frames_end, len(resampled_data) - 1, dtype=int),
        ])

        anim_elements = [line, head, date_label, high_marker, low_marker]
        if final_text:
            anim_elements += [final_text, final_sub]

        ax_y_span   = (high_p + y_pad_top) - (low_p - y_pad_bot)
        date_format = "%b %Y" if date_range_days > 366 else "%b %d"
        end_frame   = frames_start + frames_main

        # ── 13. Update ────────────────────────────────────────────────────────────
        def update(frame_index):
            idx       = all_indices[frame_index]
            cur_data  = resampled_data.iloc[:idx + 1]
            cur_date  = cur_data.index[-1]
            cur_price = float(cur_data.iloc[-1])

            line.set_data(cur_data.index, cur_data.values)
            head.set_data([cur_date], [cur_price])
            date_label.set_position((cur_date, cur_price + ax_y_span * 0.04))
            date_label.set_text(cur_date.strftime(date_format))
            date_label.set_visible(True)
            head.set_visible(True)

            if frame_index >= end_frame:
                date_label.set_visible(False)
                head.set_visible(False)
                if final_text and final_sub:
                    final_text.set_visible(True)
                    final_sub.set_visible(True)
                if logo_ax is not None:
                    logo_ax.set_visible(True)
                high_marker.set_data([high_date], [high_p])
                high_marker.set_visible(True)
                low_marker.set_data([low_date], [low_p])
                low_marker.set_visible(True)

            remaining = total_frames - frame_index
            pct       = int(frame_index / total_frames * 100)

            # Push pct to GUI progress bar on every frame
            if progress_callback:
                progress_callback(pct)

            # Log text every 30 frames
            if frame_index % 30 == 0:
                msg = f"Frame {frame_index}/{total_frames} ({pct}%) — {remaining} frames left"
                log_callback(msg)
                print(f"  >> {msg}", flush=True)

            return anim_elements

        # ── 14. Save ──────────────────────────────────────────────────────────────
        if not shutil.which("ffmpeg") and not os.path.exists("ffmpeg.exe"):
            log_callback("ERROR: ffmpeg not found. Install it or place ffmpeg.exe here.")
            return

        log_callback(f"Starting render: {total_frames} frames @ {FPS}fps")
        print(f"\n{'='*55}\n  Rendering {total_frames} frames → {output_path}\n{'='*55}", flush=True)

        writer = animation.FFMpegWriter(
            fps=FPS, bitrate=8000,
            extra_args=['-vcodec', 'libx264', '-pix_fmt', 'yuv420p'])
        ani = animation.FuncAnimation(fig, update, frames=total_frames, blit=False)
        ani.save(output_path, writer=writer)
        plt.close(fig)

        if progress_callback:
            progress_callback(100)
        log_callback("Render complete.")
        print(f"\n  ✓ Done: {output_path}\n", flush=True)


class StockReviewApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Stock Video Generator")
        self.geometry("620x950")
        self.resizable(False, False)

        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(self.main_frame, text="STOCK VIDEO GENERATOR",
                     font=("Arial", 22, "bold")).pack(pady=(10, 15))

        # ── Tabs ──────────────────────────────────────────────────────────────────
        self.mode_tabview = ctk.CTkTabview(self.main_frame)
        self.mode_tabview.pack(fill="x", expand=True, padx=10)
        self.tab_quiz   = self.mode_tabview.add("Quiz Mode")
        self.tab_review = self.mode_tabview.add("Year in Review")
        self.mode_tabview.set("Quiz Mode")

        self._setup_manual_tab(self.tab_quiz,   is_quiz=True)
        self._setup_quiz_fields()
        self._setup_manual_tab(self.tab_review, is_quiz=False)

        # ── Settings ──────────────────────────────────────────────────────────────
        self.settings_frame = ctk.CTkFrame(self.main_frame)
        self.settings_frame.pack(fill="x", padx=10, pady=(6, 4))

        # Logo upload
        self.logo_path = None
        logo_row = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        logo_row.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkButton(logo_row, text="Upload Logo", width=110,
                      command=self.choose_logo).pack(side="left", padx=(0, 8))
        self.lbl_logo = ctk.CTkLabel(logo_row, text="No logo selected",
                                     font=("Arial", 11), text_color=FONT_MUTED_COLOR,
                                     anchor="w")
        self.lbl_logo.pack(side="left", fill="x", expand=True)

        # Duration
        self.lbl_duration = ctk.CTkLabel(self.settings_frame,
                                         text="Animation Duration: 10s", font=("Arial", 12))
        self.lbl_duration.pack(pady=(5, 0))
        self.slider_duration = ctk.CTkSlider(self.settings_frame, from_=5, to=30,
                                             number_of_steps=25,
                                             command=self.update_duration_label)
        self.slider_duration.set(10)
        self.slider_duration.pack(fill="x", padx=20, pady=(0, 10))

        # Idle row
        idle_row = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        idle_row.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkLabel(idle_row, text="Start Idle (s):").pack(side="left", padx=(10, 5))
        self.entry_start_idle = ctk.CTkEntry(idle_row, width=50)
        self.entry_start_idle.pack(side="left")
        self.entry_start_idle.insert(0, "1.0")
        ctk.CTkLabel(idle_row, text="End Idle (s):").pack(side="left", padx=(20, 5))
        self.entry_end_idle = ctk.CTkEntry(idle_row, width=50)
        self.entry_end_idle.pack(side="left")
        self.entry_end_idle.insert(0, "4.0")

        # Audio
        self.use_audio_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.main_frame,
                        text="Use Audio (merge audio/background.mp3)",
                        variable=self.use_audio_var,
                        font=("Arial", 12)).pack(pady=(5, 5))

        # Generate button
        self.btn_gen = ctk.CTkButton(
            self.main_frame, text="GENERATE VIDEO", height=50,
            fg_color="#39FF14", text_color="black", hover_color="#2cc712",
            font=("Arial", 16, "bold"), command=self.start_generation)
        self.btn_gen.pack(fill="x", padx=10, pady=(8, 4))

        # ── Progress bar ──────────────────────────────────────────────────────────
        self.progress_bar = ctk.CTkProgressBar(self.main_frame, height=20)
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 2))
        self.progress_bar.set(0)

        self.lbl_progress = ctk.CTkLabel(
            self.main_frame, text="Ready",
            font=("Arial", 12, "bold"), text_color=FONT_MUTED_COLOR)
        self.lbl_progress.pack(pady=(0, 4))

        # Log box
        self.log_box = ctk.CTkTextbox(self.main_frame, height=130, font=("Consolas", 11))
        self.log_box.pack(fill="x", padx=10, pady=(0, 10))

        os.makedirs("videos", exist_ok=True)
        os.makedirs("audio",  exist_ok=True)

    # ── UI builders ───────────────────────────────────────────────────────────────
    def _setup_manual_tab(self, parent_tab, is_quiz=False):
        name_key = 'quiz_manual_name' if is_quiz else 'review_manual_name'
        text_key = 'quiz_manual_text' if is_quiz else 'review_manual_text'

        ctk.CTkLabel(parent_tab, text="Stock/Asset Name:", anchor="w").pack(
            fill="x", padx=10, pady=(10, 0))
        setattr(self, name_key, ctk.CTkEntry(parent_tab, placeholder_text="My Portfolio"))
        getattr(self, name_key).pack(fill="x", padx=10, pady=(5, 10))

        ctk.CTkLabel(parent_tab,
                     text="Data (e.g. 'YYYY-MM-DD price' or 'DD.MM.YYYY price'):",
                     anchor="w").pack(fill="x", padx=10)
        setattr(self, text_key, ctk.CTkTextbox(parent_tab, height=150))
        getattr(self, text_key).pack(fill="both", expand=True, padx=10, pady=5)
        getattr(self, text_key).insert("0.0", "01.01.2023 500\n15.06.2023 700\n31.12.2023 1200")

    def _setup_quiz_fields(self):
        qf = ctk.CTkFrame(self.tab_quiz, fg_color="transparent")
        qf.pack(fill="x", padx=10, pady=(10, 10))

        ctk.CTkLabel(qf, text="Quiz Title:", font=("Arial", 12, "bold")).pack(anchor="w", padx=10)
        self.entry_quiz_title = ctk.CTkEntry(
            qf, placeholder_text="Can you guess this stock from the chart?")
        self.entry_quiz_title.pack(fill="x", padx=10, pady=(0, 5))
        self.entry_quiz_title.insert(0, "Can you guess this stock from the chart?")

        ctk.CTkLabel(qf, text="Quiz Subtitle:", font=("Arial", 12, "bold")).pack(anchor="w", padx=10)
        self.entry_quiz_subtitle = ctk.CTkEntry(qf, placeholder_text="answer in comments \U0001f447")
        self.entry_quiz_subtitle.pack(fill="x", padx=10, pady=(0, 5))
        self.entry_quiz_subtitle.insert(0, "answer in comments \U0001f447")

        ctk.CTkLabel(qf, text="Reveal Name (optional):",
                     font=("Arial", 12, "bold")).pack(anchor="w", padx=10)
        self.entry_quiz_reveal = ctk.CTkEntry(qf, placeholder_text="e.g., BAC, AAPL, or Apple")
        self.entry_quiz_reveal.pack(fill="x", padx=10, pady=(0, 5))

    # ── Helpers ───────────────────────────────────────────────────────────────────
    def choose_logo(self):
        path = filedialog.askopenfilename(
            title="Select Logo Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp"),
                       ("All files", "*.*")])
        if path:
            self.logo_path = path
            fn = os.path.basename(path)
            self.lbl_logo.configure(
                text=fn if len(fn) <= 40 else f"...{fn[-37:]}",
                text_color=FONT_LIGHT_COLOR)

    def update_duration_label(self, value):
        self.lbl_duration.configure(text=f"Animation Duration: {int(value)}s")

    def log(self, msg):
        self.log_box.insert("end", f"> {msg}\n")
        self.log_box.see("end")

    def set_progress(self, pct):
        """Thread-safe — schedules update on the main Tk thread."""
        self.after(0, self._apply_progress, pct)

    def _apply_progress(self, pct):
        self.progress_bar.set(pct / 100)
        if pct >= 100:
            self.lbl_progress.configure(text="✓  Done!", text_color="#39FF14")
        else:
            self.lbl_progress.configure(
                text=f"Rendering…  {pct}%", text_color=FONT_MUTED_COLOR)

    # ── Generation ────────────────────────────────────────────────────────────────
    def start_generation(self):
        self.btn_gen.configure(state="disabled")
        self.progress_bar.set(0)
        self.lbl_progress.configure(text="Starting…", text_color=FONT_MUTED_COLOR)

        bundle = {}
        bundle['duration']  = int(self.slider_duration.get())
        bundle['use_audio'] = self.use_audio_var.get()
        bundle['logo_path'] = self.logo_path
        try:
            bundle['start_idle'] = float(self.entry_start_idle.get())
            bundle['end_idle']   = float(self.entry_end_idle.get())
        except ValueError:
            self.log("Error: Idle times must be numbers.")
            self.btn_gen.configure(state="normal")
            return

        mode = self.mode_tabview.get()
        bundle['quiz_mode'] = (mode == "Quiz Mode")
        if bundle['quiz_mode']:
            bundle['quiz_title']       = self.entry_quiz_title.get().strip()
            bundle['quiz_subtitle']    = self.entry_quiz_subtitle.get().strip()
            bundle['quiz_reveal_name'] = self.entry_quiz_reveal.get().strip()

        name_entry = self.quiz_manual_name if bundle['quiz_mode'] else self.review_manual_name
        text_entry = self.quiz_manual_text if bundle['quiz_mode'] else self.review_manual_text
        bundle['name'] = name_entry.get().strip()
        bundle['text'] = text_entry.get("0.0", "end").strip()

        if not bundle['name']:
            self.log("Error: Enter an asset name.")
            self.btn_gen.configure(state="normal")
            return

        threading.Thread(target=self.run_process, args=(bundle,), daemon=True).start()

    def run_process(self, bundle):
        try:
            stock_name = bundle['name']
            self.log("Parsing data…")
            dates, prices = [], []
            for line in bundle['text'].split('\n'):
                line = line.strip()
                if not line:
                    continue
                try:
                    parts = line.rsplit(maxsplit=1)
                    if len(parts) != 2:
                        self.log(f"Skipping malformed line: '{line}'")
                        continue
                    date_str, price_str = parts
                    dt    = pd.to_datetime(date_str, dayfirst=('.' in date_str))
                    price = float(price_str.replace(',', ''))
                    dates.append(dt)
                    prices.append(price)
                except Exception as e:
                    self.log(f"Skipping invalid line: '{line}' ({e})")

            if len(dates) < 2:
                self.log("Error: Need at least 2 valid data points.")
                return

            df   = pd.DataFrame({'Price': prices},
                                 index=pd.to_datetime(dates)).sort_index()
            year = df.index[0].year if len(df.index) > 0 else 0

            clean_name = re.sub(r'[^a-zA-Z0-9]', '', stock_name)
            temp_path  = os.path.join("videos", f"temp_{clean_name}.mp4")
            final_path = (os.path.join("videos", f"{clean_name}_Quiz.mp4")
                          if bundle.get('quiz_mode')
                          else os.path.join("videos", f"{clean_name}_{year}_Review.mp4"))

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
                logo_path=bundle.get('logo_path'),
                log_callback=self.log,
                progress_callback=self.set_progress,
            )

            if bundle['use_audio']:
                audio_path = os.path.join("audio", "background.mp3")
                ffmpeg_exe = "ffmpeg.exe" if os.path.exists("ffmpeg.exe") else "ffmpeg"
                if os.path.exists(audio_path):
                    self.log("Merging audio…")
                    cmd = [ffmpeg_exe, '-y', '-i', temp_path, '-i', audio_path,
                           '-c:v', 'copy', '-c:a', 'aac',
                           '-map', '0:v:0', '-map', '1:a:0', '-shortest', final_path]
                    si = None
                    if os.name == 'nt':
                        si = subprocess.STARTUPINFO()
                        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    subprocess.run(cmd, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, startupinfo=si)
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    self.log(f"SUCCESS! Saved: {final_path}")
                else:
                    self.log("Audio not found — saving video only.")
                    os.rename(temp_path, final_path)
                    self.log(f"SUCCESS! Saved: {final_path}")
            else:
                self.log("Skipping audio.")
                os.rename(temp_path, final_path)
                self.log(f"SUCCESS! Saved: {final_path}")

        except Exception as e:
            self.log(f"CRITICAL ERROR: {e}")
            import traceback; traceback.print_exc()
        finally:
            self.btn_gen.configure(state="normal")


if __name__ == "__main__":
    app = StockReviewApp()
    app.mainloop()