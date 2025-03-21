import asyncio
import logging
import json
from signal import SIGINT, SIGTERM
from typing import Union
import os
import numpy as np
import cv2
from PIL import Image
from pathlib import Path

from livekit import api, rtc

from diffusers import AutoPipelineForImage2Image
from diffusers.utils import load_image
import torch

# ensure LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET are set

WIDTH = 1280
HEIGHT = 720

def test_pipeline_with_static_image(pipe, metadata):
    """Test the pipeline with a static image to verify it works correctly."""
    try:
        # Create a test directory if it doesn't exist
        test_dir = Path("test_images")
        test_dir.mkdir(exist_ok=True)
        
        # Create a simple test image (a red square)
        test_image = Image.new('RGB', (1024, 1024), color='red')
        test_image.save(test_dir / "test_input.png")

        logging.info("Testing pipeline with static image...")
        
        # Process the test image
        output = pipe(
            prompt="add a cat to the image",
            image=test_image.resize((512, 512)),
            num_inference_steps=3,
            strength=0.8,
            guidance_scale=0.0,
            output_type="pil"
        ).images[0]
    
        # Save the output
        output.save(test_dir / "test_output.png")
        logging.info("Successfully processed test image!")
        return True
        
    except Exception as e:
        logging.error(f"Error testing pipeline with static image: {str(e)}")
        logging.exception("Full traceback:")
        return False

async def main(room: rtc.Room) -> None:
    # Initialize the image to image pipeline
    pipe = AutoPipelineForImage2Image.from_pretrained(
        "stabilityai/sdxl-turbo",
        torch_dtype=torch.float16,
        variant="fp16",
        use_safetensors=True
    )
    pipe.to("cuda")

    # Enable memory optimization
    pipe.enable_model_cpu_offload()
    pipe.enable_vae_slicing()
    pipe.enable_attention_slicing()
    pipe.enable_vae_tiling()
    pipe.set_progress_bar_config(disable=True)

    # Set pipeline parameters
    pipe.safety_checker = None  # Disable safety checker for better performance
    pipe.requires_safety_checking = False

    metadata = {
        "video_text": "Turn the image into a cartoon",
        "strength": 0.45,
        "steps": 1,
        "guidance_scale": 0.0,
    }
    
    # Test the pipeline with a static image first
    # if not test_pipeline_with_static_image(pipe, metadata):
    #     logging.error("Pipeline test failed. Please check the logs for details.")
    #     return
    
    # return

    @room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant) -> None:
        logging.info("participant connected: %s %s", participant.sid, participant.identity)

    @room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant):
        logging.info("participant disconnected: %s %s", participant.sid, participant.identity)

    @room.on("local_track_published")
    def on_local_track_published(
        publication: rtc.LocalTrackPublication,
        track: Union[rtc.LocalAudioTrack, rtc.LocalVideoTrack],
    ):
        logging.info("local track published: %s", publication.sid)

    @room.on("active_speakers_changed")
    def on_active_speakers_changed(speakers: list[rtc.Participant]):
        logging.info("active speakers changed: %s", speakers)

    @room.on("local_track_unpublished")
    def on_local_track_unpublished(publication: rtc.LocalTrackPublication):
        logging.info("local track unpublished: %s", publication.sid)

    @room.on("track_published")
    def on_track_published(
        publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant
    ):
        logging.info(
            "track published: %s from participant %s (%s)",
            publication.sid,
            participant.sid,
            participant.identity,
        )

    @room.on("track_unpublished")
    def on_track_unpublished(
        publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant
    ):
        logging.info("track unpublished: %s", publication.sid)

    @room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        logging.info("track subscribed: %s", publication.sid)
        if track.kind == rtc.TrackKind.KIND_VIDEO:
            logging.info("Processing video track from %s", participant.identity)
            # Create a video source from the incoming track with standard resolution
            video_source = rtc.VideoSource(width=WIDTH, height=HEIGHT)
            video_track = rtc.LocalVideoTrack.create_video_track("echo", video_source)
            
            async def echo_video():
                logging.info("Starting echo_video")
                try:
                    video_stream = rtc.VideoStream(track)
                    frame_count = 0
                    async for frame_event in video_stream:
                        frame_count += 1
                        if frame_count % 30 == 0:  # Log every 30 frames
                            logging.info("Processed %d frames from %s", frame_count, participant.identity)
                        
                        # skip frames to reduce processing
                        if frame_count % 20 != 0:
                            continue
                        
                        frame = frame_event.frame
                        width, height = frame.width, frame.height
                        frame_type = frame.type
                        data_size = len(frame.data)
                        logging.debug(f"Frame dimensions: {width}x{height}, data size: {data_size}")

                        # Validate frame dimensions
                        if width <= 0 or height <= 0:
                            logging.error(f"Invalid frame dimensions: {width}x{height}")
                            continue
                        
                        # Check if it's YUV420 format (1.5 bytes per pixel)
                        if data_size == (width * height * 3 // 2):
                            logging.debug("Detected YUV420 format")
                            frame_array = np.frombuffer(frame.data, dtype=np.uint8)
                            logging.debug(f"Frame array shape: {frame_array.shape}, dtype: {frame_array.dtype}")
                            
                            # Reshape for YUV420
                            yuv = frame_array.reshape((height * 3 // 2, width))
                            logging.debug(f"YUV shape after reshape: {yuv.shape}")
                            
                            # Convert YUV420 to BGR using a different method
                            try:
                                # First convert to RGB
                                frame = cv2.cvtColor(yuv, cv2.COLOR_YUV2RGB_I420)
                                # Then convert RGB to BGR
                                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                                logging.debug(f"Frame shape after YUV conversion: {frame.shape}, dtype: {frame.dtype}")
                            except Exception as e:
                                logging.error(f"Error in YUV conversion: {str(e)}")
                                continue
                        else:
                            logging.error(f"Unexpected data size: {data_size} bytes for {width}x{height} frame")
                            continue  # Skip this frame

                        # Validate frame after conversion
                        if frame is None or frame.size == 0:
                            logging.error("Empty frame after conversion")
                            continue
                        
                        logging.debug(f"Frame shape after conversion: {frame.shape}, dtype: {frame.dtype}")
                        
                        # Convert BGR to RGB for PIL
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        logging.debug(f"Frame RGB shape: {frame_rgb.shape}, dtype: {frame_rgb.dtype}")
                        
                        try:
                            pil_image = Image.fromarray(frame_rgb)
                            if pil_image.size[0] == 0 or pil_image.size[1] == 0:
                                logging.error("Invalid PIL image dimensions")
                                continue
                                
                            # Log image debug before processing
                            logging.debug(f"PIL image size: {pil_image.size}, mode: {pil_image.mode}")
                            
                            # Ensure image is in RGB mode
                            if pil_image.mode != 'RGB':
                                pil_image = pil_image.convert('RGB')
                            
                            # Resize image if needed (SDXL expects specific dimensions)
                            target_size = (512, 512)  # SDXL's preferred size
                            if pil_image.size != target_size:
                                pil_image = pil_image.resize(target_size, Image.Resampling.LANCZOS)
                                logging.debug(f"Resized image to {target_size}")
                            
                            # Convert PIL image to numpy array and normalize
                            image_array = np.array(pil_image)
                            image_array = image_array.astype(np.float32) / 255.0
                            
                            # Ensure the image is in the correct format for the pipeline
                            if image_array.shape != (512, 512, 3):
                                logging.error(f"Invalid image shape after processing: {image_array.shape}")
                                continue
                                
                            logging.debug(f"Image array shape: {image_array.shape}, dtype: {image_array.dtype}")

                            # Convert numpy array to PIL Image
                            pil_image = Image.fromarray((image_array * 255).astype(np.uint8))
                            
                            # Process with pipeline
                            output = pipe(
                                prompt="surround the person with bubbles detailed, dramatic lighting shadow (lofi, analog-style)",
                                image=pil_image,
                                strength=0.7,
                                num_inference_steps=2,
                                guidance_scale=10.0,
                                output_type="pil",
                            ).images[0]
                            
                            # Convert back to numpy array
                            processed_frame = np.array(output)
                            
                            # Validate processed frame
                            if processed_frame is None or processed_frame.size == 0:
                                logging.error("Empty processed frame")
                                continue
                                
                            # Convert RGB to BGR for OpenCV
                            processed_frame = cv2.cvtColor(processed_frame, cv2.COLOR_RGB2BGR)
                        
                        except Exception as e:
                            logging.error(f"Error processing frame: {str(e)}")
                            continue

                        # Convert processed frame back to YUV420 format
                        if processed_frame.shape != (HEIGHT, WIDTH, 3):
                            processed_frame = cv2.resize(processed_frame, (WIDTH, HEIGHT))
                            logging.debug(f"Resized processed frame to {WIDTH}x{HEIGHT}")
                        
                        # Convert BGR to YUV420 (since processed_frame is in BGR format)
                        yuv420_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2YUV_I420)
                        
                        # Ensure the YUV420 frame is in the correct format
                        if yuv420_frame.shape != (HEIGHT * 3 // 2, WIDTH):  # 360 * 3/2 = 540 for YUV420
                            logging.error(f"Invalid YUV420 frame shape: {yuv420_frame.shape}")
                            continue
                            
                        new_frame = rtc.VideoFrame(
                            data=yuv420_frame.tobytes(),
                            width=WIDTH,
                            height=HEIGHT,
                            type=frame_type
                        )
                        video_source.capture_frame(new_frame)
                except Exception as e:
                    logging.error("Error in echo_video: %s", e)
                    logging.exception("Full traceback:")  # This will log the full stack trace
                    raise

            logging.info("Starting echo task for %s", participant.identity)
            asyncio.create_task(echo_video())
            
            logging.info("Publishing echo track for %s", participant.identity)
            asyncio.create_task(
                room.local_participant.publish_track(
                    video_track,
                    options=rtc.TrackPublishOptions(
                        video_codec=rtc.VideoCodec.AV1,
                        simulcast=False
                    )
                )
            )

        elif track.kind == rtc.TrackKind.KIND_AUDIO:
            print("Subscribed to an Audio Track")
            _audio_stream = rtc.AudioStream(track)
            # audio_stream is an async iterator that yields AudioFrame

    @room.on("track_unsubscribed")
    def on_track_unsubscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        logging.info("track unsubscribed: %s", publication.sid)

    @room.on("track_muted")
    def on_track_muted(publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        logging.info("track muted: %s", publication.sid)

    @room.on("track_unmuted")
    def on_track_unmuted(
        publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant
    ):
        logging.info("track unmuted: %s", publication.sid)

    @room.on("data_received")
    def on_data_received(data: rtc.DataPacket):
        logging.info("received data from %s: %s", data.participant.identity, data.data)
        json_data = json.loads(data.data)        
        video_text = json_data.get('prompt', 'Processed Feed')
        logging.info("video text: %s", video_text)
        metadata["video_text"] = video_text
    @room.on("connection_quality_changed")
    def on_connection_quality_changed(participant: rtc.Participant, quality: rtc.ConnectionQuality):
        logging.info("connection quality changed for %s", participant.identity)

    @room.on("track_subscription_failed")
    def on_track_subscription_failed(
        participant: rtc.RemoteParticipant, track_sid: str, error: str
    ):
        logging.info("track subscription failed: %s %s", participant.identity, error)

    @room.on("connection_state_changed")
    def on_connection_state_changed(state: rtc.ConnectionState):
        logging.info("connection state changed: %s", state)

    @room.on("connected")
    def on_connected() -> None:
        logging.info("connected")

    @room.on("disconnected")
    def on_disconnected() -> None:
        logging.info("disconnected")

    @room.on("reconnecting")
    def on_reconnecting() -> None:
        logging.info("reconnecting")

    @room.on("reconnected")
    def on_reconnected() -> None:
        logging.info("reconnected")

    token = (
        api.AccessToken()
        .with_identity("python-bot")
        .with_name("Python Bot")
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room="test_room",
            )
        )
        .to_jwt()
    )
    await room.connect(os.getenv("LIVEKIT_URL"), token)
    logging.info("connected to room %s", room.name)
    logging.info("participants: %s", room.remote_participants)

    await asyncio.sleep(2)
    await room.local_participant.publish_data("hello world")
    # print all participants
    logging.info("participants: %s", room.remote_participants)

    # get participant video track
    # participant = room.remote_participants['test_user']
    # remote_track_publication = [x for x in participant.track_publications if x.kind == rtc.TrackKind.KIND_VIDEO]
    # video_track = remote_track_publication[0].track

    # # subscribe to video track
    # await room.local_participant.subscribe(video_track)

    # video_track = participant.track_publications
    # logging.info("participant: %s", participant)
    # breakpoint()
    # logging.info("participant: %s", participant.tracks)
    # video_track = participant.tracks[0]
    # logging.info("video track: %s", video_track)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        handlers=[logging.FileHandler("basic_room.log"), logging.StreamHandler()],
    )

    loop = asyncio.get_event_loop()
    room = rtc.Room(loop=loop)

    async def cleanup():
        await room.disconnect()
        loop.stop()

    asyncio.ensure_future(main(room))
    for signal in [SIGINT, SIGTERM]:
        loop.add_signal_handler(signal, lambda: asyncio.ensure_future(cleanup()))

    try:
        loop.run_forever()
    finally:
        loop.close()
