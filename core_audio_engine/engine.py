def process_audio(task_id: str, file_path: str) -> None:
    """Run the full pipeline in a background thread with Jamendo API music."""
    from core_audio_engine.engine import run_pipeline

    tasks[task_id]["status"] = "PROCESSING"

    fp = Path(file_path)
    if not fp.is_file():
        tasks[task_id]["status"] = "FAILURE"
        tasks[task_id]["error"] = f"Uploaded file not found: {fp}"
        return

    output_dir = fp.parent / "output"
    output_file = fp.parent / "radio_show_final.wav"
    
    # --- NEW JAMENDO API LOGIC ---
    logger.info("Fetching background music from Jamendo API...")
    music_path = str(fp.parent / "jamendo_track.mp3")
    client_id = os.environ.get("JAMENDO_CLIENT_ID")
    
    if client_id:
        try:
            # We are defaulting to 'lofi' but you can change this tag!
            url = f"https://api.jamendo.com/v3.0/tracks/?client_id={client_id}&format=json&tags=lofi&limit=1"
            response = requests.get(url)
            data = response.json()
            
            if data.get('results'):
                audio_url = data['results'][0]['audio_download']
                music_data = requests.get(audio_url).content
                with open(music_path, "wb") as f:
                    f.write(music_data)
                logger.info("Successfully downloaded Jamendo track!")
            else:
                raise ValueError("No tracks found on Jamendo for that tag.")
        except Exception as e:
            logger.error("Jamendo failed, falling back: %s", e)
            tasks[task_id]["status"] = "FAILURE"
            tasks[task_id]["error"] = f"Music API failed: {e}"
            return
    else:
        tasks[task_id]["status"] = "FAILURE"
        tasks[task_id]["error"] = "JAMENDO_CLIENT_ID environment variable is missing."
        return
    # -----------------------------

    logger.info("Starting pipeline for %s (task %s)", fp, task_id)

    try:
        final_path = run_pipeline(
            raw_audio=str(fp),
            music_path=music_path,
            output_path=str(output_file),
            output_dir=str(output_dir),
            hf_token=os.environ.get("HF_AUTH_TOKEN"),
        )
        tasks[task_id]["status"] = "SUCCESS"
        tasks[task_id]["result_file"] = str(final_path)
        logger.info("Pipeline complete → %s (task %s)", final_path, task_id)
    except Exception as exc:
        logger.exception("Pipeline failed for %s (task %s)", fp, task_id)
        tasks[task_id]["status"] = "FAILURE"
        tasks[task_id]["error"] = str(exc)
