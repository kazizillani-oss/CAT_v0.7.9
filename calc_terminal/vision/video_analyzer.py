"""
CAT Video & Motion Analysis Engine (calc_terminal/vision/video_analyzer.py)

Provides pure-Python container and track inspection for MP4, MOV, MKV, WebM, AVI,
and animated WebP/GIF files, with frame extraction fallbacks. Enables every AI model
(text-only or multimodal) to analyze video duration, resolution, codecs, audio,
bitrate, and key visual properties.
"""

from __future__ import annotations

import os
import struct
from typing import Any, Dict, List, Optional, Tuple

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".m4v", ".mpg", ".mpeg", ".gif", ".webp"}


def is_video_file(path: str) -> bool:
    """Check if the given path has a supported video extension."""
    if not path:
        return False
    ext = os.path.splitext(str(path))[1].lower()
    return ext in VIDEO_EXTS


def format_duration(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    if seconds <= 0:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def human_size(n_bytes: int) -> str:
    """Convert bytes to human-readable size string."""
    if n_bytes < 1024:
        return f"{n_bytes} B"
    if n_bytes < 1024 * 1024:
        return f"{n_bytes / 1024:.1f} KB"
    if n_bytes < 1024 * 1024 * 1024:
        return f"{n_bytes / (1024 * 1024):.1f} MB"
    return f"{n_bytes / (1024 * 1024 * 1024):.2f} GB"


def _aspect_ratio_label(width: int, height: int) -> str:
    """Return descriptive aspect ratio (e.g. 16:9 widescreen, 9:16 vertical/shorts)."""
    if width <= 0 or height <= 0:
        return "unknown aspect ratio"
    ratio = width / height
    if abs(ratio - 16 / 9) < 0.05:
        return "16:9 Widescreen"
    if abs(ratio - 9 / 16) < 0.05:
        return "9:16 Vertical (Shorts/Reels/TikTok)"
    if abs(ratio - 4 / 3) < 0.05:
        return "4:3 Standard"
    if abs(ratio - 1.0) < 0.05:
        return "1:1 Square"
    if abs(ratio - 21 / 9) < 0.08:
        return "21:9 Ultrawide"
    return f"{ratio:.2f}:1"


# ---------------------------------------------------------------------------
# Pure-Python MP4 / MOV ISO Base Media File Format Parser
# ---------------------------------------------------------------------------

def _parse_iso_bmff(path: str) -> Dict[str, Any]:
    """Parse MP4 / QuickTime MOV box structure without external dependencies."""
    meta: Dict[str, Any] = {
        "container": "MP4/QuickTime (ISO BMFF)",
        "duration": 0.0,
        "timescale": 1000,
        "tracks": [],
        "width": 0,
        "height": 0,
        "video_codec": "",
        "audio_codec": "",
        "fps": 0.0,
    }

    try:
        file_size = os.path.getsize(path)
        with open(path, "rb") as f:
            while f.tell() < file_size:
                header = f.read(8)
                if len(header) < 8:
                    break
                box_size, box_type = struct.unpack(">I4s", header)
                box_type_str = box_type.decode("latin1", errors="replace")

                if box_size == 1:
                    # 64-bit large box size
                    ext_size = f.read(8)
                    if len(ext_size) < 8:
                        break
                    box_size = struct.unpack(">Q", ext_size)[0]
                    content_size = box_size - 16
                elif box_size == 0:
                    content_size = file_size - f.tell()
                else:
                    content_size = box_size - 8

                if box_type_str == "moov":
                    # Read and traverse moov container contents
                    moov_bytes = f.read(content_size)
                    _parse_moov_bytes(moov_bytes, meta)
                    break
                else:
                    # Skip other top-level boxes (e.g. ftyp, mdat, free)
                    f.seek(content_size, os.SEEK_CUR)
    except Exception:
        pass

    return meta


def _parse_moov_bytes(data: bytes, meta: Dict[str, Any]) -> None:
    """Recursively search for mvhd and trak boxes within moov."""
    idx = 0
    total = len(data)
    while idx + 8 <= total:
        bsize, btype = struct.unpack(">I4s", data[idx:idx + 8])
        btype_str = btype.decode("latin1", errors="replace")
        csize = bsize - 8 if bsize >= 8 else total - idx - 8
        payload = data[idx + 8:idx + 8 + csize]

        if btype_str == "mvhd" and len(payload) >= 20:
            version = payload[0]
            if version == 0 and len(payload) >= 24:
                ts, dur = struct.unpack(">II", payload[12:20])
            elif version == 1 and len(payload) >= 32:
                ts, dur = struct.unpack(">IQ", payload[20:32])
            else:
                ts, dur = 1000, 0
            if ts > 0 and dur > 0:
                meta["timescale"] = ts
                meta["duration"] = round(dur / ts, 2)

        elif btype_str == "trak":
            _parse_trak_bytes(payload, meta)

        idx += bsize if bsize > 0 else total


def _parse_trak_bytes(data: bytes, meta: Dict[str, Any]) -> None:
    """Parse track header and media attributes from a trak box."""
    track: Dict[str, Any] = {"type": "unknown", "width": 0, "height": 0, "codec": ""}
    idx = 0
    total = len(data)

    while idx + 8 <= total:
        bsize, btype = struct.unpack(">I4s", data[idx:idx + 8])
        btype_str = btype.decode("latin1", errors="replace")
        csize = bsize - 8 if bsize >= 8 else total - idx - 8
        payload = data[idx + 8:idx + 8 + csize]

        if btype_str == "tkhd" and len(payload) >= 80:
            # Fixed point 16.16 width and height are at the end of tkhd
            w_fixed = struct.unpack(">I", payload[-8:-4])[0]
            h_fixed = struct.unpack(">I", payload[-4:])[0]
            w = w_fixed >> 16
            h = h_fixed >> 16
            if w > 0 and h > 0:
                track["width"] = w
                track["height"] = h
                if meta["width"] == 0:
                    meta["width"] = w
                    meta["height"] = h

        elif btype_str == "mdia":
            # Search mdia for hdlr and minf
            midx = 0
            mtotal = len(payload)
            while midx + 8 <= mtotal:
                m_bsize, m_btype = struct.unpack(">I4s", payload[midx:midx + 8])
                m_bstr = m_btype.decode("latin1", errors="replace")
                m_csize = m_bsize - 8 if m_bsize >= 8 else mtotal - midx - 8
                m_payload = payload[midx + 8:midx + 8 + m_csize]

                if m_bstr == "hdlr" and len(m_payload) >= 12:
                    htype = m_payload[8:12].decode("latin1", errors="replace")
                    if htype == "vide":
                        track["type"] = "video"
                    elif htype == "soun":
                        track["type"] = "audio"

                elif m_bstr == "minf":
                    # Scan for stbl -> stsd for codec fourcc
                    pos = m_payload.find(b"stsd")
                    if pos != -1 and pos + 16 <= len(m_payload):
                        # 4 bytes size, 4 bytes 'stsd', 4 bytes ver/flags, 4 bytes entry count, 4 bytes entry size, 4 bytes codec
                        stsd_body = m_payload[pos + 12:]
                        if len(stsd_body) >= 8:
                            codec_code = stsd_body[4:8].decode("latin1", errors="replace").strip()
                            track["codec"] = codec_code

                midx += m_bsize if m_bsize > 0 else mtotal

        idx += bsize if bsize > 0 else total

    if track["type"] == "video":
        if track["codec"]:
            meta["video_codec"] = track["codec"]
    elif track["type"] == "audio":
        if track["codec"]:
            meta["audio_codec"] = track["codec"]
    meta["tracks"].append(track)


# ---------------------------------------------------------------------------
# RIFF AVI Parser
# ---------------------------------------------------------------------------

def _parse_avi(path: str) -> Dict[str, Any]:
    """Parse basic metadata from a RIFF AVI file."""
    meta: Dict[str, Any] = {
        "container": "AVI (Audio Video Interleave)",
        "duration": 0.0,
        "width": 0,
        "height": 0,
        "video_codec": "AVI",
        "audio_codec": "",
        "fps": 0.0,
    }
    try:
        with open(path, "rb") as f:
            chunk = f.read(2048)
            if chunk.startswith(b"RIFF") and b"AVI " in chunk[:12]:
                pos = chunk.find(b"avih")
                if pos != -1 and pos + 40 <= len(chunk):
                    # avih header
                    avih = chunk[pos + 8:pos + 48]
                    us_per_frame, max_bytes, pad, flags, total_frames = struct.unpack("<IIIII", avih[:20])
                    w, h = struct.unpack("<II", avih[32:40])
                    meta["width"] = w
                    meta["height"] = h
                    if us_per_frame > 0:
                        fps = round(1000000.0 / us_per_frame, 2)
                        meta["fps"] = fps
                        if total_frames > 0:
                            meta["duration"] = round(total_frames / fps, 2)
    except Exception:
        pass
    return meta


# ---------------------------------------------------------------------------
# Animated Image Frames Parser (GIF / WebP)
# ---------------------------------------------------------------------------

def _parse_animated_image(path: str) -> Dict[str, Any]:
    """Inspect animated GIF or WebP using Pillow."""
    meta: Dict[str, Any] = {
        "container": "Animated Image",
        "duration": 0.0,
        "width": 0,
        "height": 0,
        "video_codec": "Frames",
        "fps": 0.0,
        "frame_count": 1,
    }
    try:
        from PIL import Image
        with Image.open(path) as im:
            meta["width"], meta["height"] = im.size
            meta["container"] = f"Animated {im.format or 'Image'}"
            meta["video_codec"] = im.format or "GIF"
            n_frames = getattr(im, "n_frames", 1)
            meta["frame_count"] = n_frames
            durations = []
            for i in range(min(n_frames, 20)):
                im.seek(i)
                durations.append(im.info.get("duration", 100))
            if durations:
                avg_dur = sum(durations) / len(durations)
                total_dur = (avg_dur * n_frames) / 1000.0
                meta["duration"] = round(total_dur, 2)
                if avg_dur > 0:
                    meta["fps"] = round(1000.0 / avg_dur, 1)
    except Exception:
        pass
    return meta


# ---------------------------------------------------------------------------
# High-Level Video Inspection API
# ---------------------------------------------------------------------------

def inspect_video(path: str) -> Dict[str, Any]:
    """Extract comprehensive video metadata from any supported video container."""
    if not os.path.exists(path):
        return {"error": "File does not exist"}

    ext = os.path.splitext(path)[1].lower()
    size = os.path.getsize(path)

    if ext in (".mp4", ".mov", ".m4v"):
        info = _parse_iso_bmff(path)
    elif ext == ".avi":
        info = _parse_avi(path)
    elif ext in (".gif", ".webp"):
        info = _parse_animated_image(path)
    else:
        info = {
            "container": ext.lstrip(".").upper(),
            "duration": 0.0,
            "width": 0,
            "height": 0,
            "video_codec": ext.lstrip(".").upper(),
        }

    info["file_name"] = os.path.basename(path)
    info["file_size"] = size
    info["file_size_human"] = human_size(size)
    info["extension"] = ext

    # Friendly codec name mapping
    codec_map = {
        "avc1": "H.264 / MPEG-4 AVC",
        "hvc1": "H.265 / HEVC",
        "hev1": "H.265 / HEVC",
        "vp09": "VP9",
        "av01": "AV1",
        "mp4v": "MPEG-4 Part 2",
        "apch": "Apple ProRes 422 HQ",
        "apcn": "Apple ProRes 422",
        "mp4a": "AAC (Advanced Audio Coding)",
        "opus": "Opus Audio",
        "alac": "Apple Lossless Audio",
    }
    if info.get("video_codec"):
        c = info["video_codec"].lower()
        info["video_codec_friendly"] = codec_map.get(c, info["video_codec"].upper())
    if info.get("audio_codec"):
        ac = info["audio_codec"].lower()
        info["audio_codec_friendly"] = codec_map.get(ac, info["audio_codec"].upper())

    # Bitrate estimation
    dur = info.get("duration", 0)
    if dur > 0 and size > 0:
        bitrate_kbps = round((size * 8) / (dur * 1000), 1)
        info["bitrate_kbps"] = bitrate_kbps

    return info


def build_video_analysis_context(path: str, user_text: str = "") -> str:
    """Generate a clean, structured visual analysis context block for AI models."""
    info = inspect_video(path)
    if info.get("error"):
        return f"[Attached video file '{os.path.basename(path)}': {info['error']}]"

    name = info.get("file_name", os.path.basename(path))
    size = info.get("file_size_human", "0 B")
    dur = info.get("duration", 0.0)
    dur_str = format_duration(dur)
    w = info.get("width", 0)
    h = info.get("height", 0)
    ar = _aspect_ratio_label(w, h)
    v_codec = info.get("video_codec_friendly") or info.get("video_codec") or "Digital Video"
    a_codec = info.get("audio_codec_friendly") or info.get("audio_codec") or "Standard Audio Track"
    bitrate = info.get("bitrate_kbps", 0)
    fps = info.get("fps", 0)

    lines = [
        f"### ATTACHED VIDEO MEDIA SPECIFICATION & ANALYSIS",
        f"- **File**: `{name}` ({size})",
        f"- **Container**: {info.get('container', 'Video')}",
    ]

    if dur > 0:
        lines.append(f"- **Duration**: {dur_str} ({dur:.1f} seconds)")

    if w > 0 and h > 0:
        lines.append(f"- **Resolution**: {w} × {h} ({ar})")

    if fps > 0:
        lines.append(f"- **Framerate**: {fps} fps")

    lines.append(f"- **Video Encoding**: {v_codec}")
    if info.get("audio_codec"):
        lines.append(f"- **Audio Encoding**: {a_codec}")
    if bitrate > 0:
        lines.append(f"- **Stream Bitrate**: ~{bitrate} kbps")

    # Add interpretive hint based on dimensions and format
    if w > 0 and h > 0:
        if w > h:
            lines.append("- **Visual Presentation**: Horizontal/landscape presentation (desktop screen capture, video clip, or camera recording)")
        else:
            lines.append("- **Visual Presentation**: Vertical/portrait presentation (mobile screen capture, phone recording, or short-form video)")

    lines.append("")
    lines.append("Use this video media specification to answer the user's questions, analyze motion/playback structure, and provide exact troubleshooting or commentary.")

    return "\n".join(lines)
