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


def analyze_media(path, prompt, video):
    from backend.speech_analysis.__main__ import analyze_recording

    pose_model = os.getenv("SPEAKLY_POSE_MODEL")
    if video and not pose_model:
        raise HTTPException(503, "Set SPEAKLY_POSE_MODEL for video analysis.")
    result = analyze_recording(path, [], os.getenv("SPEAKLY_WHISPER_MODEL", "small.en"),
                               os.getenv("SPEAKLY_MODEL_CACHE"), prompt=prompt)
    if video:
        from backend.speech_analysis.video import analyze_video

        visual = analyze_video(path, Path(pose_model))
        result["features"].update(visual["features"])
        result["quality"]["video"] = visual["quality"]
    return result


@router.post("/v1/onboarding/recordings")
def analyze_upload(file: Annotated[UploadFile, File()],
                   prompt: Annotated[str, Form(max_length=500)] = "",
                   video: Annotated[bool, Form()] = False):
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Recording exceeds the 80 MiB upload limit.")
    with TemporaryDirectory() as directory:
        path = Path(directory) / "recording"
        size = 0
        with path.open("wb") as target:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Recording exceeds the 80 MiB upload limit.")
                target.write(chunk)
        if not size:
            raise HTTPException(422, "Provide a nonempty audio or video recording.")
        try:
            result = analyze_media(path, prompt, video)
        except (ValueError, subprocess.CalledProcessError) as exc:
            raise HTTPException(422, "Provide a decodable recording up to four minutes long.") from exc
        except (ImportError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            raise HTTPException(503, "Recording analysis is unavailable.") from exc
    return {"id": uuid4().hex, "result": result}
