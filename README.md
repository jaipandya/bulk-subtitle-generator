# Bulk Subtitle Generator

🎬 Automatically generate subtitles for your video and audio files using Whisper.cpp

## Overview

This tool automates subtitle generation for media files in any directory. It uses `whisper-cli` (from whisper.cpp) for fast, accurate transcription and includes smart audio preprocessing and subtitle formatting.

## ✨ Features

- **Bulk Processing**: Process entire directories and subdirectories at once
- **Wide Format Support**: Works with video (.mp4, .mkv, .mov, .avi, .wmv, .flv, .webm) and audio (.mp3, .wav, .flac, .aac, .ogg, .m4a) files
- **Smart Resume**: Interrupted? Resume exactly where you left off
- **Professional Formatting**: Automatic subtitle formatting with customizable line length and caption limits
- **Multiple Languages**: Support for 99+ languages via Whisper
- **Performance Optimized**: Multi-threading support and audio preprocessing for optimal results

## 🚀 Quick Start

### Prerequisites

1. **Python 3.7+**
2. **FFmpeg** - For audio preprocessing
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt update && sudo apt install ffmpeg
   
   # Windows: Download from https://ffmpeg.org/download.html
   ```

3. **whisper-cli** - The command-line tool from whisper.cpp
   ```bash
   # macOS
   brew install whisper-cpp
   
   # Or compile from source: https://github.com/ggerganov/whisper.cpp
   ```

4. **Whisper Model** - Download a model file
   ```bash
   # Create models directory and download medium model (recommended)
   mkdir -p ~/whisper-models
   curl -L -o ~/whisper-models/ggml-medium.bin \
     https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin
   ```

### Basic Usage

```bash
# Generate English subtitles for all videos in current directory
python subtitle_generator.py .

# Generate Spanish subtitles for a specific directory
python subtitle_generator.py /path/to/videos -l es

# Use a different model and force overwrite existing subtitles
python subtitle_generator.py . --model-path ~/whisper-models/ggml-large.bin --force
```

## 📖 Usage Examples

### Generate subtitles with custom formatting
```bash
python subtitle_generator.py . --max-line-length 38 --max-lines 1
```

### Use more CPU threads for faster processing
```bash
python subtitle_generator.py . --threads 8
```

### Skip files that already have subtitles (default behavior)
```bash
python subtitle_generator.py . --skip-existing
```

### Process everything, ignoring existing subtitles
```bash
python subtitle_generator.py . --no-skip-existing
```

## 🛠️ Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `root_directory` | Directory to process (required) | - |
| `-l, --language` | Language code (en, es, fr, etc.) | `en` |
| `--model-path` | Path to GGML model file | `~/whisper-models/ggml-medium.bin` |
| `--cli-executable` | Whisper CLI executable name/path | `whisper-cli` |
| `--threads` | Number of CPU threads to use | `0` (auto) |
| `--max-line-length` | Max characters per subtitle line | `42` |
| `--max-lines` | Max lines per subtitle caption | `2` |
| `--skip-existing` | Skip files with existing subtitles | `True` |
| `--force` | Overwrite everything and ignore resume state | `False` |

## 📋 Supported Languages

Use standard language codes: `en` (English), `es` (Spanish), `fr` (French), `de` (German), `ja` (Japanese), `zh` (Chinese), and [many more](https://github.com/openai/whisper#available-models-and-languages).

## 🔧 Available Models

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| `tiny` | 39 MB | Fastest | Good |
| `base` | 74 MB | Fast | Better |
| `small` | 244 MB | Medium | Good |
| `medium` | 769 MB | Slower | Better |
| `large` | 1550 MB | Slowest | Best |

Download models from [Hugging Face](https://huggingface.co/ggerganov/whisper.cpp/tree/main).

## ❓ FAQ

### **Q: The script says "whisper-cli not found" - what do I do?**
**A:** Install whisper.cpp:
- macOS: `brew install whisper-cpp`
- Linux/Windows: Compile from [source](https://github.com/ggerganov/whisper.cpp)
- Alternative: Use `--cli-executable` to specify the full path to your whisper executable

### **Q: I interrupted the script - how do I resume?**
**A:** Just run the same command again! The script automatically saves progress and resumes from where it stopped.

### **Q: Can I process just one file?**
**A:** Yes! Put the file in a directory and run the script on that directory, or specify the directory containing your single file.

### **Q: The subtitles are too long/short per line - can I change this?**
**A:** Yes! Use `--max-line-length` to set characters per line and `--max-lines` to set lines per caption:
```bash
python subtitle_generator.py . --max-line-length 60 --max-lines 1
```

### **Q: What if I want to regenerate all subtitles?**
**A:** Use the `--force` flag to overwrite existing subtitle files and ignore resume state.

### **Q: Can I use a different Whisper model?**
**A:** Yes! Download any model from [Hugging Face](https://huggingface.co/ggerganov/whisper.cpp/tree/main) and use `--model-path` to specify it.

### **Q: The script is too slow - how can I speed it up?**
**A:** Try these options:
- Use more threads: `--threads 8`
- Use a smaller model: `--model-path ~/whisper-models/ggml-small.bin`
- Ensure you have a good CPU (Whisper is CPU-intensive)

### **Q: What subtitle format does this create?**
**A:** The script generates SRT files (`.srt`) with language codes (e.g., `video.en.srt` for English).

### **Q: Can I use this in my own scripts?**
**A:** Absolutely! Import the functions or modify the script for your needs. It's MIT licensed.

## 📄 License

MIT License - feel free to use, modify, and distribute!

## 🤝 Contributing

Found a bug or have a feature request? Please open an issue or submit a pull request!

---

⭐ **Like this project?** Give it a star on GitHub! 