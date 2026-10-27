import asyncio
import speech_recognition as sr

from quart import Blueprint, request, jsonify
from io import BytesIO
from pydub import AudioSegment

bp = Blueprint("audio", __name__)


def _transcrever_audio(audio_bytes: bytes) -> str:
    """Converte e transcreve o áudio fora do event loop da aplicação."""
    audio_seg = AudioSegment.from_file(BytesIO(audio_bytes))
    wav_io = BytesIO()
    audio_seg.export(wav_io, format="wav")
    wav_io.seek(0)

    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_io) as source:
        audio_data = recognizer.record(source)

    return recognizer.recognize_google(audio_data, language="pt-BR")


@bp.route("/voice-to-text", methods=["POST"])
async def voice_to_text():
    files = await request.files
    if 'file' not in files:
        return jsonify({"error": "No file part"}), 400
    audio_file = files['file']

    try:
        audio_bytes = await asyncio.to_thread(audio_file.read)
        txt = await asyncio.to_thread(_transcrever_audio, audio_bytes)
        return jsonify({"transcription": txt})

    except sr.UnknownValueError:
        return jsonify({"error": "Não foi possível entender o áudio"}), 400

    except sr.RequestError as e:
        return jsonify({"error": str(e)}), 500
