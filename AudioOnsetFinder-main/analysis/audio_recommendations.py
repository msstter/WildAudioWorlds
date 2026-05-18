"""Shared audio-analysis recommendations used by GUI and script surfaces."""

import os

import librosa
import numpy as np


def estimate_noise_floor(y, sr, frame_length=2048, hop_length=512, percentile=10):
    """Estimate the noise floor as the *percentile*-th frame RMS (dBFS)."""
    rms = librosa.feature.rms(
        y=y,
        frame_length=frame_length,
        hop_length=hop_length,
    )[0]
    rms = rms[rms > 0]
    if len(rms) == 0:
        return -80.0
    noise_rms = float(np.percentile(rms, percentile))
    return float(20 * np.log10(max(noise_rms, 1e-10)))


def estimate_snr(y, sr, frame_length=2048, hop_length=512):
    """Estimate signal-to-noise ratio in dB."""
    rms = librosa.feature.rms(
        y=y,
        frame_length=frame_length,
        hop_length=hop_length,
    )[0]
    rms = rms[rms > 0]
    if len(rms) < 10:
        return 20.0

    signal_rms = float(np.percentile(rms, 90))
    noise_rms = float(np.percentile(rms, 10))
    if noise_rms < 1e-10:
        return 60.0
    return float(20 * np.log10(signal_rms / noise_rms))


def spectral_profile(y, sr, n_fft=2048, hop_length=512):
    """Compute spectral statistics across the recording."""
    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop_length))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    mean_power = np.mean(S ** 2, axis=1)
    total_power = np.sum(mean_power)

    if total_power < 1e-10:
        return {
            "dominant_freq_hz": 0,
            "spectral_centroid_hz": 0,
            "spectral_bandwidth_hz": 0,
            "energy_below_200hz": 0,
            "energy_200_2000hz": 0,
            "energy_2000_8000hz": 0,
            "energy_above_8000hz": 0,
        }

    dominant_idx = np.argmax(mean_power)
    dominant_freq = float(freqs[dominant_idx])

    centroid = float(np.sum(freqs * mean_power) / total_power)
    variance = np.sum(mean_power * (freqs - centroid) ** 2) / total_power
    bandwidth = float(np.sqrt(max(variance, 0)))

    def band_energy(f_low, f_high):
        mask = (freqs >= f_low) & (freqs < f_high)
        return float(np.sum(mean_power[mask]) / total_power)

    return {
        "dominant_freq_hz": round(dominant_freq, 1),
        "spectral_centroid_hz": round(centroid, 1),
        "spectral_bandwidth_hz": round(bandwidth, 1),
        "energy_below_200hz": round(band_energy(0, 200), 4),
        "energy_200_2000hz": round(band_energy(200, 2000), 4),
        "energy_2000_8000hz": round(band_energy(2000, 8000), 4),
        "energy_above_8000hz": round(band_energy(8000, sr / 2), 4),
    }


def harmonic_percussive_ratio(y, sr):
    """Compute the ratio of harmonic to percussive energy."""
    S = np.abs(librosa.stft(y))
    H, P = librosa.decompose.hpss(S)
    h_energy = float(np.sum(H ** 2))
    p_energy = float(np.sum(P ** 2))
    total = h_energy + p_energy
    if total < 1e-10:
        return 0.5, 0.5
    return round(h_energy / total, 4), round(p_energy / total, 4)


def measure_dynamic_range(y, sr, frame_length=2048, hop_length=512):
    """Measure the dynamic range of the recording in dB."""
    rms = librosa.feature.rms(
        y=y,
        frame_length=frame_length,
        hop_length=hop_length,
    )[0]
    rms = rms[rms > 0]
    if len(rms) < 2:
        return 0.0
    peak_db = float(20 * np.log10(np.max(rms)))
    floor_db = float(20 * np.log10(np.percentile(rms, 5)))
    return round(peak_db - floor_db, 1)


def detect_tonal_noise(y, sr, n_fft=4096):
    """Detect persistent tonal components that could be notch-filtered."""
    S = np.abs(librosa.stft(y, n_fft=n_fft))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    mean_power = np.mean(S ** 2, axis=1)
    std_power = np.std(S ** 2, axis=1)

    if np.max(mean_power) < 1e-10:
        return []

    prominence = mean_power / (std_power + 1e-10)
    median_prominence = np.median(prominence)

    tonal_freqs = []
    for i, (freq_hz, prominence_value, mean_value) in enumerate(
        zip(freqs, prominence, mean_power)
    ):
        if freq_hz < 30 or freq_hz > sr / 2 - 100:
            continue
        if (
            prominence_value > median_prominence * 5
            and mean_value > np.median(mean_power) * 3
        ):
            neighbors = slice(max(0, i - 3), min(len(mean_power), i + 4))
            if mean_power[i] > np.mean(mean_power[neighbors]) * 1.5:
                tonal_freqs.append(round(float(freq_hz), 1))

    if not tonal_freqs:
        return []

    merged = [tonal_freqs[0]]
    for freq_hz in tonal_freqs[1:]:
        if freq_hz - merged[-1] > 10:
            merged.append(freq_hz)
    return merged[:5]


def estimate_noise_stationarity(y, sr, frame_length=2048, hop_length=512):
    """Measure how stationary the background noise is (0=varying, 1=constant)."""
    S = np.abs(librosa.stft(y, n_fft=frame_length, hop_length=hop_length))

    frame_energy = np.sum(S ** 2, axis=0)
    noise_threshold = np.percentile(frame_energy, 25)
    noise_frames = S[:, frame_energy <= noise_threshold]

    if noise_frames.shape[1] < 5:
        return 0.5

    mean_spectrum = np.mean(noise_frames, axis=1)
    per_frame_diff = np.mean(np.abs(noise_frames - mean_spectrum[:, None]), axis=0)
    avg_diff = float(np.mean(per_frame_diff))
    avg_level = float(np.mean(mean_spectrum))

    if avg_level < 1e-10:
        return 0.5

    variation_ratio = avg_diff / avg_level
    stationarity = max(0.0, min(1.0, 1.0 - variation_ratio))
    return round(stationarity, 3)


def analyze_audio(audio_path, signal_profile=None, sr=None):
    """Analyze an audio file and recommend Audio Editor settings."""
    y, file_sr = librosa.load(audio_path, sr=sr, mono=True)

    noise_floor_db = estimate_noise_floor(y, file_sr)
    snr = estimate_snr(y, file_sr)
    spec = spectral_profile(y, file_sr)
    h_ratio, p_ratio = harmonic_percussive_ratio(y, file_sr)
    dynamic_range = measure_dynamic_range(y, file_sr)
    tonal_noise = detect_tonal_noise(y, file_sr)
    stationarity = estimate_noise_stationarity(y, file_sr)
    peak_db = float(20 * np.log10(max(np.max(np.abs(y)), 1e-10)))

    analysis = {
        "file": os.path.basename(audio_path),
        "sample_rate": file_sr,
        "duration_s": round(len(y) / file_sr, 2),
        "peak_db": round(peak_db, 1),
        "noise_floor_db": round(noise_floor_db, 1),
        "snr_db": round(snr, 1),
        "dynamic_range_db": round(dynamic_range, 1),
        "spectral": spec,
        "harmonic_ratio": h_ratio,
        "percussive_ratio": p_ratio,
        "tonal_noise_freqs": tonal_noise,
        "noise_stationarity": stationarity,
    }

    settings = {}
    reasoning = {}

    has_profile = (
        signal_profile is not None
        and "summary" in signal_profile
        and signal_profile["summary"].get("n_regions", 0) > 0
    )
    has_neg_profile = (
        signal_profile is not None
        and "negative_summary" in signal_profile
        and signal_profile["negative_summary"].get("n_regions", 0) > 0
    )

    if has_profile:
        sp = signal_profile["summary"]
        sig_f_low = sp["freq_range_hz"][0]
        sig_f_high = sp["freq_range_hz"][1]
        sig_character = sp["signal_character"]
        sig_harmonicity = sp["harmonicity"]
        sig_bandwidth = sp["spectral_bandwidth_hz"]
        sig_sharpness = sp["attack_sharpness"]
    else:
        sig_f_low = None
        sig_f_high = None
        sig_character = (
            "percussive"
            if p_ratio > 0.55
            else ("harmonic" if h_ratio > 0.55 else "mixed")
        )
        sig_harmonicity = h_ratio
        sig_bandwidth = spec["spectral_bandwidth_hz"]
        sig_sharpness = 0

    if has_neg_profile:
        nsp = signal_profile["negative_summary"]
        neg_f_low = nsp["freq_range_hz"][0]
        neg_f_high = nsp["freq_range_hz"][1]
        neg_character = nsp["signal_character"]
        neg_harmonicity = nsp["harmonicity"]
    else:
        neg_f_low = None
        neg_f_high = None
        neg_character = None
        neg_harmonicity = None

    if has_profile:
        margin = max(50, sig_f_low * 0.3)
        hp = max(20, int(sig_f_low - margin))
        if has_neg_profile and neg_f_high is not None and neg_f_high < sig_f_low:
            hp = max(hp, int(round(neg_f_high / 10) * 10))
            hp = min(hp, max(20, int(sig_f_low - 30)))
            reasoning["MUTER_HIGHPASS_HZ"] = (
                f"{hp} Hz — raised to suppress unwanted sound below "
                f"{neg_f_high:.0f} Hz while preserving signal at {sig_f_low:.0f} Hz"
            )
        else:
            hp = int(round(hp / 10) * 10)
            reasoning["MUTER_HIGHPASS_HZ"] = (
                f"{hp} Hz — signal starts at {sig_f_low:.0f} Hz; "
                f"30% margin below preserves all signal energy"
            )
    else:
        if spec["energy_below_200hz"] < 0.05:
            hp = 200
            reasoning["MUTER_HIGHPASS_HZ"] = (
                "200 Hz — very little energy below 200 Hz "
                f"({spec['energy_below_200hz'] * 100:.1f}%); safe to remove"
            )
        elif spec["energy_below_200hz"] < 0.15:
            hp = 100
            reasoning["MUTER_HIGHPASS_HZ"] = (
                "100 Hz — some low-frequency content present; "
                "moderate cut to preserve potential bass signals"
            )
        else:
            hp = 60
            reasoning["MUTER_HIGHPASS_HZ"] = (
                "60 Hz — significant low-frequency energy; "
                "minimal cut to preserve bass content"
            )
    settings["MUTER_HIGHPASS_HZ"] = hp

    if has_profile and sig_f_high < file_sr / 2 - 500:
        margin = max(500, sig_f_high * 0.3)
        lp = min(int(file_sr / 2 - 100), int(sig_f_high + margin))
        if has_neg_profile and neg_f_low is not None and neg_f_low > sig_f_high:
            lp = min(lp, int(round(neg_f_low / 100) * 100))
            lp = max(lp, int(sig_f_high + 100))
            reasoning["MUTER_LOWPASS_HZ"] = (
                f"{lp} Hz — lowered to suppress unwanted sound above "
                f"{neg_f_low:.0f} Hz while preserving signal up to {sig_f_high:.0f} Hz"
            )
        else:
            lp = int(round(lp / 100) * 100)
            reasoning["MUTER_LOWPASS_HZ"] = (
                f"{lp} Hz — signal peaks at {sig_f_high:.0f} Hz; "
                f"30% margin above captures harmonics while cutting interference"
            )
        settings["MUTER_LOWPASS_HZ"] = lp
    elif spec["energy_above_8000hz"] > 0.15:
        settings["MUTER_LOWPASS_HZ"] = 0
        reasoning["MUTER_LOWPASS_HZ"] = (
            f"Disabled — substantial energy above 8 kHz "
            f"({spec['energy_above_8000hz'] * 100:.1f}%); preserving high-frequency detail"
        )
    elif spec["energy_above_8000hz"] < 0.02:
        settings["MUTER_LOWPASS_HZ"] = 8000
        reasoning["MUTER_LOWPASS_HZ"] = (
            f"8000 Hz — almost no energy above 8 kHz "
            f"({spec['energy_above_8000hz'] * 100:.1f}%); useful noise reduction"
        )
    else:
        settings["MUTER_LOWPASS_HZ"] = 0
        reasoning["MUTER_LOWPASS_HZ"] = (
            "Disabled — no clear benefit from cutting high frequencies"
        )

    neg_reinforces_hpss = (
        has_neg_profile
        and has_profile
        and neg_character is not None
        and sig_character != "mixed"
        and neg_character != "mixed"
        and sig_character != neg_character
    )

    hp_diff = abs(h_ratio - p_ratio)
    if neg_reinforces_hpss or hp_diff > 0.2:
        settings["MUTER_HPSS_ENABLED"] = True
        if sig_character == "harmonic":
            settings["MUTER_HPSS_TARGET"] = "harmonic"
            reasoning["MUTER_HPSS_TARGET"] = (
                f"Harmonic — signal is predominantly tonal "
                f"(H/P ratio: {h_ratio:.2f}/{p_ratio:.2f})"
            )
        else:
            settings["MUTER_HPSS_TARGET"] = "percussive"
            reasoning["MUTER_HPSS_TARGET"] = (
                f"Percussive — signal has strong transient character "
                f"(H/P ratio: {h_ratio:.2f}/{p_ratio:.2f})"
            )
        if neg_reinforces_hpss:
            settings["MUTER_HPSS_MARGIN"] = 3.0
            reasoning["MUTER_HPSS_MARGIN"] = (
                f"3.0 — negative profile is {neg_character}, target is "
                f"{sig_character}; aggressive HPSS cleanly separates them"
            )
        elif hp_diff > 0.4:
            settings["MUTER_HPSS_MARGIN"] = 3.0
            reasoning["MUTER_HPSS_MARGIN"] = (
                "3.0 — strong H/P separation; hard split for clean isolation"
            )
        else:
            settings["MUTER_HPSS_MARGIN"] = 2.0
            reasoning["MUTER_HPSS_MARGIN"] = (
                "2.0 — moderate H/P difference; softer split to avoid signal loss"
            )
        if neg_reinforces_hpss:
            reasoning["MUTER_HPSS_ENABLED"] = (
                f"Enabled — target sound is {sig_character} while unwanted "
                f"sound is {neg_character}; HPSS will separate effectively"
            )
        else:
            reasoning["MUTER_HPSS_ENABLED"] = (
                f"Enabled — clear harmonic/percussive separation "
                f"(H: {h_ratio:.0%}, P: {p_ratio:.0%})"
            )
        settings["MUTER_HPSS_EMPHASIS_DB"] = 0
    else:
        settings["MUTER_HPSS_ENABLED"] = False
        settings["MUTER_HPSS_TARGET"] = "percussive"
        settings["MUTER_HPSS_MARGIN"] = 2.0
        settings["MUTER_HPSS_EMPHASIS_DB"] = 0
        reasoning["MUTER_HPSS_ENABLED"] = (
            f"Disabled — harmonic and percussive energy are balanced "
            f"(H: {h_ratio:.0%}, P: {p_ratio:.0%}); separation would lose signal"
        )

    if stationarity > 0.5 and snr < 30:
        settings["MUTER_SPECTRAL_DENOISE"] = True
        if stationarity > 0.7:
            strength = 2.0 if snr < 15 else 1.5
        else:
            strength = 1.0
        settings["MUTER_DENOISE_STRENGTH"] = strength
        reasoning["MUTER_SPECTRAL_DENOISE"] = (
            f"Enabled — noise is stationary ({stationarity:.0%} stable), "
            f"SNR is moderate ({snr:.0f} dB); spectral gating will be effective"
        )
        reasoning["MUTER_DENOISE_STRENGTH"] = (
            f"{strength:.1f} — {'aggressive' if strength >= 2.0 else 'moderate'} "
            f"denoising for {'poor' if snr < 15 else 'moderate'} SNR"
        )
    elif snr < 15:
        settings["MUTER_SPECTRAL_DENOISE"] = True
        settings["MUTER_DENOISE_STRENGTH"] = 1.0
        reasoning["MUTER_SPECTRAL_DENOISE"] = (
            f"Enabled — low SNR ({snr:.0f} dB); even non-stationary noise "
            f"benefits from gentle spectral reduction"
        )
        reasoning["MUTER_DENOISE_STRENGTH"] = (
            "1.0 — gentle; noise is non-stationary so aggressive denoising "
            "would distort the signal"
        )
    else:
        settings["MUTER_SPECTRAL_DENOISE"] = False
        settings["MUTER_DENOISE_STRENGTH"] = 1.0
        reasoning["MUTER_SPECTRAL_DENOISE"] = (
            f"Disabled — good SNR ({snr:.0f} dB); denoising unnecessary"
        )

    notch_freqs = list(tonal_noise) if tonal_noise else []
    if has_neg_profile and has_profile:
        for neg_region in signal_profile.get("negative_regions", []):
            region_low = neg_region.get("f_low", 0)
            region_high = neg_region.get("f_high", 0)
            region_bandwidth = region_high - region_low
            if (
                region_bandwidth > 0
                and region_bandwidth < 500
                and region_high > sig_f_low
                and region_low < sig_f_high
            ):
                center = (region_low + region_high) / 2
                if not any(abs(center - freq_hz) < 50 for freq_hz in notch_freqs):
                    notch_freqs.append(round(center, 1))

    if notch_freqs:
        settings["MUTER_NOTCH_FREQS"] = notch_freqs
        settings["MUTER_NOTCH_Q"] = 30.0
        sources = []
        tonal_set = set(round(freq_hz) for freq_hz in (tonal_noise or []))
        neg_set = [freq_hz for freq_hz in notch_freqs if round(freq_hz) not in tonal_set]
        if tonal_noise:
            sources.append(
                f"tonal noise at {', '.join(f'{freq_hz:.0f} Hz' for freq_hz in tonal_noise)}"
            )
        if neg_set:
            sources.append(
                f"negative selections at {', '.join(f'{freq_hz:.0f} Hz' for freq_hz in neg_set)}"
            )
        reasoning["MUTER_NOTCH_FREQS"] = f"Notch filters for: {'; '.join(sources)}"
    else:
        settings["MUTER_NOTCH_FREQS"] = []
        settings["MUTER_NOTCH_Q"] = 30.0

    if has_profile and sig_bandwidth < 2000:
        settings["MUTER_BANDPASS_BOOST"] = True
        boost_low = max(20, int(sig_f_low))
        boost_high = int(sig_f_high)
        if has_neg_profile and neg_f_low is not None:
            if neg_f_low > sig_f_low and neg_f_low < sig_f_high:
                boost_high = min(boost_high, int(neg_f_low))
            if neg_f_high < sig_f_high and neg_f_high > sig_f_low:
                boost_low = max(boost_low, int(neg_f_high))
        settings["MUTER_BOOST_LOW_HZ"] = boost_low
        settings["MUTER_BOOST_HIGH_HZ"] = boost_high
        gain = 6.0 if snr < 20 else 4.0
        settings["MUTER_BOOST_GAIN_DB"] = gain
        reasoning["MUTER_BANDPASS_BOOST"] = (
            f"Enabled — signal is concentrated in a narrow band "
            f"({boost_low:.0f}–{boost_high:.0f} Hz, BW={sig_bandwidth:.0f} Hz); "
            f"boosting improves SNR by {gain:.0f} dB"
        )
    else:
        settings["MUTER_BANDPASS_BOOST"] = False
        settings["MUTER_BOOST_LOW_HZ"] = 300
        settings["MUTER_BOOST_HIGH_HZ"] = 3000
        settings["MUTER_BOOST_GAIN_DB"] = 6.0
        reasoning["MUTER_BANDPASS_BOOST"] = (
            "Disabled — signal bandwidth is wide or no profile provided; "
            "boosting might amplify noise"
        )

    if snr < 15 and stationarity > 0.4:
        settings["MUTER_SPECTRAL_ENHANCE"] = True
        settings["MUTER_ENHANCE_FACTOR"] = 2.5 if snr < 10 else 2.0
        reasoning["MUTER_SPECTRAL_ENHANCE"] = (
            f"Enabled — low SNR ({snr:.0f} dB) with somewhat stationary background; "
            f"enhancing spectral peaks lifts signal above noise"
        )
    else:
        settings["MUTER_SPECTRAL_ENHANCE"] = False
        settings["MUTER_ENHANCE_FACTOR"] = 2.0

    if dynamic_range > 40:
        settings["MUTER_COMPRESS"] = True
        if dynamic_range > 60:
            settings["MUTER_COMPRESS_RATIO"] = 4.0
            settings["MUTER_COMPRESS_THRESHOLD_DB"] = -40.0
        else:
            settings["MUTER_COMPRESS_RATIO"] = 2.5
            settings["MUTER_COMPRESS_THRESHOLD_DB"] = -30.0
        reasoning["MUTER_COMPRESS"] = (
            f"Enabled — wide dynamic range ({dynamic_range:.0f} dB); "
            f"compression boosts quiet events that might be missed"
        )
    else:
        settings["MUTER_COMPRESS"] = False
        settings["MUTER_COMPRESS_RATIO"] = 3.0
        settings["MUTER_COMPRESS_THRESHOLD_DB"] = -30.0
        reasoning["MUTER_COMPRESS"] = (
            f"Disabled — dynamic range is manageable ({dynamic_range:.0f} dB)"
        )

    if sig_character == "percussive" or (has_profile and sig_sharpness > 0.3):
        settings["MUTER_SHARPEN_TRANSIENTS"] = True
        settings["MUTER_SHARPEN_GAIN_DB"] = 6.0
        if has_profile:
            avg_dur = signal_profile["summary"]["avg_signal_duration_s"]
            attack_ms = min(20, max(5, avg_dur * 1000 * 0.3))
        else:
            attack_ms = 10.0
        settings["MUTER_SHARPEN_ATTACK_MS"] = round(attack_ms, 1)
        reasoning["MUTER_SHARPEN_TRANSIENTS"] = (
            f"Enabled — {'signal profile shows sharp attacks' if has_profile else 'percussive character detected'}; "
            f"sharpening makes onsets more detectable"
        )
    else:
        settings["MUTER_SHARPEN_TRANSIENTS"] = False
        settings["MUTER_SHARPEN_GAIN_DB"] = 6.0
        settings["MUTER_SHARPEN_ATTACK_MS"] = 15.0
        reasoning["MUTER_SHARPEN_TRANSIENTS"] = (
            "Disabled — signal is harmonic/sustained; sharpening would add artifacts"
        )

    settings["MUTER_AUTO_THRESHOLD"] = True
    reasoning["MUTER_AUTO_THRESHOLD"] = (
        "Enabled — adaptive per-file thresholding adapts to each file's "
        "unique noise floor (recommended for all recordings)"
    )

    if snr > 30:
        settings["MUTER_NOISE_MARGIN_DB"] = 6.0
        reasoning["MUTER_NOISE_MARGIN_DB"] = (
            "6 dB — good SNR allows a tight margin above the noise floor"
        )
    elif snr > 15:
        settings["MUTER_NOISE_MARGIN_DB"] = 8.0
        reasoning["MUTER_NOISE_MARGIN_DB"] = (
            f"8 dB — moderate SNR ({snr:.0f} dB); wider margin preserves quiet signals"
        )
    else:
        settings["MUTER_NOISE_MARGIN_DB"] = 10.0
        reasoning["MUTER_NOISE_MARGIN_DB"] = (
            f"10 dB — low SNR ({snr:.0f} dB); wide margin avoids muting quiet signals"
        )

    settings["MUTER_DB_THRESHOLD"] = 30
    settings["MUTER_SAVE_NOISE_PROFILE"] = True

    settings["MUTER_FADE_MS"] = 5.0
    reasoning["MUTER_FADE_MS"] = (
        "5 ms — standard crossfade prevents mute-edge artifacts"
    )

    if has_profile and sig_f_high > 4000 and snr < 20:
        settings["MUTER_PRE_EMPHASIS"] = 0.97
        reasoning["MUTER_PRE_EMPHASIS"] = (
            "0.97 — signal has high-frequency content with moderate SNR; "
            "pre-emphasis compensates for distance roll-off"
        )
    else:
        settings["MUTER_PRE_EMPHASIS"] = 0.0
        reasoning["MUTER_PRE_EMPHASIS"] = "Disabled — no high-frequency compensation needed"

    if dynamic_range > 30:
        settings["MUTER_NORMALIZE"] = "rms"
        settings["MUTER_NORMALIZE_TARGET_DB"] = -3.0
        reasoning["MUTER_NORMALIZE"] = (
            "RMS — wide dynamic range benefits from perceived-loudness matching"
        )
    else:
        settings["MUTER_NORMALIZE"] = "peak"
        settings["MUTER_NORMALIZE_TARGET_DB"] = -1.0
        reasoning["MUTER_NORMALIZE"] = (
            "Peak — consistent dynamic range; peak normalization is sufficient"
        )

    settings["MUTER_TRIM_SILENCE"] = False
    settings["MUTER_TRIM_THRESHOLD_DB"] = 40.0

    settings["MUTER_CHANNEL"] = "mix"
    settings["MUTER_RESAMPLE_HZ"] = 44100
    reasoning["MUTER_RESAMPLE_HZ"] = (
        "44100 Hz — standard rate ensures consistent timing precision"
    )

    return {
        "analysis": analysis,
        "settings": settings,
        "reasoning": reasoning,
    }


def analyze_folder(folder_path, signal_profile=None, sr=None):
    """Analyze the first suitable audio file in a folder."""
    audio_exts = {".wav", ".mp3", ".flac", ".ogg", ".mp4", ".m4a", ".aiff"}
    files = sorted(
        [
            entry
            for entry in os.listdir(folder_path)
            if os.path.splitext(entry)[1].lower() in audio_exts
        ]
    )

    if not files:
        return {"error": f"No audio files found in {folder_path}"}

    first_path = os.path.join(folder_path, files[0])
    result = analyze_audio(first_path, signal_profile=signal_profile, sr=sr)
    result["analysis"]["n_files_in_folder"] = len(files)
    result["analysis"]["representative_file"] = files[0]
    return result


__all__ = [
    "analyze_audio",
    "analyze_folder",
    "detect_tonal_noise",
    "estimate_noise_floor",
    "estimate_noise_stationarity",
    "estimate_snr",
    "harmonic_percussive_ratio",
    "measure_dynamic_range",
    "spectral_profile",
]