import os
import torch
import base64
import tempfile
from io import BytesIO
from pydub import AudioSegment
from typing import Any, Dict, List
from pyannote.audio import Pipeline
from pyannote.core import Annotation
from app.schemas.conversations import FileData
from app.database.redis_client import get_redis_config

def annotation_to_segments(annotation: Annotation) -> List[Dict[str, Any]]:
    return [
        {
            "start": segment.start,
            "end": segment.end,
            "speaker": track
        }
        for segment, track in annotation.itertracks()
    ]

def audiosegment_to_base64(audio_segment: AudioSegment) -> str:
    buffer = BytesIO()
    audio_segment.export(buffer, format="wav")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def process_filedata_with_diarization(file_data: FileData) -> Dict[str, Any]:
    """
    Processes a FileData object (from frontend) for VAD and speaker diarization.
    
    Args:
        file_data (FileData): Uploaded file containing audio bytes and metadata.
    
    Returns:
        Tuple[Any, AudioSegment]: Diarization result object and speech-only audio.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    temp_audio_path = None
    temp_speech_path = None

    try:
        # Save the uploaded file to a temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio_file:
            temp_audio_path = tmp_audio_file.name
            tmp_audio_file.write(file_data.file)

        # Load pipelines
        vad_pipeline = Pipeline.from_pretrained(
            "pyannote/voice-activity-detection",
            use_auth_token=get_redis_config("api_keys")["HF_AUTH_TOKEN"]
        ).to(device)

        diarization_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=get_redis_config("api_keys")["HF_AUTH_TOKEN"]
        ).to(device)

        # Load and preprocess original audio
        audio = AudioSegment.from_wav(temp_audio_path).set_frame_rate(16000)

        print("Applying Voice Activity Detection...")
        speech_regions = vad_pipeline(temp_audio_path)

        print("Cropping non-speech parts...")
        speech_only_audio = AudioSegment.empty()
        for segment in speech_regions.get_timeline():
            start_ms = int(segment.start * 1000)
            end_ms = int(segment.end * 1000)
            speech_only_audio += audio[start_ms:end_ms]

        # Save speech-only audio for diarization
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_speech_file:
            temp_speech_path = tmp_speech_file.name
            speech_only_audio.export(tmp_speech_file, format="wav")

        print("Running speaker diarization...")
        diarization = diarization_pipeline(temp_speech_path)

        processed_audio = {
            "diarization": annotation_to_segments(diarization),
            "speech_audio_base64": audiosegment_to_base64(speech_only_audio)
        }
        return processed_audio

    except Exception as e:
        print(f"Error in audio processing: {e}")
        raise
    finally:
        for temp_path in [temp_audio_path, temp_speech_path]:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError as e:
                    print(f"Warning: Could not delete temporary file {temp_path}: {e}")