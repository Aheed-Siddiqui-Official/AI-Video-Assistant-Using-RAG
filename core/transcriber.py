import whisper
import os

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")

_model = None
def load_model():
    global _model

    if _model is None:
        print(f"loading model ...")
        _model = whisper.load_model(WHISPER_MODEL)
        print("whisper model loaded successfully")

    return _model

# will return transcription text
def transcribe_chunk(chunk_path : str, translate : bool = False) -> str:
    model = load_model()

    task = "translate" if translate else "transcribe"
    
    result = model.transcribe(chunk_path, task="transcribe") 

    return result["text"]  