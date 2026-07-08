import whisper

def transcribe_audio(audio_path):
    print(f"Transcribing: {audio_path.name}")
    model = whisper.load_model("base")
    result = model.transcribe(str(audio_path))
    return result["text"]