# Livekit with video processor

This project implements a real-time video processing pipeline using WebRTC, Livekit, and OpenCV. It allows for live video streaming with real-time edge detection and visual effects processing.

## Architecture

The system consists of three main components:
1. **Client** - Web interface for video capture and display
2. **Livekit** - WebRTC server handling video streaming
3. **Video Processor** - Python service that applies real-time video effects

### Flow:
1. Browser captures webcam feed and sends it to Livekit
2. Livekit forwards the video stream to the video processor via RTP
3. Video processor applies effects and sends processed stream back to Livekit
4. Livekit delivers the processed stream back to the browser

## Setup

1. Clone the repository:
```bash
git clone https://github.com/kazuar/livekit_test.git
cd livekit_test
```

2. Install dependencies:
```bash
uv sync
```

3. Run the livekit server:
```bash
docker run --rm -p 7880:7880 \
    -e LIVEKIT_KEYS="devkey: secret" \
    livekit/livekit-server
```

4. Run the video processor:
```bash
uv run python src/server/basic_room.py
```

5. Create access token to connect to livekit:
```bash
lk token create \
  --api-key devkey --api-secret secret \
  --join --room test_room --identity test_user \
  --valid-for 24h
```

6. Update the access token in the client in `src/client/src/app.js`

7. Run the client:
```bash
cd src/client
npm install
npm run dev
```

8. Open your browser and navigate to `http://localhost:5173` to access the video processing interface.

## Notes

* Tested only on Macbook Pro with laptop camera and chrome browser.
