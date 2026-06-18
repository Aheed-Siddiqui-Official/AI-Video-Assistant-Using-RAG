import yt_dlp
import os
import shutil
import sys
import re
from pathlib import Path

try:
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_dir = str(Path(ffmpeg_exe).parent)
    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
except Exception:
    pass

from pydub import AudioSegment

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def setup_ffmpeg():
    """Setup FFmpeg path"""
    # First try to find FFmpeg in PATH
    ffmpeg_path = shutil.which("ffmpeg")
    
    if not ffmpeg_path:
        try:
            # Try imageio_ffmpeg
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            AudioSegment.converter = ffmpeg_exe
            print(f"Found FFmpeg at: {ffmpeg_exe}")
            
            # Create a symlink or copy with standard name if needed
            ffmpeg_dir = Path(ffmpeg_exe).parent
            standard_ffmpeg = ffmpeg_dir / "ffmpeg.exe"
            
            if not standard_ffmpeg.exists():
                print(f"Creating symlink: {standard_ffmpeg}")
                try:
                    os.symlink(ffmpeg_exe, str(standard_ffmpeg))
                except (OSError, NotImplementedError):
                    # If symlink fails, try copying
                    print(f"Symlink failed, copying file instead...")
                    shutil.copy2(ffmpeg_exe, str(standard_ffmpeg))
            
            return str(ffmpeg_dir)
        except Exception as e:
            print(f"Could not find FFmpeg: {e}")
            return None
    
    # Return the directory containing ffmpeg
    AudioSegment.converter = ffmpeg_path
    return os.path.dirname(ffmpeg_path)

def extract_video_id(url: str) -> str:
    """Extract video ID from YouTube URL"""
    # Pattern for different YouTube URL formats
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/)([^&\n?#]+)',
        r'youtube\.com/watch\?.*v=([^&\n?#]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    raise ValueError(f"Could not extract video ID from URL: {url}")

def download_youtube_audio(url: str) -> str:
    try:
        # Extract and validate video ID
        video_id = extract_video_id(url)
        clean_url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"Downloading single video: {video_id}")
        print(f"URL: {clean_url}")
        
        ffmpeg_dir = setup_ffmpeg()
        
        output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_path,
            "noplaylist": True,  # Download only the single video, not playlists
            "quiet": False,
            "no_warnings": False,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                    "preferredquality": "192",
                }
            ],
        }
        
        if ffmpeg_dir:
            print(f"Using FFmpeg directory: {ffmpeg_dir}")
            ydl_opts["ffmpeg_location"] = ffmpeg_dir
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=True)
            filename = ydl.prepare_filename(info).replace(".webm", ".wav").replace(".m4a", ".wav")
        
        return filename
    
    except Exception as e:
        print(f"Error downloading audio: {e}")
        raise

def convert_to_wav(input_path: str) -> str:
    """Convert any audio/video file to WAV format using pydub."""
    output_path = os.path.splitext(input_path)[0] + "_converted.wav"
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1).set_frame_rate(16000) #16khz
    audio.export(output_path, format="wav")
    return output_path

def chunk_audio(wav_path : str, chunk_minutes : int = 10) -> list:
    audio = AudioSegment.from_wav(wav_path)
    chunk_ms = chunk_minutes * 60 * 1000

    chunks = []

    for i, start in enumerate(range(0, len(audio), chunk_ms)):
        chunk = audio[start : start + chunk_ms]
        chunk_path = f"{wav_path}_chunk_{i}.wav"
        chunk.export(chunk_path, format = "wav")

        chunks.append(chunk_path)

    return chunks

if __name__ == "__main__":
    data = download_youtube_audio("https://youtu.be/W1sRWyMtkfA?si=LqVpfgscuX-ZN379")
    data_final = convert_to_wav(data)
    print(chunk_audio(data_final))

def process_input(source: str) -> list:
    if source.startswith("http://") or source.startswith("https://"):
        print("Detected YouTube URL. Downloading audio...")
        wav_path = download_youtube_audio(source)
    else:
        print("Detected local file. Converting to WAV...")
        wav_path = convert_to_wav(source)

    print("Chunking audio...")
    chunks = chunk_audio(wav_path)
    print(f"Audio ready — {len(chunks)} chunk(s) created.")
    return chunks