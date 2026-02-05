# 🎯 MysteryChart

**MysteryChart** is a Python desktop application that generates cinematic, vertical **“Guess the Asset”** videos from real financial data.

It animates historical stock or crypto price charts and turns them into engaging quiz-style videos where viewers try to guess the asset before the reveal — perfect for **TikTok, Instagram Reels, and YouTube Shorts**.

---

## ✨ Features

* 📈 Smooth animated chart drawing with glow effects
* 🧠 Quiz-style format: *Can you guess the asset?*
* 🔓 Optional answer reveal at the end
* 🎬 Vertical video output (1080×1920, Shorts-ready)
* 🔉 Optional background audio
* 🌐 Automatic data download via Yahoo Finance
* ✍️ Manual data input supported
* 🖥️ Simple desktop UI built with CustomTkinter

---

## 🛠️ Tech Stack

* **Python 3.10+**
* CustomTkinter (GUI)
* Matplotlib (animation & rendering)
* Pandas / NumPy (data processing)
* yFinance (market data)
* SciPy (optional, for smoothing)
* FFmpeg (video & audio processing)

---

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/MysteryChart.git
cd MysteryChart
```

### 2. Create virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate  # Linux / macOS
.venv\Scripts\activate     # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

Or if you are using **uv**:

```bash
uv sync
```

### 4. Install FFmpeg

Make sure `ffmpeg` is available in your system PATH.

* Windows: [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
* macOS: `brew install ffmpeg`
* Linux: `sudo apt install ffmpeg`

---

## ▶️ Usage

Run the application:

```bash
python main.py
```

### You can:

* Download real market data (stocks / crypto)
* Paste your own historical price data manually
* Choose whether to reveal the correct answer
* Add background music
* Generate a vertical MP4 video automatically

Generated videos are saved in the `videos/` folder.

---

## 📁 Project Structure

```
MysteryChart/
├── main.py
├── stock_year_review.py
├── videos/
├── audio/
├── README.md
├── pyproject.toml
└── .gitignore
```

---

## 🎥 Use Cases

* TikTok / Reels finance content
* YouTube Shorts market quizzes
* Educational finance videos
* Portfolio & demo projects

---

## ⚠️ Notes

* SciPy is optional — the app works without it
* yFinance is required only for automatic data downloads
* Large datasets may increase render time

---

## 📜 License

MIT License — free to use, modify, and distribute.

---

## ⭐️ Support

If you like this project, feel free to star the repository ⭐️

Contributions and ideas are welcome!
