import os
import base64
import tempfile
from io import BytesIO
from pydub import AudioSegment
from typing import Any, Dict, List, Optional
from pyannote.core import Annotation
from app.schemas.conversations import FileData
from app.services.manage_models.model_manager import model_manager

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

def detect_audio_format(file_bytes: bytes) -> Optional[str]:
    """
    Detect audio format based on file header/magic bytes.
    
    Args:
        file_bytes (bytes): Raw file bytes
        
    Returns:
        Optional[str]: Detected format or None if unknown
    """
    # Check for common audio format signatures
    if file_bytes.startswith(b'RIFF') and b'WAVE' in file_bytes[:12]:
        return 'wav'
    elif file_bytes.startswith(b'ID3') or file_bytes.startswith(b'\xff\xfb'):
        return 'mp3'
    elif file_bytes.startswith(b'OggS'):
        return 'ogg'
    elif file_bytes.startswith(b'fLaC'):
        return 'flac'
    elif file_bytes.startswith(b'\x00\x00\x00 ftypM4A'):
        return 'm4a'
    elif file_bytes.startswith(b'#!AMR'):
        return 'amr'
    else:
        # Try to detect based on common patterns
        if b'ftypmp4' in file_bytes[:32] or b'ftypisom' in file_bytes[:32]:
            return 'mp4'
        elif file_bytes.startswith(b'\xff\xf1') or file_bytes.startswith(b'\xff\xf9'):
            return 'aac'
    
    return None

def load_audio_from_bytes(file_bytes: bytes, temp_path: str) -> AudioSegment:
    """
    Load audio from bytes with format detection and error handling.
    
    Args:
        file_bytes (bytes): Raw audio file bytes
        temp_path (str): Path to temporary file
        
    Returns:
        AudioSegment: Loaded audio segment
        
    Raises:
        ValueError: If audio format cannot be determined or loaded
    """
    detected_format = detect_audio_format(file_bytes)
    
    # List of formats to try in order
    formats_to_try = []
    if detected_format:
        formats_to_try.append(detected_format)
    
    # Add common formats as fallbacks
    common_formats = ['wav', 'mp3', 'ogg', 'flac', 'm4a', 'aac', 'mp4', 'webm']
    for fmt in common_formats:
        if fmt not in formats_to_try:
            formats_to_try.append(fmt)
    
    last_error = None
    
    for audio_format in formats_to_try:
        try:
            # Create temporary file with appropriate extension
            temp_file_path = f"{temp_path}.{audio_format}"
            with open(temp_file_path, 'wb') as f:
                f.write(file_bytes)
            
            # Try to load with detected/guessed format
            if audio_format == 'wav':
                audio = AudioSegment.from_wav(temp_file_path)
            elif audio_format == 'mp3':
                audio = AudioSegment.from_mp3(temp_file_path)
            elif audio_format == 'ogg':
                audio = AudioSegment.from_ogg(temp_file_path)
            elif audio_format == 'flac':
                audio = AudioSegment.from_flac(temp_file_path)
            elif audio_format in ['m4a', 'aac']:
                audio = AudioSegment.from_file(temp_file_path, format='m4a')
            elif audio_format == 'mp4':
                audio = AudioSegment.from_file(temp_file_path, format='mp4')
            elif audio_format == 'webm':
                audio = AudioSegment.from_file(temp_file_path, format='webm')
            else:
                # Generic loader
                audio = AudioSegment.from_file(temp_file_path, format=audio_format)
            
            print(f"Successfully loaded audio as {audio_format}")
            
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass
                
            return audio.set_frame_rate(16000)
            
        except Exception as e:
            last_error = e
            print(f"Failed to load as {audio_format}: {e}")
            # Clean up failed temporary file
            try:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
            except OSError:
                pass
            continue
    
    # If we get here, all formats failed
    raise ValueError(f"Could not load audio file. Tried formats: {formats_to_try}. Last error: {last_error}")

def validate_file_data(file_data: FileData) -> None:
    """
    Validate the input file data.
    
    Args:
        file_data (FileData): File data to validate
        
    Raises:
        ValueError: If file data is invalid
    """
    if not file_data or not file_data.file:
        raise ValueError("No file data provided")
    
    if len(file_data.file) == 0:
        raise ValueError("File is empty")
    
    # Check minimum file size (100 bytes is very small for audio)
    if len(file_data.file) < 100:
        raise ValueError("File too small to be valid audio")
    
    # Check maximum file size (100MB limit)
    if len(file_data.file) > 100 * 1024 * 1024:
        raise ValueError("File too large (>100MB)")

def process_filedata_with_diarization(file_data: FileData) -> Dict[str, Any]:
    """
    Processes a FileData object (from frontend) for VAD and speaker diarization.
    
    Args:
        file_data (FileData): Uploaded file containing audio bytes and metadata.
    
    Returns:
        Dict[str, Any]: A dictionary containing the diarization result and the base64-encoded speech-only audio.
        
    Raises:
        ValueError: If file cannot be processed
        RuntimeError: If audio processing models fail
    """
    temp_audio_path = None
    temp_speech_path = None
    temp_base_path = None

    try:
        # Validate input
        validate_file_data(file_data)
        print(f"Processing audio file of size: {len(file_data.file)} bytes")
        
        # Create base temporary file path
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp_file:
            temp_base_path = tmp_file.name
        
        # Load and preprocess audio with format detection
        print("Loading audio with format detection...")
        audio = load_audio_from_bytes(file_data.file, temp_base_path)
        
        print(f"Audio loaded successfully: {len(audio)}ms duration, {audio.frame_rate}Hz sample rate")
        
        # Check audio duration (minimum 1 second)
        if len(audio) < 1000:
            raise ValueError("Audio file too short (less than 1 second)")
        
        # Save the processed audio to a temporary WAV file for pipeline processing
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio_file:
            temp_audio_path = tmp_audio_file.name
            audio.export(tmp_audio_file, format="wav")

        # Load pipelines
        print("Loading voice activity detection model...")
        vad_pipeline = model_manager.get_model("voice-activity-detection")
        
        print("Loading speaker diarization model...")
        diarization_pipeline = model_manager.get_model("speaker-diarization")

        # Apply Voice Activity Detection
        print("Applying Voice Activity Detection...")
        try:
            speech_regions = vad_pipeline(temp_audio_path)
        except Exception as e:
            raise RuntimeError(f"Voice Activity Detection failed: {e}")

        # Check if any speech was detected
        timeline = speech_regions.get_timeline()
        if not timeline:
            print("No speech detected - likely music, noise, or non-vocal audio")
            # Return empty results for non-speech audio with empty string instead of None
            processed_audio = {
                "diarization": [],
                "speech_audio_base64": "",  # Empty string instead of None
                "metadata": {
                    "original_duration_ms": len(audio),
                    "speech_duration_ms": 0,
                    "sample_rate": audio.frame_rate,
                    "channels": audio.channels,
                    "segments_count": 0,
                    "audio_type": "non_speech",
                    "message": "No speech detected in audio file (music/noise/instrumental)"
                }
            }
            return processed_audio

        print("Cropping non-speech parts...")
        speech_only_audio = AudioSegment.empty()
        total_speech_duration = 0
        
        for segment in timeline:
            start_ms = int(segment.start * 1000)
            end_ms = int(segment.end * 1000)
            segment_audio = audio[start_ms:end_ms]
            speech_only_audio += segment_audio
            total_speech_duration += (end_ms - start_ms)

        print(f"Speech-only audio duration: {total_speech_duration}ms")
        
        # Check if we have enough speech for diarization
        if len(speech_only_audio) < 1000:
            print("Very little speech detected - returning minimal results")
            processed_audio = {
                "diarization": [],
                "speech_audio_base64": audiosegment_to_base64(speech_only_audio) if len(speech_only_audio) > 0 else "",  # Empty string instead of None
                "metadata": {
                    "original_duration_ms": len(audio),
                    "speech_duration_ms": len(speech_only_audio),
                    "sample_rate": audio.frame_rate,
                    "channels": audio.channels,
                    "segments_count": 0,
                    "audio_type": "minimal_speech",
                    "message": f"Very little speech detected ({len(speech_only_audio)}ms)"
                }
            }
            return processed_audio

        # Save speech-only audio for diarization
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_speech_file:
            temp_speech_path = tmp_speech_file.name
            speech_only_audio.export(tmp_speech_file, format="wav")

        print("Running speaker diarization...")
        try:
            diarization = diarization_pipeline(temp_speech_path)
        except Exception as e:
            print(f"Diarization failed, returning speech without speaker labels: {e}")
            # Return speech audio without diarization if speaker separation fails
            processed_audio = {
                "diarization": [],
                "speech_audio_base64": audiosegment_to_base64(speech_only_audio),
                "metadata": {
                    "original_duration_ms": len(audio),
                    "speech_duration_ms": len(speech_only_audio),
                    "sample_rate": audio.frame_rate,
                    "channels": audio.channels,
                    "segments_count": 0,
                    "audio_type": "speech_no_diarization",
                    "message": f"Speech detected but diarization failed: {e}"
                }
            }
            return processed_audio

        # Convert results
        segments = annotation_to_segments(diarization)
        speech_base64 = audiosegment_to_base64(speech_only_audio)
        
        print(f"Processing completed successfully. Found {len(segments)} diarization segments")

        processed_audio = {
            "diarization": segments,
            "speech_audio_base64": speech_base64,
            "metadata": {
                "original_duration_ms": len(audio),
                "speech_duration_ms": len(speech_only_audio),
                "sample_rate": audio.frame_rate,
                "channels": audio.channels,
                "segments_count": len(segments),
                "audio_type": "speech_with_diarization",
                "message": f"Successfully processed speech with {len(segments)} speaker segments"
            }
        }
        return processed_audio

    except ValueError as e:
        print(f"Validation error in audio processing: {e}")
        raise
    except RuntimeError as e:
        print(f"Runtime error in audio processing: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error in audio processing: {e}")
        raise RuntimeError(f"Audio processing failed: {e}")
    finally:
        # Clean up all temporary files
        for temp_path in [temp_audio_path, temp_speech_path, temp_base_path]:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError as e:
                    print(f"Warning: Could not delete temporary file {temp_path}: {e}")