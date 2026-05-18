import librosa
import numpy as np


DEFAULT_HOP_LENGTH = 512
DEFAULT_FEATURE_FRAME_LENGTH = 2048
DEFAULT_FFT_NFFT = 1024

class AudioProcessor:
    def __init__(
        self,
        sr=22050,
        hop_length=DEFAULT_HOP_LENGTH,
        frame_length=DEFAULT_FEATURE_FRAME_LENGTH,
        fft_nfft=DEFAULT_FFT_NFFT,
    ):
        self.sr = sr  # Target sample rate
        self.hop_length = hop_length
        self.frame_length = frame_length
        self.fft_nfft = fft_nfft

    def _build_frame_metadata(self, frame_count, total_samples, sr):
        total_samples = max(0, int(total_samples))
        frame_indices = np.arange(frame_count, dtype=np.int32)
        center_samples = frame_indices * int(self.hop_length)
        half_window = int(self.frame_length) // 2
        start_samples = np.maximum(center_samples - half_window, 0)
        end_samples = np.minimum(center_samples + half_window, total_samples)

        return {
            "sample_rate": int(sr),
            "hop_length": int(self.hop_length),
            "frame_length": int(self.frame_length),
            "fft_nfft": int(self.fft_nfft),
            "frame_count": int(frame_count),
            "clip_duration_sec": float(total_samples / sr) if sr else 0.0,
            "frame_indices": frame_indices,
            "sample_starts": start_samples.astype(np.int64, copy=False),
            "sample_centers": center_samples.astype(np.int64, copy=False),
            "sample_ends": end_samples.astype(np.int64, copy=False),
            "time_starts_sec": start_samples.astype(np.float64, copy=False) / sr if sr else np.zeros(frame_count, dtype=np.float64),
            "time_centers_sec": center_samples.astype(np.float64, copy=False) / sr if sr else np.zeros(frame_count, dtype=np.float64),
            "time_ends_sec": end_samples.astype(np.float64, copy=False) / sr if sr else np.zeros(frame_count, dtype=np.float64),
        }

    def extract_features(self, file_path):
        """
        Loads an audio file and extracts:
        - UMAP input features (MFCCs + spectral centroid + spectral flux)
        - RMS volume per frame
        - Fundamental frequency (F0) per frame
        - FFT magnitude bins per frame
        """
        # 1. Load the audio file
        y, sr = librosa.load(file_path, sr=self.sr)

        # Keep frame alignment consistent across all frame-based features
        hop_length = self.hop_length

        # 2. Extract MFCCs (13 is a standard number for timbre)
        mfccs = librosa.feature.mfcc(
            y=y,
            sr=sr,
            n_mfcc=13,
            hop_length=hop_length,
            n_fft=self.frame_length,
        )

        # 3. Extract Spectral Centroid (Brightness)[cite: 1]
        spectral_centroid = librosa.feature.spectral_centroid(
            y=y,
            sr=sr,
            hop_length=hop_length,
            n_fft=self.frame_length,
        )

        # 4. Extract Spectral Flux (Rate of change)[cite: 1]
        # We calculate the onset envelope as a proxy for flux
        spectral_flux = librosa.onset.onset_strength(
            y=y,
            sr=sr,
            hop_length=hop_length,
            n_fft=self.frame_length,
        )
        spectral_flux = spectral_flux.reshape(1, -1) # Reshape for stacking

        # 4b. Extract raw FFT magnitude bins for the SpectroTerrain export
        fft_magnitude = np.abs(librosa.stft(y, n_fft=self.fft_nfft, hop_length=hop_length))
        fft_bins = fft_magnitude[:512, :]
        fft_bins = np.nan_to_num(fft_bins, nan=0.0, posinf=0.0, neginf=0.0)
        if fft_bins.size > 0:
            fft_bins = librosa.amplitude_to_db(fft_bins, ref=np.max)
            fft_bins = np.nan_to_num(fft_bins, nan=-80.0, posinf=0.0, neginf=-80.0)
            fft_min = float(np.min(fft_bins))
            fft_max = float(np.max(fft_bins))
            fft_range = (fft_max - fft_min) or 1.0
            fft_bins = ((fft_bins - fft_min) / fft_range) * 255.0

        # 5. Extract RMS volume and pitch (F0)
        rms = librosa.feature.rms(y=y, frame_length=self.frame_length, hop_length=hop_length).flatten()
        pitch = librosa.yin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
            frame_length=self.frame_length,
            hop_length=hop_length,
        )

        # 6. Align all feature streams to a shared frame count
        frame_count = min(
            mfccs.shape[1],
            spectral_centroid.shape[1],
            spectral_flux.shape[1],
            fft_bins.shape[1],
            rms.shape[0],
            pitch.shape[0],
        )

        mfccs = mfccs[:, :frame_count]
        spectral_centroid = spectral_centroid[:, :frame_count]
        spectral_flux = spectral_flux[:, :frame_count]
        fft_bins = fft_bins[:, :frame_count]
        rms = np.nan_to_num(rms[:frame_count], nan=0.0, posinf=0.0, neginf=0.0)
        pitch = np.nan_to_num(pitch[:frame_count], nan=0.0, posinf=0.0, neginf=0.0)
        frame_metadata = self._build_frame_metadata(frame_count, y.shape[0], sr)

        # 7. Combine only UMAP features into one high-dimensional vector
        # This creates a "feature map" where each column is a frame of time
        feature_vector = np.vstack((mfccs, spectral_centroid, spectral_flux))
        
        return feature_vector.T, rms, pitch, fft_bins.T, frame_metadata