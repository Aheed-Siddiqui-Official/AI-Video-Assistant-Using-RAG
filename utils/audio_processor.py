import os
import shutil
import re
from pathlib import Path

try:
    import yt_dlp
except ModuleNotFoundError:
    yt_dlp = None

from pydub import AudioSegment

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def setup_ffmpeg():
    """Setup FFmpeg for pydub and yt-dlp"""
    # Try to find ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    
    if not ffmpeg_path:
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            ffmpeg_path = ffmpeg_exe
            print(f"Using FFmpeg from imageio_ffmpeg: {ffmpeg_exe}")
        except Exception as e:
            print(f"Warning: Could not find FFmpeg: {e}")
    
    if ffmpeg_path:
        AudioSegment.converter = ffmpeg_path
        os.environ["PATH"] = str(Path(ffmpeg_path).parent) + os.pathsep + os.environ.get("PATH", "")
    
    return ffmpeg_path


def extract_video_id(url: str) -> str:
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
    """Download YouTube audio and convert to WAV"""
    if yt_dlp is None:
        raise ModuleNotFoundError("yt_dlp is not installed. Run: pip install yt-dlp")

    setup_ffmpeg()

    video_id = extract_video_id(url)
    clean_url = f"https://www.youtube.com/watch?v={video_id}"
    
    print(f"Downloading single video: {video_id}")
    print(f"URL: {clean_url}")

    output_template = os.path.join(DOWNLOAD_DIR, f"%(title)s_{video_id}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "192",
        }],
        "postprocessor_args": ["-ar", "16000", "-ac", "1"],  # 16kHz mono - best for RAG/STT
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(clean_url, download=True)
        
        # yt-dlp post-processor should have created the .wav
        base_name = ydl.prepare_filename(info)
        wav_path = os.path.splitext(base_name)[0] + ".wav"

        # Fallback: search for the most recent .wav containing the video_id
        if not os.path.exists(wav_path):
            candidates = [
                os.path.join(DOWNLOAD_DIR, f)
                for f in os.listdir(DOWNLOAD_DIR)
                if f.lower().endswith(".wav") and video_id in f
            ]
            if candidates:
                wav_path = max(candidates, key=os.path.getmtime)
            else:
                raise FileNotFoundError(f"WAV file was not created for video {video_id}")

    if not os.path.exists(wav_path):
        raise FileNotFoundError(f"Final audio file not found: {wav_path}")

    print(f"✅ Successfully downloaded: {wav_path} ({os.path.getsize(wav_path)/1024/1024:.2f} MB)")
    return wav_path


def chunk_audio(wav_path: str, chunk_minutes: int = 10) -> list:
    """Split audio into chunks"""
    if not os.path.exists(wav_path):
        raise FileNotFoundError(f"Audio file not found: {wav_path}")

    print(f"Chunking audio: {wav_path}")
    audio = AudioSegment.from_wav(wav_path)
    chunk_ms = chunk_minutes * 60 * 1000

    chunks = []
    for i, start in enumerate(range(0, len(audio), chunk_ms)):
        chunk = audio[start : start + chunk_ms]
        chunk_path = f"{os.path.splitext(wav_path)[0]}_chunk_{i:03d}.wav"
        
        chunk.export(chunk_path, format="wav")
        chunks.append(chunk_path)
        print(f"  Created chunk {i}: {chunk_path} ({len(chunk)/1000:.1f}s)")

    return chunks


def process_input(source: str) -> list:
    """Main entry point"""
    if source.startswith(("http://", "https://")):
        print("Detected YouTube URL. Downloading audio...")
        wav_path = download_youtube_audio(source)
    else:
        print("Detected local file. Converting to WAV...")
        wav_path = convert_to_wav(source)   # keep your original if needed

    print("Chunking audio...")
    chunks = chunk_audio(wav_path)
    print(f"✅ Audio ready — {len(chunks)} chunk(s) created.")
    return chunks


# Optional helper (only needed for local non-wav files)
def convert_to_wav(input_path: str) -> str:
    output_path = os.path.splitext(input_path)[0] + "_converted.wav"
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1).set_frame_rate(16000)
    audio.export(output_path, format="wav")
    return output_path