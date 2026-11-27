"""Analyze an onboarding recording using the existing research pipeline."""

import os
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import StringConstraints
from typing import Annotated

router = APIRouter()
MAX_RECORDING_BYTES = 50 * 1024 * 1024


def analyze_sample(path: Path, prompt: str, video: bool) -> dict:
    from backend.speech_analysis.__main__ import analyze_recording

    result = analyze_recording(
        path, [], os.getenv("SPEAKLY_WHISPER_MODEL", "small.en"),
        os.getenv("SPEAKLY_MODEL_CACHE"),
        os.getenv("SPEAKLY_FILLER_HEAD") or None,
        prompt=prompt,
    )
    if video:
        pose_model = os.getenv("SPEAKLY_POSE_MODEL")
        if not pose_model or not Path(pose_model).is_file():
            raise RuntimeError("Video analysis model is not configured")
        from backend.speech_analysis.video import analyze_video

        video_result = analyze_video(path, pose_model)
        result["features"].update(video_result["features"])
        result["quality"]["video"] = video_result["quality"]
    return result


@router.post("/v1/onboarding/recordings/analyze")
async def analyze_onboarding_recording(
    recording: Annotated[UploadFile, File()],
    sample_id: Annotated[str, Form(), StringConstraints(strip_whitespace=True, min_length=1, max_length=80)],
    prompt: Annotated[str, Form(), StringConstraints(strip_whitespace=True, min_length=1, max_length=500)],
    media_type: Annotated[str, Form(pattern="^(audio|video)$")],
):
    try:
        with tempfile.TemporaryDirectory(prefix="speakly-recording-") as directory:
            path = Path(directory) / "recording"
            size = 0
            with path.open("wb") as destination:
                while chunk := await recording.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_RECORDING_BYTES:
                        raise HTTPException(413, "Recording exceeds the 50 MB limit.")
                    destination.write(chunk)
            if size == 0:
                raise HTTPException(422, "Recording is empty.")
            try:
                from starlette.concurrency import run_in_threadpool

                result = await run_in_threadpool(analyze_sample, path, prompt, media_type == "video")
            except (ImportError, ModuleNotFoundError, FileNotFoundError) as exc:
                raise HTTPException(503, "Recording analysis is not configured on this server.") from exc
            except (ValueError, subprocess.SubprocessError) as exc:
                raise HTTPException(422, "The recording could not be analyzed. Check its format and length.") from exc
            except (RuntimeError, OSError) as exc:
                raise HTTPException(503, "Recording analysis is temporarily unavailable.") from exc
            return {"id": sample_id, "result": result}
    finally:
        await recording.close()
