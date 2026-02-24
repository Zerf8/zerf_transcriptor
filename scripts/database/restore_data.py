import json
import os
from src.models import Video, Transcription, Clip, get_engine
from sqlalchemy.orm import sessionmaker

STATE_FILE = r"c:\proyectos\Zerf_Transcriptor\data\processing_state.json"

def restore():
    if not os.path.exists(STATE_FILE):
        print("❌ No processing_state.json found")
        return

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        processed_list = data.get('videos_procesados', [])
        print(f"📂 Found {len(processed_list)} processed videos in state file.")
        
        engine = get_engine()
        Session = sessionmaker(bind=engine)
        session = Session()
        
        count_t = 0
        count_c = 0
        
        for item in processed_list:
            try:
                url = item.get('url', '')
                if "v=" not in url and "youtu.be" not in url: continue
                
                # Extract ID
                if "v=" in url:
                    yid = url.split("v=")[1].split("&")[0]
                else:
                    yid = url.split("youtu.be/")[1].split("?")[0]
                    
                # Find Video in DB
                video = session.query(Video).filter_by(youtube_id=yid).first()
                if not video:
                    print(f"⚠️ Video {yid} not found in DB. Skipping.")
                    continue
                    
                meta = item.get('metadata', {})
                srt_path = meta.get('srt_path')

                if not srt_path:
                    print(f"⚠️ SRT path missing for {yid}")
                    continue
                    
                # Derived paths
                base_name = os.path.splitext(os.path.basename(srt_path))[0]
                if base_name.endswith('_yt'):
                    base_name = base_name[:-3] # Remove _yt
                
                # Check srt existence for transcription only
                srt_exists = os.path.exists(srt_path)
                if not srt_exists:
                    # Try finding it in subfolders if missing
                    if os.path.exists(os.path.join(os.path.dirname(srt_path), "youtube", os.path.basename(srt_path))):
                         srt_path = os.path.join(os.path.dirname(srt_path), "youtube", os.path.basename(srt_path))
                         srt_exists = True
                if base_name.endswith('_yt'):
                    base_name = base_name[:-3] # Remove _yt
                
                raw_path = os.path.join(os.path.dirname(srt_path), base_name + '_raw.json')
                if not os.path.exists(raw_path):
                     # Try with _large_v3_raw.json or similar if needed, or just standard
                     raw_path = os.path.join(os.path.dirname(srt_path), base_name + '_large_v3_raw.json')

                # Clips are in output/clips, not output/transcripciones
                clips_path = os.path.join(r"c:\proyectos\Zerf_Transcriptor\output\clips", base_name + '_clips.json')
                
                # Fallback for old name format or AI clips
                if not os.path.exists(clips_path):
                     # DEBUG
                     # print(f"Checking AI path for {base_name}...")
                     clips_path = os.path.join(r"c:\proyectos\Zerf_Transcriptor\output\clips", base_name + '_clips_ai.json')

                if os.path.exists(clips_path):
                    print(f"✅ Clips found: {clips_path}")
                else:
                    print(f"❌ Clips NOT found: {clips_path}")
                
                # 1. Restore Transcription
                # Check if exists to avoid dupes (though DB truncate cleared them)
                existing_t = session.query(Transcription).filter_by(video_id=video.id).first()
                if not existing_t:
                    # Only attempt to read SRT if it exists
                    if srt_exists:
                        srt_content = ""
                        with open(srt_path, "r", encoding="utf-8") as f:
                            srt_content = f.read()
                        
                        raw_content = ""
                        whisper_text = ""
                        language = "es"
                        
                        if os.path.exists(raw_path):
                            with open(raw_path, "r", encoding="utf-8") as f:
                                raw_content = f.read()
                                try:
                                    raw_json = json.loads(raw_content)
                                    whisper_text = raw_json.get('text', '')
                                    language = raw_json.get('language', 'es')
                                except:
                                    pass
                                    
                        t = Transcription(
                            video_id=video.id,
                            whisper_text=whisper_text,
                            gemini_text=None,
                            srt_content=srt_content,
                            raw_json=raw_content,
                            language=language
                        )
                        session.add(t)
                        count_t += 1
                        
                        # Update Video status
                        video.status = 'completed'
                    else:
                         print(f"⏩ Skipping transcription restore for {yid} (SRT missing)")
                
                # 2. Restore Clips
                if os.path.exists(clips_path):
                    # Clear existing clips for this video just in case
                    session.query(Clip).filter_by(video_id=video.id).delete()
                    
                    with open(clips_path, "r", encoding="utf-8") as f:
                        clips_data = json.load(f)
                        
                    if isinstance(clips_data, dict):
                        if 'clips' in clips_data:
                            clips_list = clips_data['clips']
                        elif 'suggested_clips' in clips_data:
                            clips_list = clips_data['suggested_clips']
                        else:
                            clips_list = []
                    elif isinstance(clips_data, list):
                        clips_list = clips_data
                    else:
                        clips_list = []
                        
                    for c in clips_list:
                        clip = Clip(
                            video_id=video.id,
                            start_time=c.get('start_time'),
                            end_time=c.get('end_time'),
                            start_seconds=c.get('start_seconds'),
                            end_seconds=c.get('end_seconds'),
                            text_preview=c.get('text_preview', c.get('title', '')),
                            score=c.get('score', 0),
                            reason=c.get('reason', ''),
                            tags=json.dumps(c.get('tags', [])),
                            source='ai'
                        )
                        session.add(clip)
                        count_c += 1
                        # print(f"  + Added clip: {c.get('title', 'No Title')}")
                    
                    # Commit per video to ensure persistence
                    try:
                        session.commit()
                        print(f"  ✅ Committed {len(clips_list)} clips for video {yid}")
                    except Exception as e_commit:
                        session.rollback()
                        print(f"  ❌ Failed to commit clips for {yid}: {e_commit}")
                        
            except Exception as e_inner:
                print(f"❌ Error processing {yid}: {e_inner}")

        print(f"✅ Recovery Complete: {count_t} transcriptions, {count_c} clips restored.")
        session.close()

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Critical Error: {e}")

if __name__ == "__main__":
    restore()
