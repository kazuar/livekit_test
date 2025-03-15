import {
    Room,
    RoomEvent,
    LocalTrack,
    createLocalTracks,
} from 'livekit-client';

// LiveKit server URL - adjust if your server runs on a different port
const LIVEKIT_URL = 'ws://localhost:7880';

// For demo purposes - you would typically create this token on your server
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NDIxNDY2NzEsImlzcyI6ImRldmtleSIsIm5hbWUiOiJ0ZXN0X3VzZXIiLCJuYmYiOjE3NDIwNjAyNzEsInN1YiI6InRlc3RfdXNlciIsInZpZGVvIjp7InJvb20iOiJ0ZXN0X3Jvb20iLCJyb29tSm9pbiI6dHJ1ZX19.7-RIRzgXNHxeKyOnK1QSCyiu8y4HmnqaFPxflnMUnlY';

class VideoChat {
    constructor() {
        this.room = new Room();
        console.log(this.room.name);
        this.localVideo = document.getElementById('localVideo');
        this.remoteVideo = document.getElementById('remoteVideo');
        this.startButton = document.getElementById('startButton');
        
        this.startButton.addEventListener('click', () => this.startStream());
        
        // Set up room event listeners
        this.room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
            console.log('Track subscribed:', track.kind, 'from participant:', participant.identity);
            if (track.kind === 'video') {
                track.attach(this.remoteVideo);
                console.log('Attached remote video track');
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
    }

    async startStream() {
        try {
            // Disable the start button while connecting
            this.startButton.disabled = true;
            
            // Get local camera track
            const tracks = await createLocalTracks({
                audio: true,
                video: true
            });

            // Connect to the LiveKit room
            await this.room.connect(LIVEKIT_URL, TOKEN);
            console.log('Connected to room:', this.room.name);

            // Publish tracks one by one
            for (const track of tracks) {
                await this.room.localParticipant.publishTrack(track);
            }

            // Attach local video
            const videoTrack = tracks.find(track => track.kind === 'video');
            if (videoTrack) {
                videoTrack.attach(this.localVideo);
            }

        } catch (error) {
            console.error('Error starting stream:', error);
            this.startButton.disabled = false;
        }
    }
}

// Initialize the video chat when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new VideoChat();
}); 