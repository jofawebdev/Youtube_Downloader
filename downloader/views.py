import os
import subprocess
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpRequest
from django.contrib import messages
import yt_dlp as youtube_dl
from typing import Union

# Ensure download directory exists
os.makedirs(settings.DOWNLOAD_DIR, exist_ok=True)

def home(request: HttpRequest) -> HttpResponse:
    """Render the main download interface."""
    has_ffmpeg = _check_ffmpeg_available()
    context = {
        'supports_merged_formats': has_ffmpeg,
    }
    return render(request, 'downloader/home.html', context)

def download_video(request: HttpRequest) -> Union[HttpResponse, redirect]:
    """
    Handle video download requests with comprehensive error handling and
    format selection based on system capabilities.
    """
    if request.method != 'POST':
        messages.error(request, "Invalid request method")
        return redirect('home')

    video_url = request.POST.get('url', '').strip()
    
    # Validate URL input
    if not video_url or 'youtube.com/' not in video_url and 'youtu.be/' not in video_url:
        messages.warning(request, "Please provide a valid YouTube URL")
        return redirect('home')

    # Configure base download options
    ydl_opts = {
        'outtmpl': os.path.join(settings.DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'progress_hooks': [_get_progress_hook(request)],
        'ffmpeg_location': getattr(settings, 'FFMPEG_PATH', None),
    }

    try:
        # Configure format selection based on ffmpeg availability
        if _check_ffmpeg_available():
            ydl_opts.update({
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
            })
        else:
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best'
            messages.info(request, "Using basic download mode - some HD formats might not be available")

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            # First get video info without downloading
            info_dict = ydl.extract_info(video_url, download=False)
            
            # Check video duration against limit
            max_duration = getattr(settings, 'MAX_VIDEO_DURATION', 7200)  # Default 2 hours
            if info_dict.get('duration', 0) > max_duration:
                messages.warning(
                    request, 
                    f"Videos longer than {max_duration//3600} hours are not supported"
                )
                return redirect('home')
            
            # Start actual download
            ydl.download([video_url])
            
        messages.success(
            request, 
            f"'{info_dict.get('title', 'Video')}' downloaded successfully!"
        )
        return redirect('home')

    except youtube_dl.utils.DownloadError as e:
        error_msg = _parse_youtube_dl_error(str(e))
        messages.error(request, error_msg)
    except youtube_dl.utils.ExtractorError:
        messages.error(request, "Error extracting video information")
    except Exception as e:
        messages.error(request, f"Unexpected error: {str(e)}")
        if settings.DEBUG:
            raise  # Re-raise in development for debugging
    
    return redirect('home')

def _check_ffmpeg_available() -> bool:
    """
    Verify ffmpeg installation and accessibility.
    Returns:
        bool: True if ffmpeg is available, False otherwise
    """
    try:
        ffmpeg_path = getattr(settings, 'FFMPEG_PATH', 'ffmpeg')
        result = subprocess.run(
            [ffmpeg_path, '-version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return 'ffmpeg version' in result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def _parse_youtube_dl_error(error: str) -> str:
    """Convert yt-dlp errors to user-friendly messages."""
    error_lower = error.lower()
    
    if 'unable to download webpage' in error_lower:
        return "Video not found or unavailable"
    if 'ffmpeg' in error_lower and 'not installed' in error_lower:
        return "System configuration issue - using basic download mode"
    if 'private video' in error_lower:
        return "This video is private and cannot be downloaded"
    if 'age restricted' in error_lower:
        return "Age-restricted content requires YouTube login"
    if 'copyright' in error_lower:
        return "Copyright protected content cannot be downloaded"
    if 'unavailable' in error_lower:
        return "Video is unavailable in your region"
    
    return "Error downloading video - please check the URL"

def _get_progress_hook(request: HttpRequest) -> callable:
    """Generate a progress hook function for tracking download progress."""
    def progress_hook(d: dict) -> None:
        """
        Handle download progress updates.
        Implement with WebSocket or server-side events for real-time updates.
        """
        # TODO: Implement progress tracking system
        if d['status'] == 'downloading':
            # Example: Store progress in cache or database
            pass
            
    return progress_hook