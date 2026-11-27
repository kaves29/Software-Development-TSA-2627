"""Analyze one temporary recording for Speakly onboarding."""

import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

router = APIRouter()
MAX_UPLOAD_BYTES = 80 * 1024 * 1024
MAX_MAIN_UPLOAD_BYTES = 50 * 1024 * 1024


def analyze_media(path, prompt, video):
    from backend.speech_analysis.__main__ import analyze_recording

    pose_model = os.getenv("SPEAKLY_POSE_MODEL")
    if video and not pose_model:
        raise HTTPException(503, "Set SPEAKLY_POSE_MODEL for video analysis.")
    filler_head = os.getenv("SPEAKLY_FILLER_HEAD") or None
    if filler_head and not Path(filler_head).is_file():
        raise HTTPException(503, "The filler model checkpoint is not available.")
    result = analyze_recording(path, [], os.getenv("SPEAKLY_WHISPER_MODEL", "small.en"),
                               os.getenv("SPEAKLY_MODEL_CACHE"), filler_head, prompt=prompt)
    if video:
        from backend.speech_analysis.video import analyze_video

        visual = analyze_video(path, Path(pose_model),
                               hand_model=os.getenv("SPEAKLY_HAND_MODEL") or None,
                               face_model=os.getenv("SPEAKLY_FACE_MODEL") or None,
                               pose_fingertip_proximity=os.getenv("SPEAKLY_POSE_FINGERTIP_PROXIMITY") == "1")
        result["features"].update(visual["features"])
        result["quality"]["video"] = visual["quality"]
    return result


def _analyze_upload(file, prompt, video, limit):
    if file.size is not None and file.size > limit:
        raise HTTPException(413, "Recording exceeds the upload limit.")
    with TemporaryDirectory() as directory:
        path = Path(directory) / "recording"
        size = 0
        with path.open("wb") as target:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, "Recording exceeds the upload limit.")
                target.write(chunk)
        if not size:
            raise HTTPException(422, "Provide a nonempty audio or video recording.")
        try:
            result = analyze_media(path, prompt, video)
        except (ValueError, subprocess.CalledProcessError) as exc:
            raise HTTPException(422, "Provide a decodable recording up to four minutes long.") from exc
        except (ImportError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            raise HTTPException(503, "Recording analysis is unavailable.") from exc
    return result


@router.post("/v1/onboarding/recordings")
def analyze_upload(file: Annotated[UploadFile, File()],
                   prompt: Annotated[str, Form(max_length=500)] = "",
                   video: Annotated[bool, Form()] = False):
    return {"id": uuid4().hex, "result": _analyze_upload(file, prompt, video, MAX_UPLOAD_BYTES)}


@router.post("/v1/onboarding/recordings/analyze")
def analyze_onboarding_recording(
    recording: Annotated[UploadFile, File()],
    sample_id: Annotated[str, Form(min_length=1, max_length=80)],
    prompt: Annotated[str, Form(min_length=1, max_length=500)],
    media_type: Annotated[str, Form(pattern="^(audio|video)$")],
):
    sample_id, prompt = sample_id.strip(), prompt.strip()
    if not sample_id or not prompt:
        raise HTTPException(422, "Sample ID and prompt must not be empty.")
    return {"id": sample_id, "result": _analyze_upload(
        recording, prompt, media_type == "video", MAX_MAIN_UPLOAD_BYTES)}
