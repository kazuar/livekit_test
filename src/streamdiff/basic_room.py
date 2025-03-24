import asyncio
import logging
import json
from signal import SIGINT, SIGTERM
from typing import Union
import os
import numpy as np
import cv2

from livekit import api, rtc

# ensure LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET are set


async def main(room: rtc.Room) -> None:
    metadata = {
        "video_text": "Processed Feed"
    }

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
            video_source = rtc.VideoSource(width=1280, height=720)  # 720p resolution
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
                        
                        frame = frame_event.frame
                        width, height = frame.width, frame.height
                        frame_type = frame.type
                        data_size = len(frame.data)
                        logging.debug(f"Frame dimensions: {width}x{height}, data size: {data_size}")
                        
                        # Check if it's YUV420 format (1.5 bytes per pixel)
                        if data_size == (width * height * 3 // 2):
                            logging.debug("Detected YUV420 format")
                            frame_array = np.frombuffer(frame.data, dtype=np.uint8)
                            # Reshape for YUV420
                            yuv = frame_array.reshape((height * 3 // 2, width))
                            # Convert YUV420 to BGR
                            frame = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)
                        else:
                            logging.error(f"Unexpected data size: {data_size} bytes for {width}x{height} frame")
                            continue  # Skip this frame
                        
                        logging.debug(f"Frame shape after conversion: {frame.shape}")

                        # Apply more pronounced edge detection
                        edges = cv2.Canny(frame, 50, 150)  # Adjusted thresholds
                        edges = cv2.dilate(edges, None)  # Make edges thicker

                        # Create colored edge overlay with brighter color
                        colored_edges = np.zeros_like(frame)
                        colored_edges[edges > 0] = [0, 255, 0]  # Bright green edges
                        
                        # Add some visual effects
                        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
                        sharpened = cv2.addWeighted(frame, 1.5, blurred, -0.5, 0)
                        
                        # Blend original frame with edges more prominently
                        processed_frame = cv2.addWeighted(sharpened, 0.6, colored_edges, 0.4, 0)
                        
                        # Add text overlay to confirm processing
                        cv2.putText(
                            processed_frame,
                            metadata["video_text"],
                            (50, 50),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1,
                            (0, 255, 0),
                            2
                        )
                        
                        # Convert processed frame back to YUV420 format
                        if processed_frame.shape != (720, 1280, 3):
                            processed_frame = cv2.resize(processed_frame, (1280, 720))
                            logging.debug(f"Resized processed frame to 1280x720")
                        
                        # Convert RGB to YUV420
                        yuv420_frame = cv2.cvtColor(processed_frame, cv2.COLOR_RGB2YUV_I420)
                        
                        new_frame = rtc.VideoFrame(
                            data=yuv420_frame.tobytes(),
                            width=1280,
                            height=720,
                            type=frame_type
                        )
                        video_source.capture_frame(new_frame)
                except Exception as e:
                    logging.error("Error in echo_video: %s", e)
                    logging.exception("Full traceback:")  # This will log the full stack trace

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
