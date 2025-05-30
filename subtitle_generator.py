"""
Batch Subtitle Generator using Whisper.cpp

A Python script that automatically generates subtitles for video and audio files
using whisper-cli from the whisper.cpp project. Supports batch processing,
resume functionality, and customizable subtitle formatting.

For detailed usage instructions and examples, see README.md.

Author: Batch Subtitle Generator Project
License: MIT
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

STATE_FILENAME = ".subtitle_generator_resume_state.json"
SUPPORTED_EXTENSIONS = (
    '.mp4', '.mkv', '.mov', '.avi', '.wmv', '.flv', '.webm',  # Video
    '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'           # Audio
)

# Constants for display formatting
PROGRESS_LINE_PADDING = 20


def generate_subtitles_for_media_files(root_dir, language='en', model_path='~/whisper-models/ggml-medium.bin', 
                                       cli_executable='whisper-cli', threads=0, max_line_length=42, max_lines=2, 
                                       skip_existing=True, force=False, resume_from_file=None, state_file_path=None):
    """
    Recursively find media files and generate subtitles using a Whisper CLI tool (e.g., whisper-cli from whisper.cpp)
    
    Args:
        root_dir (str): Root directory to start searching
        language (str): Language code for Whisper (default: 'en')
        model_path (str): Path to the GGML model file for whisper.cpp
        cli_executable (str): Path to the Whisper CLI executable (default: 'whisper-cli')
        threads (int): Number of threads for whisper.cpp (default: 0, let whisper.cpp decide)
        max_line_length (int): Maximum number of characters per subtitle line (default: 42)
        max_lines (int): Maximum number of lines per subtitle caption (default: 2)
        skip_existing (bool): Skip files that already have subtitles (default: True)
        force (bool): Force overwrite existing subtitle files and ignore resume state (default: False)
        resume_from_file (str): Path of the file to resume processing from
        state_file_path (str): Path to the state file for saving resume information
        
    Returns:
        bool: True if processing completed successfully
    """
    session_processed_count = 0
    session_error_count = 0

    def preprocess_audio(input_path, temp_output_dir):
        """Convert audio to a format optimal for Whisper (16kHz mono WAV)"""
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        wav_path = os.path.join(temp_output_dir, f"{base_name}.wav")
        
        ffmpeg_cmd = [
            'ffmpeg', '-i', input_path,
            '-ar', '16000',      # 16kHz sample rate
            '-ac', '1',          # Mono
            '-c:a', 'pcm_s16le', # 16-bit PCM
            '-y', wav_path       # Overwrite output file if it exists
        ]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
        return wav_path

    def clear_progress_line(progress_message):
        """Clear the current progress line"""
        sys.stdout.write("\r" + " " * (len(progress_message) + PROGRESS_LINE_PADDING) + "\r")
        sys.stdout.flush()
    
    # Find all supported media files
    all_media_files = []
    print(f"Scanning for media files ({', '.join(SUPPORTED_EXTENSIONS)})...")
    for subdir, _, files in os.walk(root_dir):
        for file_name in files:
            if file_name.lower().endswith(SUPPORTED_EXTENSIONS):
                all_media_files.append(os.path.join(subdir, file_name))
    
    if not all_media_files:
        print("No supported media files found.")
        return True

    total_overall_files = len(all_media_files)
    all_media_files.sort()  # Ensure consistent order for resuming

    start_index = 0
    if resume_from_file:
        try:
            start_index = all_media_files.index(resume_from_file)
            print(f"Resuming from: {resume_from_file} (file {start_index + 1} of {total_overall_files})")
        except ValueError:
            print(f"Warning: Resume file '{resume_from_file}' not found in the current list. Starting from the beginning.")

    files_to_process_session = all_media_files[start_index:]
    total_in_session = len(files_to_process_session)

    if total_in_session == 0 and resume_from_file:
        print("All files from the resume point seem to be processed or list is empty.")
        return True

    with tempfile.TemporaryDirectory() as temp_dir:
        for idx, media_path in enumerate(files_to_process_session):
            try:
                current_overall_idx = start_index + idx
                progress_message = (f"[{idx + 1}/{total_in_session}] "
                                   f"(Overall: {current_overall_idx + 1}/{total_overall_files}) "
                                   f"Processing: {os.path.basename(media_path)}...")
                
                clear_progress_line(progress_message)
                sys.stdout.write(progress_message)
                sys.stdout.flush()

                try:
                    # Generate subtitle filename with language code
                    base_name_no_ext = os.path.splitext(os.path.basename(media_path))[0]
                    target_srt_path = os.path.join(os.path.dirname(media_path), f"{base_name_no_ext}.{language}.srt")

                    # Skip if subtitle already exists, unless force is True
                    if not force and skip_existing and os.path.exists(target_srt_path):
                        clear_progress_line(progress_message)
                        print(f"Skipped (already exists): {target_srt_path}")
                        continue
                    
                    # Preprocess audio to WAV
                    wav_input_path = preprocess_audio(media_path, temp_dir)

                    # Build whisper-cli command
                    cmd = [
                        cli_executable,
                        '-m', model_path,
                        '-l', language,
                        '--output-srt', 
                    ]
                    if threads > 0:
                        cmd.extend(['-t', str(threads)])
                    if max_line_length > 0:
                        cmd.extend(['-ml', str(max_line_length)])
                    
                    cmd.append(wav_input_path)
                    
                    # Add a newline before Whisper starts so its output doesn't overwrite the script's progress line
                    print() 
                    subprocess.run(cmd, check=True)

                    # whisper-cli with --output-srt creates output like "basename_of_input.srt"
                    wav_input_basename = os.path.basename(wav_input_path)
                    cpp_generated_srt_filename = f"{wav_input_basename}.srt"
                    cpp_generated_srt_path = os.path.join(temp_dir, cpp_generated_srt_filename)

                    if os.path.exists(cpp_generated_srt_path):
                        # Move the generated SRT file to the target location
                        os.rename(cpp_generated_srt_path, target_srt_path)
                        # Post-process the SRT file for line length and line count
                        format_subtitle_lines(target_srt_path, max_line_length, max_lines)
                    else:
                        raise FileNotFoundError(f"Expected {cli_executable} to generate {cpp_generated_srt_path}, but it was not found.")

                    clear_progress_line(progress_message)
                    print(f"✓ Successfully generated: {target_srt_path}")
                    session_processed_count += 1
                        
                except subprocess.CalledProcessError as e:
                    clear_progress_line(progress_message)
                    print(f"✗ {cli_executable} command failed for {media_path}. Error: {e}")
                    session_error_count += 1
                except (FileNotFoundError, OSError) as e:
                    clear_progress_line(progress_message)
                    print(f"✗ File operation error with {media_path}: {e}")
                    session_error_count += 1
                except Exception as e:
                    clear_progress_line(progress_message)
                    print(f"✗ Unexpected error with {media_path}: {e}")
                    session_error_count += 1

            except KeyboardInterrupt:
                clear_progress_line(progress_message)
                print("\n🛑 Pausing...")
                if state_file_path:
                    save_resume_state(media_path, state_file_path)
                    print(f"Resume state saved. Next file to process: {media_path}")
                else:
                    print("State file path not configured, cannot save resume state.")
                print("Run the script again in the same directory to resume.")
                sys.exit(130)  # Standard exit code for Ctrl+C
                
    print(f"\nProcessing complete:")
    print(f"Successfully processed: {session_processed_count} files")
    print(f"Errors encountered: {session_error_count} files")
    return True


def load_resume_state(state_file_path):
    """Loads the resume state from the state file."""
    if os.path.exists(state_file_path):
        try:
            with open(state_file_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
                return state.get("next_file_to_process")
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not read or parse state file '{state_file_path}': {e}")
    return None


def save_resume_state(current_file_path, state_file_path):
    """Saves the current file path to the state file for resuming."""
    try:
        with open(state_file_path, 'w', encoding='utf-8') as f:
            json.dump({"next_file_to_process": current_file_path}, f)
    except OSError as e:
        print(f"Warning: Could not save state file '{state_file_path}': {e}")


def clear_resume_state(state_file_path):
    """Clears the resume state file."""
    if os.path.exists(state_file_path):
        try:
            os.remove(state_file_path)
            print(f"Resume state file '{state_file_path}' cleared.")
        except OSError as e:
            print(f"Warning: Could not clear state file '{state_file_path}': {e}")


def break_text_into_lines(text, max_chars_per_line=42, max_lines_per_caption=2):
    """Break text into lines respecting word boundaries and max lines per caption."""
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        # Check if adding this word would exceed the char limit for the current line
        test_line = f"{current_line} {word}" if current_line else word

        if len(test_line) <= max_chars_per_line:
            current_line = test_line
        else:
            # Current line is full, or word itself is too long
            if current_line:
                lines.append(current_line)
            current_line = word
            # Handle cases where a single word is longer than max_chars_per_line
            while len(current_line) > max_chars_per_line:
                lines.append(current_line[:max_chars_per_line])
                current_line = current_line[max_chars_per_line:]
    
    if current_line:
        lines.append(current_line)
    
    # Ensure we don't exceed max_lines_per_caption
    return '\n'.join(lines[:max_lines_per_caption])


def format_subtitle_lines(srt_path, max_chars_per_line=42, max_lines_per_caption=2):
    """Post-process SRT file to ensure proper line lengths and line counts."""
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    blocks = re.split(r'\n\s*\n', content.strip())
    formatted_blocks = []
    
    for block in blocks:
        if not block.strip():
            continue
        lines = block.split('\n')
        if len(lines) >= 3:  # Valid subtitle block: index, timing, text...
            index = lines[0]
            timing = lines[1]
            text_content = ' '.join(lines[2:])
            
            formatted_text = break_text_into_lines(text_content, max_chars_per_line, max_lines_per_caption)
            
            formatted_block = f"{index}\n{timing}\n{formatted_text}"
            formatted_blocks.append(formatted_block)
        else:
            formatted_blocks.append(block)  # Keep malformed blocks as is
    
    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(formatted_blocks) + '\n\n')


def validate_model_file(model_path_to_check):
    """Validate that the model file exists and expand user path."""
    expanded_path = os.path.expanduser(model_path_to_check)
    if not os.path.exists(expanded_path):
        print(f"Error: Model file not found at {expanded_path}")
        print("Please ensure the model file exists. You might need to download it, e.g.:")
        print("mkdir -p ~/whisper-models && curl -L -o ~/whisper-models/ggml-medium.bin "
              "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin")
        sys.exit(1)
    return expanded_path


def main():
    """Main function to handle command line arguments and orchestrate subtitle generation."""
    parser = argparse.ArgumentParser(description="Generate subtitles for media files using Whisper.")
    parser.add_argument("root_directory", help="Root directory to start searching for media files.")
    parser.add_argument("-l", "--language", default="en", 
                       help="Language code for Whisper (default: 'en').")
    parser.add_argument("--model-path", default=os.path.expanduser("~/whisper-models/ggml-medium.bin"), 
                       help="Path to the GGML model file (default: ~/whisper-models/ggml-medium.bin).")
    parser.add_argument("--cli-executable", default="whisper-cli", 
                       help="Path or name of the Whisper CLI executable (default: 'whisper-cli').")
    parser.add_argument("--threads", type=int, default=0, 
                       help="Number of threads for whisper.cpp (default: 0, whisper.cpp decides).")
    parser.add_argument("--max-line-length", type=int, default=42, 
                       help="Maximum characters per subtitle line (42 recommended). Default: 42.")
    parser.add_argument("--max-lines", type=int, default=2, 
                       help="Maximum lines per subtitle caption (2 recommended). Default: 2.")
    parser.add_argument("--skip-existing", action=argparse.BooleanOptionalAction, default=True, 
                       help="Skip files that already have subtitles (default: True). Use --no-skip-existing to disable.")
    parser.add_argument("--force", action="store_true", 
                       help="Force overwrite all existing subtitle files and ignore resume state.")
    
    args = parser.parse_args()
    
    root_directory = args.root_directory
    
    if not os.path.exists(root_directory):
        print(f"Error: Directory '{root_directory}' does not exist.")
        sys.exit(1)
    
    if not os.path.isdir(root_directory):
        print(f"Error: '{root_directory}' is not a directory.")
        sys.exit(1)
    
    # Validate and expand model path
    validated_model_path = validate_model_file(args.model_path)

    state_file_path = os.path.join(root_directory, STATE_FILENAME)
    resume_from_file = None

    if args.force:
        print("Force option enabled: Clearing any existing resume state and overwriting all subtitles.")
        clear_resume_state(state_file_path)
    else:
        resume_from_file = load_resume_state(state_file_path)
    
    thread_info = args.threads if args.threads > 0 else 'auto'
    print(f"Starting subtitle generation for directory: {root_directory}")
    print(f"Model: {validated_model_path}")
    print(f"Executable: {args.cli_executable}")
    print(f"Language: {args.language}")
    print(f"Threads: {thread_info}")
    print(f"Max Line Length: {args.max_line_length}")
    print(f"Max Lines: {args.max_lines}")
    print(f"Force: {args.force}")
    
    if resume_from_file and not args.force:
        print(f"Attempting to resume from state file: {state_file_path}")

    session_completed = generate_subtitles_for_media_files(
        root_dir=root_directory,
        language=args.language,
        model_path=validated_model_path,
        cli_executable=args.cli_executable,
        max_lines=args.max_lines,
        max_line_length=args.max_line_length,
        threads=args.threads,
        force=args.force,
        skip_existing=args.skip_existing,
        resume_from_file=resume_from_file,
        state_file_path=state_file_path
    )
    
    if session_completed and os.path.exists(state_file_path):
        clear_resume_state(state_file_path)


if __name__ == "__main__":
    main()
