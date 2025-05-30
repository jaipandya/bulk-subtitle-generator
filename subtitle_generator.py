"""
Bulk Subtitle Generator using Whisper.cpp

A Python script that automatically generates subtitles for video and audio files
using whisper-cli from the whisper.cpp project. Supports batch processing,
resume functionality, and customizable subtitle formatting.

For detailed usage instructions and examples, see README.md.
"""
import os
import subprocess
import sys
import argparse
import json
import tempfile
import re # For post-processing

STATE_FILENAME = ".subtitle_generator_resume_state.json"
SUPPORTED_EXTENSIONS = (
    '.mp4', '.mkv', '.mov', '.avi', '.wmv', '.flv', '.webm',  # Video
    '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'           # Audio
)


def generate_subtitles_for_mp4s(root_dir, language='en', model_path='~/whisper-models/ggml-medium.bin', cli_executable='whisper-cli', threads=0, max_line_length=42, max_lines=2, skip_existing=True, force=False, resume_from_file=None, state_file_path=None):
    """
    Recursively find MP4 files and generate subtitles using a Whisper CLI tool (e.g., whisper-cli from whisper.cpp)
    
    Args:
        root_dir: Root directory to start searching
        language: Language code for Whisper (default: 'en')
        model_path: Path to the GGML model file for whisper.cpp (default: '~/whisper-models/ggml-medium.bin')
        cli_executable: Path to the Whisper CLI executable (default: 'whisper-cli')
        threads: Number of threads for whisper.cpp (default: 0, let whisper.cpp decide)
        max_line_length: Maximum number of characters per subtitle line (default: 42).
        max_lines: Maximum number of lines per subtitle caption (default: 2).
        skip_existing: Skip files that already have subtitles (default: True)
        force: Force overwrite existing subtitle files and ignore resume state (default: False)
        resume_from_file: Path of the file to resume processing from.
        state_file_path: Path to the state file for saving resume information.
    """
    session_processed_count = 0
    session_error_count = 0

    # Validate model file path (expanded)
    # Note: model_path is already expanded in main() before calling this function
    # if not os.path.exists(model_path):
    #     print(f"Error: Model file not found at {model_path}")
    #     sys.exit(1)

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
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True) # capture_output to hide ffmpeg's verbose output
        return wav_path
    
    all_mp4_full_paths = []
    print(f"Scanning for media files ({', '.join(SUPPORTED_EXTENSIONS)})...")
    for subdir, _, files in os.walk(root_dir):
        for file_name in files:
            if file_name.lower().endswith(SUPPORTED_EXTENSIONS):
                all_mp4_full_paths.append(os.path.join(subdir, file_name))
    
    if not all_mp4_full_paths:
        print("No supported media files found.")
        return True # Nothing to process, considered complete

    total_overall_files = len(all_mp4_full_paths)
    all_mp4_full_paths.sort() # Ensure consistent order for resuming

    start_index = 0
    if resume_from_file:
        try:
            start_index = all_mp4_full_paths.index(resume_from_file)
            print(f"Resuming from: {resume_from_file} (file {start_index + 1} of {total_overall_files})")
        except ValueError:
            print(f"Warning: Resume file '{resume_from_file}' not found in the current list. Starting from the beginning.")
            # Optionally, clear the invalid resume_from_file here or let it proceed from start_index = 0

    files_to_process_session = all_mp4_full_paths[start_index:]
    total_in_session = len(files_to_process_session)

    if total_in_session == 0 and resume_from_file: # Resuming but no files left
        print("All files from the resume point seem to be processed or list is empty.")
        return True

    with tempfile.TemporaryDirectory() as temp_dir:
        for idx, mp4_path in enumerate(files_to_process_session):
            try:
                current_overall_idx = start_index + idx
                progress_message = f"[{idx + 1}/{total_in_session}] (Overall: {current_overall_idx + 1}/{total_overall_files}) Processing: {os.path.basename(mp4_path)}..."
                
                # Clear previous line content (adjust width as needed)
                sys.stdout.write("\r" + " " * (len(progress_message) + 20) + "\r") 
                sys.stdout.write(progress_message)
                sys.stdout.flush()

                try:
                    # Generate subtitle filename with language code
                    base_name_no_ext = os.path.splitext(os.path.basename(mp4_path))[0]
                    target_srt_path = os.path.join(os.path.dirname(mp4_path), f"{base_name_no_ext}.{language}.srt")
                    output_directory = os.path.dirname(mp4_path)

                    # Skip if subtitle already exists, unless force is True
                    if not force and skip_existing and os.path.exists(target_srt_path):
                        sys.stdout.write("\r" + " " * (len(progress_message) + 20) + "\r") # Clear progress line
                        sys.stdout.flush()
                        print(f"Skipped (already exists): {target_srt_path}")
                        continue
                    
                    # Preprocess audio to WAV
                    wav_input_path = preprocess_audio(mp4_path, temp_dir)

                    # whisper-cli command
                    cmd = [
                        cli_executable,
                        '-m', model_path, # model_path is already expanded in main()
                        '-l', language,
                        '--output-srt', 
                        # Input file is a positional argument at the end
                    ]
                    if threads > 0:
                        cmd.extend(['-t', str(threads)]) # Use -t for threads
                    if max_line_length > 0:
                        cmd.extend(['-ml', str(max_line_length)])
                    
                    cmd.append(wav_input_path) # Add preprocessed WAV file as input
                    
                    # Add a newline before Whisper starts so its output doesn't overwrite the script's progress line
                    print() 
                    subprocess.run(cmd, check=True)

                    # whisper-cli with --output-srt creates output like "basename_of_input.srt"
                    # The input to whisper-cli was the WAV file in temp_dir.
                    # So, the SRT will be generated in temp_dir next to the WAV file.
                    wav_input_basename = os.path.basename(wav_input_path)  # Gets "filename.wav"
                    cpp_generated_srt_filename_in_temp = f"{wav_input_basename}.srt"  # Creates "filename.wav.srt"
                    cpp_generated_srt_full_path_in_temp = os.path.join(temp_dir, cpp_generated_srt_filename_in_temp)

                    if os.path.exists(cpp_generated_srt_full_path_in_temp):
                        # Move the generated SRT file from temp_dir to the original video's directory with the target name
                        os.rename(cpp_generated_srt_full_path_in_temp, target_srt_path)
                        # Post-process the SRT file for line length and line count
                        format_subtitle_lines(target_srt_path, max_line_length, max_lines)
                    else:
                        raise FileNotFoundError(f"Expected {cli_executable} to generate {cpp_generated_srt_full_path_in_temp}, but it was not found.")

                    sys.stdout.write("\r" + " " * (len(progress_message) + 20) + "\r") # Clear progress line
                    sys.stdout.flush()
                    print(f"✓ Successfully generated: {target_srt_path}")
                    session_processed_count += 1
                        
                except subprocess.CalledProcessError as e:
                    sys.stdout.write("\r" + " " * (len(progress_message) + 20) + "\r") # Clear progress line
                    sys.stdout.flush()
                    print(f"✗ {cli_executable} command failed for {mp4_path}. See output above. Error: {e}")
                    session_error_count += 1
                except Exception as e:
                    sys.stdout.write("\r" + " " * (len(progress_message) + 20) + "\r") # Clear progress line
                    sys.stdout.flush()
                    print(f"✗ Unexpected error with {mp4_path}: {e}")
                    session_error_count += 1

            except KeyboardInterrupt:
                sys.stdout.write("\r" + " " * (len(progress_message) + 20) + "\r") # Clear progress line
                sys.stdout.flush()
                print("\n🛑 Pausing...")
                if state_file_path:
                    save_resume_state(mp4_path, state_file_path)
                    print(f"Resume state saved. Next file to process: {mp4_path}")
                else:
                    print("State file path not configured, cannot save resume state.")
                print("Run the script again in the same directory to resume.")
                sys.exit(130) # Standard exit code for Ctrl+C
                
    print(f"\nProcessing complete:")
    print(f"Successfully processed: {session_processed_count} files")
    print(f"Errors encountered: {session_error_count} files")
    return True # Indicates all files in the current (potentially resumed) batch were attempted

def load_resume_state(state_file_path):
    """Loads the resume state from the state file."""
    if os.path.exists(state_file_path):
        try:
            with open(state_file_path, 'r') as f:
                state = json.load(f)
                return state.get("next_file_to_process")
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read or parse state file '{state_file_path}': {e}")
    return None

def save_resume_state(current_file_path, state_file_path):
    """Saves the current file path to the state file for resuming."""
    try:
        with open(state_file_path, 'w') as f:
            json.dump({"next_file_to_process": current_file_path}, f)
    except IOError as e:
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
        if current_line: # if current_line is not empty
            test_line = f"{current_line} {word}"
        else:
            test_line = word

        if len(test_line) <= max_chars_per_line:
            current_line = test_line
        else:
            # Current line is full, or word itself is too long
            if current_line: # Add the completed line
                lines.append(current_line)
            current_line = word # Start a new line with the current word
            # Handle cases where a single word is longer than max_chars_per_line
            while len(current_line) > max_chars_per_line:
                lines.append(current_line[:max_chars_per_line])
                current_line = current_line[max_chars_per_line:]
    
    if current_line: # Add the last line
        lines.append(current_line)
    
    # Ensure we don't exceed max_lines_per_caption
    return '\n'.join(lines[:max_lines_per_caption])

def format_subtitle_lines(srt_path, max_chars_per_line=42, max_lines_per_caption=2):
    """Post-process SRT file to ensure proper line lengths and line counts."""
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    blocks = re.split(r'\n\s*\n', content.strip()) # Split by one or more blank lines
    formatted_blocks = []
    
    for block in blocks:
        if not block.strip(): continue # Skip empty blocks if any
        lines = block.split('\n')
        if len(lines) >= 3:  # Valid subtitle block: index, timing, text...
            index = lines[0]
            timing = lines[1]
            text_content = ' '.join(lines[2:]) # Join all text lines first
            
            formatted_text = break_text_into_lines(text_content, max_chars_per_line, max_lines_per_caption)
            
            formatted_block = f"{index}\n{timing}\n{formatted_text}"
            formatted_blocks.append(formatted_block)
        else:
            formatted_blocks.append(block) # Keep malformed blocks as is
    
    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(formatted_blocks) + '\n\n') # Ensure trailing newlines for SRT

def validate_model_file(model_path_to_check):
    """Validate that the model file exists and expand user path."""
    expanded_path = os.path.expanduser(model_path_to_check)
    if not os.path.exists(expanded_path):
        print(f"Error: Model file not found at {expanded_path}")
        print("Please ensure the model file exists. You might need to download it, e.g.:")
        print("mkdir -p ~/whisper-models && curl -L -o ~/whisper-models/ggml-medium.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin")
        sys.exit(1)
    return expanded_path

def main():
    parser = argparse.ArgumentParser(description="Generate subtitles for MP4 files using Whisper.")
    parser.add_argument("root_directory", help="Root directory to start searching for MP4 files.")
    parser.add_argument("-l", "--language", default="en", help="Language code for Whisper (default: 'en').")
    parser.add_argument("--model-path", default=os.path.expanduser("~/whisper-models/ggml-medium.bin"), help="Path to the GGML model file (default: ~/whisper-models/ggml-medium.bin).")
    parser.add_argument("--cli-executable", default="whisper-cli", help="Path or name of the Whisper CLI executable (default: 'whisper-cli').") #
    parser.add_argument("--threads", type=int, default=0, help="Number of threads for whisper.cpp (default: 0, whisper.cpp decides).")
    parser.add_argument("--max-line-length", type=int, default=42, help="Maximum characters per subtitle line (42 recommended). Default: 42.")
    parser.add_argument("--max-lines", type=int, default=2, help="Maximum lines per subtitle caption (2 recommended). Default: 2.")
    parser.add_argument("--skip-existing", action=argparse.BooleanOptionalAction, default=True, help="Skip files that already have subtitles (default: True). Use --no-skip-existing to disable.")
    parser.add_argument("--force", action="store_true", help="Force overwrite all existing subtitle files and ignore resume state.")
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
    
    print(f"Starting subtitle generation for directory: {root_directory} (Model: {validated_model_path}, Executable: {args.cli_executable}, Language: {args.language}, Threads: {args.threads if args.threads > 0 else 'auto'}, Max Line Length: {args.max_line_length}, Max Lines: {args.max_lines}, Force: {args.force})")
    if resume_from_file and not args.force: # Only print resume message if not forcing
        print(f"Attempting to resume from state file: {state_file_path}")

    session_completed = generate_subtitles_for_mp4s(
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
    if session_completed and os.path.exists(state_file_path): # Clear state only if fully completed
        clear_resume_state(state_file_path)

if __name__ == "__main__":
    main()
