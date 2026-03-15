@app.get("/metadata/{task_id}")
async def get_metadata(task_id: str):
    """Return Claude's production plan metadata for the show."""
    task = load_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.get("status") != "SUCCESS":
        raise HTTPException(status_code=400, detail="Task not complete.")
    return {
        "show_title":       task.get("show_title", "Your Radio Show"),
        "show_tagline":     task.get("show_tagline", ""),
        "show_summary":     task.get("show_summary", ""),
        "keywords":         task.get("keywords", []),
        "segments":         task.get("segments", []),
        "highlights":       task.get("highlights", []),
        "production_notes": task.get("production_notes", ""),
        "mood":             task.get("mood", ""),
        "duration":         task.get("duration", 0),
    }


@app.get("/download/{task_id}/{format}")
async def download_result_format(task_id: str, format: str):
    """Download in specified format: mp3_high, mp3_low, wav."""
    task = load_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.get("status") != "SUCCESS":
        raise HTTPException(status_code=400, detail="Task not complete.")

    result_file = task.get("result_file", "")
    if not result_file:
        raise HTTPException(status_code=404, detail="No output file found.")

    # Find base WAV file
    base_path = Path(result_file)
    wav_path  = base_path.with_suffix(".wav")
    if not wav_path.is_file():
        wav_path = base_path  # use whatever we have

    if not wav_path.is_file():
        raise HTTPException(status_code=404, detail="Output file not found.")

    if format == "wav":
        return FileResponse(
            path=str(wav_path),
            media_type="audio/wav",
            filename="radio_show_final.wav",
        )

    # MP3 high quality (320kbps)
    if format == "mp3_high":
        mp3_path = wav_path.parent / "radio_show_final_320.mp3"
        if not mp3_path.is_file():
            try:
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-i", str(wav_path),
                        "-codec:a", "libmp3lame",
                        "-b:a", "320k",
                        str(mp3_path),
                    ],
                    check=True, capture_output=True,
                )
            except subprocess.CalledProcessError as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Conversion failed: {exc.stderr.decode()}"
                )
        return FileResponse(
            path=str(mp3_path),
            media_type="audio/mpeg",
            filename="radio_show_final_320kbps.mp3",
        )

    # MP3 low quality (96kbps) — smallest size
    if format == "mp3_low":
        mp3_path = wav_path.parent / "radio_show_final_96.mp3"
        if not mp3_path.is_file():
            try:
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-i", str(wav_path),
                        "-codec:a", "libmp3lame",
                        "-b:a", "96k",
                        str(mp3_path),
                    ],
                    check=True, capture_output=True,
                )
            except subprocess.CalledProcessError as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Conversion failed: {exc.stderr.decode()}"
                )
        return FileResponse(
            path=str(mp3_path),
            media_type="audio/mpeg",
            filename="radio_show_final_96kbps.mp3",
        )

    # Default MP3 (190kbps VBR)
    mp3_path = wav_path.parent / "radio_show_final.mp3"
    if not mp3_path.is_file():
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(wav_path),
                    "-codec:a", "libmp3lame",
                    "-qscale:a", "2",
                    str(mp3_path),
                ],
                check=True, capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Conversion failed: {exc.stderr.decode()}"
            )
    return FileResponse(
        path=str(mp3_path),
        media_type="audio/mpeg",
        filename="radio_show_final.mp3",
    )
