import {
    Room,
    RoomEvent,
    LocalTrack,
    createLocalTracks,
    createLocalVideoTrack,
    DataPacket_Kind
} from 'livekit-client';

// LiveKit server URL - adjust if your server runs on a different port
const LIVEKIT_URL = 'ws://localhost:7880';

// For demo purposes - you would typically create this token on your server
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NDI0MTU3NzUsImlzcyI6ImRldmtleSIsIm5hbWUiOiJ0ZXN0X3VzZXIiLCJuYmYiOjE3NDIzMjkzNzUsInN1YiI6InRlc3RfdXNlciIsInZpZGVvIjp7InJvb20iOiJ0ZXN0X3Jvb20iLCJyb29tSm9pbiI6dHJ1ZX19.F7dI4GrX72jvfJhJC6NrFGOzSrlm1pClI4lwjQ7I07o';

class VideoChat {
    constructor() {
        this.room = new Room({
            videoCaptureDefaults: {
                deviceId: 'default',
                facingMode: 'user',
                resolution: {
                    width: 1280,
                    height: 720,
                    frameRate: 30,
                },
            },
            publishDefaults: {
                videoEncoding: {
                  maxBitrate: 1_500_000,
                  maxFramerate: 30,
                },
                videoSimulcastLayers: [
                  {
                    width: 640,
                    height: 360,
                    encoding: {
                      maxBitrate: 500_000,
                      maxFramerate: 20,
                    },
                  },
                  {
                    width: 320,
                    height: 180,
                    encoding: {
                      maxBitrate: 150_000,
                      maxFramerate: 15,
                    },
                  },
                ],
            },
        });
        console.log(this.room.name);
        this.localVideo = document.getElementById('local-video');
        this.remoteVideo = document.getElementById('processed-video');
        this.startButton = document.getElementById('startButton');
        
        this.startButton.addEventListener('click', () => this.startStream());
        
        // Set up room event listeners
        this.room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
            console.log('Track subscribed:', {
                kind: track.kind,
                participant: participant.identity,
                trackSid: publication.trackSid,
                source: publication.source
            });
            if (track.kind === 'video') {
                track.attach(this.remoteVideo);
                console.log('Attached remote video track', track);
                
                // Add codec info display
                const codecEl = document.getElementById('processed-codec');
                console.log('publication', publication);
                const codec = publication.mimeType;
                if (codec) {
                    codecEl.textContent = `Codec: ${codec}`;
                }
            }
        });
        
        this.room.on(RoomEvent.TrackUnsubscribed, (track, publication, participant) => {
            console.log('Track unsubscribed:', track.kind);
            track.detach();
        });

        // Add more event listeners for debugging
        this.room.on(RoomEvent.ParticipantConnected, (participant) => {
            console.log('Participant connected:', participant.identity);
        });

        this.room.on(RoomEvent.ParticipantDisconnected, (participant) => {
            console.log('Participant disconnected:', participant.identity);
        });

        // Add prompt functionality
        this.promptInput = document.getElementById('promptInput');
        this.sendPromptButton = document.getElementById('sendPrompt');
        
        this.sendPromptButton.addEventListener('click', () => this.sendPrompt());
        this.promptInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                this.sendPrompt();
            }
        });
    }

    async startStream() {
        try {
            // Disable the start button while connecting
            this.startButton.disabled = true;
            
            // Get local camera track
            const track = await createLocalVideoTrack({
                deviceId: 'default',
                facingMode: 'user',
                resolution: {
                    width: 1280,
                    height: 720,
                    frameRate: 30,
                },
            });

            // Connect to the LiveKit room
            await this.room.connect(LIVEKIT_URL, TOKEN);
            console.log('Connected to room:', this.room.name);

            // Publish tracks one by one
            await this.room.localParticipant.publishTrack(
                track,
                    {
                        videoCodec: 'av1',
                        simulcast: false  // Optional: enable simulcast if needed
                    }
            );

            // Attach local video
            track.attach(this.localVideo);
            console.log('Attached local video track', track);
            
            // Add codec info for local video
            const localCodecEl = document.getElementById('local-codec');
            const codec = track.codec || 'detecting...';
            localCodecEl.textContent = `Codec: ${codec}`;
            
            // Update codec info when it becomes available
            track.on('codecChanged', (codec) => {
                localCodecEl.textContent = `Codec: ${codec}`;
            });

            // Log height and width
            console.log('Local video track height:', track.height);
            console.log('Local video track width:', track.width);

        } catch (error) {
            console.error('Error starting stream:', error);
            this.startButton.disabled = false;
        }
    }

    sendPrompt() {
        const prompt = this.promptInput.value.trim();
        if (!prompt || !this.room.localParticipant) return;

        const data = JSON.stringify({prompt: prompt})
        console.log('Sending prompt:', data);
        const encodedData = new TextEncoder().encode(data);
        console.log('Encoded data:', encodedData);

        this.room.localParticipant.publishData(
            encodedData,
            DataPacket_Kind.RELIABLE,
            {
                destinationIdentities: ['python-bot']
            }
        );
        
        this.promptInput.value = '';
    }
}

// Initialize the video chat when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new VideoChat();
}); 