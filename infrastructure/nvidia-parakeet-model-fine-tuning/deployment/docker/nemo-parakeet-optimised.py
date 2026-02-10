import os
import tempfile
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List, Dict, Any
import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import soundfile as sf
import numpy as np
from datetime import datetime
import logging
import gc
import torch
import multiprocessing as mp
from contextlib import asynccontextmanager
import psutil
import time
from functools import lru_cache
import hashlib

# Import NeMo
import nemo.collections.asr as nemo_asr

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
asr_model = None
model_info = {}
model_lock = asyncio.Lock()

# Performance optimizations
torch.set_num_threads(min(4, mp.cpu_count()))  # Limit CPU threads
torch.backends.cudnn.benchmark = True  # Optimize CUDNN for consistent input sizes

# Configuration
class Config:
    MODEL_NAME = os.getenv("NEMO_MODEL", "nvidia/parakeet-rnnt-1.1b")
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", min(4, mp.cpu_count())))
    MAX_AUDIO_LENGTH = int(os.getenv("MAX_AUDIO_LENGTH", 300))  # seconds
    CACHE_SIZE = int(os.getenv("CACHE_SIZE", 128))
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", 1))
    USE_GPU = os.getenv("USE_GPU", "true").lower() == "true"
    PRECISION = os.getenv("PRECISION", "float16")  # float16, float32
    PORT = int(os.getenv("PORT", 8080))
    HOST = os.getenv("HOST", "0.0.0.0")

# Performance monitoring
class PerformanceMonitor:
    def __init__(self):
        self.request_count = 0
        self.total_processing_time = 0.0
        self.start_time = time.time()
    
    def record_request(self, processing_time: float):
        self.request_count += 1
        self.total_processing_time += processing_time
    
    @property
    def average_processing_time(self) -> float:
        return self.total_processing_time / max(1, self.request_count)
    
    @property
    def requests_per_second(self) -> float:
        uptime = time.time() - self.start_time
        return self.request_count / max(1, uptime)

perf_monitor = PerformanceMonitor()

# Model management
async def load_model():
    """Load and optimize the NeMo ASR model"""
    global asr_model, model_info
    
    async with model_lock:
        if asr_model is not None:
            return
            
        try:
            logger.info(f"Loading NeMo ASR model: {Config.MODEL_NAME}")
            
            # Load model
            asr_model = nemo_asr.models.EncDecRNNTBPEModel.from_pretrained(
                model_name=Config.MODEL_NAME
            )
            
            # Optimization settings
            asr_model.eval()
            asr_model.freeze()  # <-- This is the crucial fix
            
            
            # Move to GPU if available and requested
            if Config.USE_GPU and torch.cuda.is_available():
                asr_model = asr_model.cuda()
                logger.info("Model moved to GPU")
                
                # Enable mixed precision for faster inference
                if Config.PRECISION == "float16":
                    asr_model = asr_model.half()
                    logger.info("Model converted to half precision")
            else:
                logger.info("Using CPU for inference")
            
            # Disable gradients for inference
            for param in asr_model.parameters():
                param.requires_grad = False
            
            # Compile model for faster inference (PyTorch 2.0+)
            try:
                if hasattr(torch, 'compile'):
                    asr_model = torch.compile(asr_model, mode='reduce-overhead')
                    logger.info("Model compiled with torch.compile")
            except Exception as e:
                logger.warning(f"Could not compile model: {e}")
            
            # Get model information
            model_info = {
                "model_name": Config.MODEL_NAME,
                "model_type": "EncDecRNNTBPEModel",
                "architecture": "RNN-Transducer",
                "sample_rate": getattr(asr_model, 'sample_rate', 16000),
                "vocabulary_size": len(asr_model.decoder.vocabulary) if hasattr(asr_model.decoder, 'vocabulary') else "unknown",
                "device": "cuda" if Config.USE_GPU and torch.cuda.is_available() else "cpu",
                "precision": Config.PRECISION,
                "loaded_at": datetime.now().isoformat()
            }
            
            logger.info(f"Model loaded successfully: {model_info}")
            
            # Warm up the model
            await warmup_model()
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise e

async def warmup_model():
    """Warm up the model with a dummy input"""
    if asr_model is None:
        return
        
    try:
        logger.info("Warming up model...")
        
        # Create dummy audio (1 second of silence)
        sample_rate = model_info.get('sample_rate', 16000)
        dummy_audio = np.zeros(sample_rate, dtype=np.float32)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            sf.write(temp_file.name, dummy_audio, sample_rate)
            
            # Run dummy transcription
            _ = await run_transcription([temp_file.name], batch_size=1)
            
            # Cleanup
            os.unlink(temp_file.name)
            
        logger.info("Model warmup completed")
        
    except Exception as e:
        logger.warning(f"Model warmup failed: {e}")

@lru_cache(maxsize=Config.CACHE_SIZE)
def get_audio_hash(file_path: str, file_size: int) -> str:
    """Generate hash for audio file for caching"""
    return hashlib.md5(f"{file_path}_{file_size}".encode()).hexdigest()

def preprocess_audio_file(file_path: str, target_sample_rate: int = 16000) -> str:
    """Optimized audio preprocessing"""
    try:
        # Read audio file
        audio_data, sample_rate = sf.read(file_path)
        
        # Convert to mono if stereo
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)
        
        # Check audio length
        duration = len(audio_data) / sample_rate
        if duration > Config.MAX_AUDIO_LENGTH:
            logger.warning(f"Audio too long ({duration:.2f}s), truncating to {Config.MAX_AUDIO_LENGTH}s")
            audio_data = audio_data[:int(Config.MAX_AUDIO_LENGTH * sample_rate)]
        
        # Resample if necessary
        if sample_rate != target_sample_rate:
            import librosa
            audio_data = librosa.resample(
                audio_data, 
                orig_sr=sample_rate, 
                target_sr=target_sample_rate
            )
        
        # Normalize audio
        audio_data = audio_data / (np.max(np.abs(audio_data)) + 1e-8)
        
        # Save preprocessed audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
            sf.write(temp_file.name, audio_data, target_sample_rate)
            return temp_file.name
            
    except Exception as e:
        logger.error(f"Audio preprocessing failed: {e}")
        raise e

async def run_transcription(audio_files: List[str], 
                          batch_size: int = None,
                          language: str = "en") -> List[Dict[str, Any]]:
    """Optimized transcription function"""
    global asr_model
    
    if asr_model is None:
        raise RuntimeError("Model not loaded")
    
    if batch_size is None:
        batch_size = Config.BATCH_SIZE
    
    try:
        start_time = time.time()
        
        # Use torch.no_grad() for inference
        with torch.no_grad():
            # Enable autocast for mixed precision if using GPU
            if Config.USE_GPU and torch.cuda.is_available():
                with torch.cuda.amp.autocast(enabled=(Config.PRECISION == "float16")):
                    transcriptions = asr_model.transcribe(audio_files, batch_size=batch_size)
            else:
                transcriptions = asr_model.transcribe(audio_files, batch_size=batch_size)
        
        processing_time = time.time() - start_time
        perf_monitor.record_request(processing_time)
        
        logger.info(f"Transcribed {len(audio_files)} files in {processing_time:.2f}s")
        
        results = []
        for i, transcription in enumerate(transcriptions):
            # Extract text and confidence
            if hasattr(transcription, 'text'):
                text = transcription.text
            else:
                text = str(transcription)
            
            confidence = None
            if hasattr(transcription, 'score'):
                confidence = float(transcription.score)
            elif hasattr(transcription, 'confidence'):
                confidence = float(transcription.confidence)
            
            # Get timing information if available
            words = []
            if hasattr(transcription, 'words') and transcription.words:
                for word_info in transcription.words:
                    if hasattr(word_info, 'word') and hasattr(word_info, 'start_time'):
                        words.append({
                            "word": word_info.word,
                            "start": float(word_info.start_time),
                            "end": float(word_info.end_time) if hasattr(word_info, 'end_time') else None,
                            "confidence": float(word_info.confidence) if hasattr(word_info, 'confidence') else None
                        })
            
            results.append({
                "text": text,
                "confidence": confidence,
                "words": words,
                "file_index": i,
                "processing_time": processing_time
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise e
    finally:
        # Force garbage collection
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await load_model()
    yield
    # Shutdown
    global asr_model
    if asr_model:
        del asr_model
        asr_model = None
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

# FastAPI app with lifespan
app = FastAPI(
    title="Optimized NeMo ASR OpenAI-Compatible API",
    description="High-performance OpenAI-compatible transcription API using NeMo ASR models",
    version="2.0.0",
    lifespan=lifespan
)

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool with optimized size
executor = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)

@app.post("/v1/audio/transcriptions")
async def create_transcription(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Audio file to transcribe"),
    model: Optional[str] = "nemo-parakeet-rnnt-1.1b",
    language: Optional[str] = "en",
    prompt: Optional[str] = None,
    response_format: Optional[str] = "json",
    temperature: Optional[float] = 0.0,
    timestamp_granularities: Optional[List[str]] = None
):
    """Optimized transcription endpoint"""
    global asr_model
    
    if asr_model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_extension = file.filename.lower().split('.')[-1]
    supported_formats = ['wav', 'mp3', 'flac', 'm4a', 'ogg', 'webm']
    
    if file_extension not in supported_formats:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file format: {file_extension}. Supported: {supported_formats}"
        )
    
    # Save uploaded file
    with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_input_path = temp_file.name
    
    # Schedule cleanup
    def cleanup_files(*paths):
        for path in paths:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except:
                    pass
    
    preprocessed_path = None
    
    try:
        # Preprocess audio
        target_sample_rate = model_info.get('sample_rate', 16000)
        preprocessed_path = preprocess_audio_file(temp_input_path, target_sample_rate)
        
        # Get audio duration
        audio_data, sample_rate = sf.read(preprocessed_path)
        duration = len(audio_data) / sample_rate
        
        # Run transcription
        loop = asyncio.get_event_loop()
        transcription_results = await loop.run_in_executor(
            executor,
            lambda: asyncio.run(run_transcription([preprocessed_path], language=language))
        )
        
        if not transcription_results:
            raise HTTPException(status_code=500, detail="Transcription failed")
        
        result = transcription_results[0]
        text = result["text"]
        confidence = result.get("confidence")
        words = result.get("words", [])
        processing_time = result.get("processing_time", 0)
        
        # Schedule cleanup in background
        background_tasks.add_task(cleanup_files, temp_input_path, preprocessed_path)
        
        # Format response
        if response_format == "verbose_json":
            response = {
                "task": "transcribe",
                "language": language,
                "duration": round(duration, 2),
                "text": text,
                "words": words if timestamp_granularities and "word" in timestamp_granularities else None,
                "segments": [
                    {
                        "id": 0,
                        "seek": 0,
                        "start": 0.0,
                        "end": round(duration, 2),
                        "text": text,
                        "tokens": [],
                        "temperature": temperature,
                        "avg_logprob": confidence if confidence else 0.0,
                        "compression_ratio": len(text) / max(duration, 1),
                        "no_speech_prob": 0.0
                    }
                ],
                "performance": {
                    "processing_time": round(processing_time, 3),
                    "real_time_factor": round(processing_time / duration, 2) if duration > 0 else 0,
                    "model_info": model_info
                }
            }
        elif response_format == "text":
            return text
        elif response_format == "srt":
            srt_content = f"1\n00:00:00,000 --> {duration_to_srt(duration)}\n{text}\n"
            return srt_content
        elif response_format == "vtt":
            vtt_content = f"WEBVTT\n\n1\n00:00:00.000 --> {duration_to_vtt(duration)}\n{text}\n"
            return vtt_content
        else:  # json format
            response = {
                "text": text
            }
        
        return response
        
    except Exception as e:
        # Immediate cleanup on error
        cleanup_files(temp_input_path, preprocessed_path)
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Enhanced health check with system metrics"""
    global asr_model
    
    # System metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    gpu_info = {}
    if torch.cuda.is_available():
        gpu_info = {
            "gpu_available": True,
            "gpu_count": torch.cuda.device_count(),
            "current_device": torch.cuda.current_device(),
            "memory_allocated": torch.cuda.memory_allocated() / 1024**3,  # GB
            "memory_reserved": torch.cuda.memory_reserved() / 1024**3,  # GB
        }
    
    return {
        "status": "healthy" if asr_model is not None else "unhealthy",
        "model_loaded": asr_model is not None,
        "model_info": model_info if asr_model else None,
        "system_metrics": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_gb": memory.available / 1024**3,
            "disk_percent": disk.percent,
            "disk_free_gb": disk.free / 1024**3
        },
        "gpu_info": gpu_info,
        "performance": {
            "total_requests": perf_monitor.request_count,
            "avg_processing_time": round(perf_monitor.average_processing_time, 3),
            "requests_per_second": round(perf_monitor.requests_per_second, 2)
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/metrics")
async def get_metrics():
    """Prometheus-style metrics endpoint"""
    return {
        "nemo_asr_requests_total": perf_monitor.request_count,
        "nemo_asr_processing_seconds_total": perf_monitor.total_processing_time,
        "nemo_asr_processing_seconds_avg": perf_monitor.average_processing_time,
        "nemo_asr_requests_per_second": perf_monitor.requests_per_second,
        "nemo_asr_model_loaded": 1 if asr_model is not None else 0,
    }

@app.get("/v1/models")
async def list_models():
    """List available models"""
    return {
        "object": "list",
        "data": [
            {
                "id": "nemo-parakeet-rnnt-1.1b",
                "object": "model",
                "created": int(datetime.now().timestamp()),
                "owned_by": "nvidia",
                "permission": [],
                "root": "nemo-parakeet-rnnt-1.1b",
                "parent": None
            }
        ]
    }

@app.get("/status")
async def get_status():
    """Detailed status information"""
    return {
        "service": "Optimized NeMo ASR OpenAI-Compatible API",
        "version": "2.0.0",
        "config": {
            "model_name": Config.MODEL_NAME,
            "max_workers": Config.MAX_WORKERS,
            "max_audio_length": Config.MAX_AUDIO_LENGTH,
            "batch_size": Config.BATCH_SIZE,
            "use_gpu": Config.USE_GPU,
            "precision": Config.PRECISION,
        },
        "model_loaded": asr_model is not None,
        "model_info": model_info,
        "supported_formats": ["wav", "mp3", "flac", "m4a", "ogg", "webm"],
        "response_formats": ["json", "text", "srt", "vtt", "verbose_json"],
    }

def duration_to_srt(duration: float) -> str:
    """Convert duration to SRT timestamp"""
    hours = int(duration // 3600)
    minutes = int((duration % 3600) // 60)
    seconds = int(duration % 60)
    milliseconds = int((duration % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def duration_to_vtt(duration: float) -> str:
    """Convert duration to WebVTT timestamp"""
    hours = int(duration // 3600)
    minutes = int((duration % 3600) // 60)
    seconds = duration % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

if __name__ == "__main__":
    uvicorn.run(
        app, 
        host=Config.HOST, 
        port=Config.PORT,
        log_level="info",
        workers=1,  # Single worker for model sharing
        loop="uvloop" if os.name != 'nt' else "asyncio"  # Use uvloop on Unix
    )
