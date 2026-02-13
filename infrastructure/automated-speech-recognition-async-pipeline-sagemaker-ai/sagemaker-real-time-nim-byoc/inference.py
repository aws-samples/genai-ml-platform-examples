#!/usr/bin/env python3
"""
SageMaker Inference Script - Combined HTTP + gRPC routing to NVIDIA NIM ASR

Endpoints:
- GET  /ping
- POST /invocations          (transport=auto|http|grpc)
- POST /invocations/http     (force HTTP to NIM)
- POST /invocations/grpc     (force gRPC to NIM)
"""

import time
import asyncio
import base64
import io
import json
import logging
import os
import signal
import sys
import threading
import wave
from typing import Tuple

import riva.client
from aiohttp import web, ClientSession, FormData, WSMsgType
from riva.client.realtime import RealtimeClientASR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def detect_wav_sample_rate(audio_bytes: bytes, default_rate: int = 16000) -> int:
    try:
        with wave.open(io.BytesIO(audio_bytes), 'rb') as w:
            return w.getframerate()
    except Exception:
        return default_rate


class NimClient:
    def __init__(self, host_http: str, port_http: int, host_grpc: str, port_grpc: int):
        self.http_host = host_http
        self.http_port = port_http
        self.grpc_host = host_grpc
        self.grpc_port = port_grpc
        self._grpc_asr = None
        self._realtime_asr = None

    async def wait_ready(self):
        url = f"http://{self.http_host}:{self.http_port}/v1/health/ready"
        async with ClientSession() as session:
            for _ in range(120):
                try:
                    async with session.get(url, timeout=10) as resp:
                        if resp.status == 200:
                            logger.info("NIM HTTP ready")
                            break
                except Exception:
                    pass
                await asyncio.sleep(5)

        # gRPC client
        for attempt in range(60):
            try:
                auth = riva.client.Auth(uri=f"{self.grpc_host}:{self.grpc_port}")
                self._grpc_asr = riva.client.ASRService(auth)
                logger.info("NIM gRPC ready")
                return
            except Exception:
                if attempt == 59:
                    raise
                await asyncio.sleep(5)

    async def http_transcribe(self, audio_bytes: bytes, language: str) -> Tuple[int, dict]:
        url = f"http://{self.http_host}:{self.http_port}/v1/audio/transcriptions"
        form = FormData()
        form.add_field("file", audio_bytes, filename="audio.wav", content_type="audio/wav")
        form.add_field("language", language)
        async with ClientSession() as session:
            async with session.post(url, data=form, timeout=None) as resp:
                text = await resp.text()
                try:
                    payload = json.loads(text)
                except Exception:
                    payload = {"raw": text}
                return resp.status, payload

    def grpc_transcribe(self, audio_bytes: bytes, language: str, enable_diarization: bool = False, max_speakers: int = 10) -> dict:
        # Ensure audio_bytes is bytes (not bytearray) for gRPC compatibility
        if isinstance(audio_bytes, bytearray):
            audio_bytes = bytes(audio_bytes)
            
        sample_rate = detect_wav_sample_rate(audio_bytes)
        config = riva.client.RecognitionConfig(
            encoding=riva.client.AudioEncoding.LINEAR_PCM,
            sample_rate_hertz=sample_rate,
            language_code=language,
            enable_automatic_punctuation=True,
            enable_word_time_offsets=enable_diarization,  # Required for speaker diarization
            verbatim_transcripts=False,
            max_alternatives=1,
        )
        
        # Add speaker diarization configuration if requested
        if enable_diarization:
            riva.client.add_speaker_diarization_to_config(config, True, max_speakers)

        resp = self._grpc_asr_service().offline_recognize(audio_bytes, config)
        results = []
        for result in resp.results:
            alternatives = []
            for alt in result.alternatives:
                alternative = {
                    "transcript": alt.transcript,
                    "confidence": alt.confidence
                }
                # Include word-level timing and speaker info if available
                if enable_diarization and alt.words:
                    alternative["words"] = []
                    for word in alt.words:
                        word_info = {
                            "word": word.word,
                            "start_time": word.start_time / 1000.0,  # Convert ms to seconds
                            "end_time": word.end_time / 1000.0,      # Convert ms to seconds
                            "confidence": word.confidence
                        }
                        # Include speaker tag if available
                        if hasattr(word, 'speaker_tag') and word.speaker_tag is not None:
                            word_info["speaker_tag"] = word.speaker_tag
                        alternative["words"].append(word_info)
                alternatives.append(alternative)
            
            results.append({
                "alternatives": alternatives,
                "is_final": True,
                "channel_tag": result.channel_tag
            })
        return {"predictions": [{"results": results, "model_version": "parakeet-1-1b-ctc-en-us"}]}
    
    def realtime_transcribe(self, audio_bytes: bytes, language: str = 'en-US', enable_diarization: bool = False, max_speakers: int = 10) -> dict:
        # Ensure audio_bytes is bytes (not bytearray) for gRPC compatibility
        if isinstance(audio_bytes, bytearray):
            audio_bytes = bytes(audio_bytes)

        sample_rate = detect_wav_sample_rate(audio_bytes)
        config = riva.client.StreamingRecognitionConfig(
            config=riva.client.RecognitionConfig(
                encoding=riva.client.AudioEncoding.LINEAR_PCM,
                sample_rate_hertz=sample_rate,
                language_code=language,
                enable_automatic_punctuation=True,
                enable_word_time_offsets=enable_diarization,  # Required for speaker diarization
                verbatim_transcripts=False,
                max_alternatives=1,
            ),
            interim_results=True
        )
        
        # Add speaker diarization configuration if requested
        if enable_diarization:
            riva.client.add_speaker_diarization_to_config(config, True, max_speakers)

        resp_generator = self._grpc_asr_service().streaming_response_generator([audio_bytes], config)
        return resp_generator

    async def websocket_transcribe(self, audio_bytes: bytes):
        # client = RealtimeClientASR()
        client = self._realtime_asr_service()

        await client.connect()
        client.send_audio_chunks(audio_bytes)
        client.receive_reponses()
    
    def _realtime_asr_service(self) -> RealtimeClientASR:
        if self._realtime_asr is None:
            # auth = riva.client.Auth(uri=f"{self.http_host}:{self.http_port}")
            args = {
                "server": "localhost:9000"
            }
            self._realtime_asr = RealtimeClientASR(args)
        return self._realtime_asr

    def _grpc_asr_service(self) -> riva.client.ASRService:
        if self._grpc_asr is None:
            auth = riva.client.Auth(uri=f"{self.grpc_host}:{self.grpc_port}")
            self._grpc_asr = riva.client.ASRService(auth)
        return self._grpc_asr


def start_nim_services():
    import subprocess
    logger.info("Starting NIM services...")
    cmd = "source /opt/nim/start_server.sh && start_server"
    proc = subprocess.Popen(cmd, shell=True, executable="/bin/bash", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

    def monitor():
        for line in iter(proc.stdout.readline, ''):
            logger.info(f"NIM: {line.strip()}")
        proc.stdout.close()
        rc = proc.wait()
        logger.info(f"NIM exited with code {rc}")

    t = threading.Thread(target=monitor, daemon=True)
    t.start()


class App:
    def __init__(self):
        self.port = int(os.getenv("SAGEMAKER_BIND_TO_PORT", "8080"))
        nim_host = os.getenv("NIM_HOST", "127.0.0.1")
        http_port = int(os.getenv("NIM_HTTP_PORT", os.getenv("RIVA_HTTP_PORT", "9000")))
        grpc_port = int(os.getenv("RIVA_GRPC_PORT", "50051"))

        self.nim = NimClient(nim_host, http_port, nim_host, grpc_port)

    async def ping(self, request: web.Request) -> web.Response:
        return web.Response(status=200, text="Healthy")

    async def handle_invocations(self, request: web.Request) -> web.Response:
        # Check for SageMaker custom attributes to determine routing
        custom_attrs = request.headers.get("X-Amzn-SageMaker-Custom-Attributes", "")
        if "/invocations/grpc" in custom_attrs:
            transport = "grpc"
        elif "/invocations/http" in custom_attrs:
            transport = "http"
        else:
            # transport selector: auto|http|grpc (default auto chooses http unless content too large)
            transport = request.query.get("transport", "auto")
        content_type = request.headers.get("Content-Type", "")

        # Parse input
        audio_bytes = None
        language = request.query.get("language", request.query.get("language_code", "en-US"))
        speaker_diarization = False
        max_speakers = 10

        try:
            if content_type.startswith("multipart/form-data"):
                reader = await request.multipart()
                async for field in reader:
                    if field.name in ("audio", "file"):
                        audio_bytes = await field.read()
                    elif field.name in ("language", "language_code"):
                        language = (await field.read()).decode().strip()
                    elif field.name == "speaker_diarization":
                        speaker_diarization = (await field.read()).decode().strip().lower() == "true"
                    elif field.name == "max_speakers":
                        max_speakers = int((await field.read()).decode().strip())
            elif content_type.startswith("application/json"):
                data = await request.json()
                if 'instances' in data and data['instances']:
                    inst = data['instances'][0]
                    audio_b64 = inst.get('audio') or inst.get('audio_base64')
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                    language = inst.get('language_code', language)
                    speaker_diarization = inst.get('speaker_diarization', speaker_diarization)
                    max_speakers = inst.get('max_speakers', max_speakers)
                else:
                    audio_b64 = data.get('audio') or data.get('audio_base64')
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                    language = data.get('language_code', language)
                    speaker_diarization = data.get('speaker_diarization', speaker_diarization)
                    max_speakers = data.get('max_speakers', max_speakers)
            elif content_type.startswith("audio/") or content_type.startswith("application/octet-stream"):
                audio_bytes = await request.read()
            else:
                return web.json_response({"error": f"Unsupported content type: {content_type}"}, status=400)

            if not audio_bytes:
                return web.json_response({"error": "No audio provided"}, status=400)

            # Ensure audio_bytes is bytes (not bytearray) for gRPC compatibility
            if isinstance(audio_bytes, bytearray):
                audio_bytes = bytes(audio_bytes)

            # Route
            if transport == "http":
                status, payload = await self.nim.http_transcribe(audio_bytes, language)
                return web.json_response(payload, status=status)
            if transport == "grpc":
                payload = self.nim.grpc_transcribe(audio_bytes, language, enable_diarization=speaker_diarization, max_speakers=max_speakers)
                return web.json_response(payload, status=200)

            # auto: prefer HTTP, but if payload large hint clients to use grpc
            if len(audio_bytes) > 4 * 1024 * 1024:
                payload = self.nim.grpc_transcribe(audio_bytes, language, enable_diarization=speaker_diarization, max_speakers=max_speakers)
                return web.json_response(payload, status=200)
            status, payload = await self.nim.http_transcribe(audio_bytes, language)
            return web.json_response(payload, status=status)

        except Exception as e:
            logger.exception("Invocation failed")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_invocations_http(self, request: web.Request) -> web.Response:
        request._rel_url = request.rel_url.with_query({**request.rel_url.query, "transport": "http"})
        return await self.handle_invocations(request)

    async def handle_invocations_grpc(self, request: web.Request) -> web.Response:
        request._rel_url = request.rel_url.with_query({**request.rel_url.query, "transport": "grpc"})
        return await self.handle_invocations(request)
    
    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        additional_info = 'no'
        show_intermediate = True
        word_time_offsets = False
        speaker_diarization = False

        async for msg in ws:
            if msg.type == WSMsgType.TEXT or msg.type == WSMsgType.BINARY :
                generator = self.nim.realtime_transcribe(msg.data)
                num_chars_printed = 0
                for response in generator:
                    if not response.results:
                        continue
                    partial_transcript = ""
                    start_time = time.time()
                    for result in response.results:
                        if result.pipeline_states and len(result.pipeline_states.vad_probabilities) > 0:
                            vad_prob_logs = "VAD States: "
                            for vad_state in result.pipeline_states.vad_probabilities:
                                    vad_prob_logs += str(vad_state) + " "
                        if not result.alternatives:
                            continue
                        transcript = result.alternatives[0].transcript
                        if additional_info == 'no':
                            if result.is_final:
                                if show_intermediate:
                                    overwrite_chars = ' ' * (num_chars_printed - len(transcript))
                                    await ws.send_str(json.dumps({'predictions': {'results': '' + transcript + overwrite_chars}}))
                                    num_chars_printed = 0
                                else:
                                    alternatives = []
                                    for i, alternative in enumerate(result.alternatives):
                                        alternatives.append(alternative.transcript)
                                    await ws.send_str(json.dumps({'predictions': {'alternatives': alternatives}}))
                            else:
                                partial_transcript += transcript
                        elif additional_info == 'time':
                            if result.is_final:
                                alternatives = []
                                for i, alternative in enumerate(result.alternatives):
                                    alternatives.append({"transcript":alternative.transcript, "time": time.time() - start_time})
                                
                                await ws.send_str(json.dumps({'predictions': {'alternatives': alternatives}}))

                                # if word_time_offsets:
                                #     for f in output_file:
                                #         f.write("Timestamps:\n")
                                #         temp = '{: <40s}{: <16s}{: <16s}'
                                #         value = ['Word', 'Start (ms)', 'End (ms)']
                                #         if speaker_diarization:
                                #             temp += '{: <16s}'
                                #             value.append('Speaker')
                                #         temp += '\n'
                                #         f.write(temp.format(*value))
                                #         for word_info in result.alternatives[0].words:
                                #             f.write(
                                #                 f'{word_info.word: <40s}{word_info.start_time: <16.0f}'
                                #                 f'{word_info.end_time: <16.0f}'
                                #             )
                                #             if speaker_diarization:
                                #                 f.write(f'{word_info.speaker_tag: <16d}')
                                #                 words.append(word_info)
                                #             f.write('\n')
                            else:
                                partial_transcript += transcript
                        else:  # additional_info == 'confidence'
                            if result.is_final:
                                await ws.send_str(json.dumps({'predictions': {'results': transcript, 'confidence': result.alternatives[0].confidence}}))
                            else:
                                await ws.send_str(json.dumps({'predictions': {'results': transcript, 'stability': result.stability}}))
                    if additional_info == 'no':
                        if show_intermediate and partial_transcript != '':
                            overwrite_chars = ' ' * (num_chars_printed - len(partial_transcript))
                            await ws.send_str(json.dumps({'predictions': {'results': partial_transcript}}))
                            num_chars_printed = len(partial_transcript) + 3
                    elif additional_info == 'time':
                        if partial_transcript:
                            await ws.send_str(json.dumps({'predictions': {'results': partial_transcript, "time": time.time() - start_time}}))
            elif msg.type == WSMsgType.ERROR:
                logger.error(f"WebSocket error: {ws.exception()}")
        return ws

    async def run(self):
        logger.info("Starting NIM services...")
        start_nim_services()
        logger.info("Waiting 30s for init...")
        await asyncio.sleep(30)
        await self.nim.wait_ready()

        app = web.Application(client_max_size=50 * 1024 * 1024)
        app.router.add_get('/ping', self.ping)
        app.router.add_post('/invocations', self.handle_invocations)
        app.router.add_post('/invocations/http', self.handle_invocations_http)
        app.router.add_post('/invocations/grpc', self.handle_invocations_grpc)
        app.router.add_get('/invocations-bidirectional-stream', self.handle_websocket)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"Service ready on :{self.port}")
        while True:
            await asyncio.sleep(1)


async def main():
    try:
        app = App()
        await app.run()
    except Exception:
        logger.exception("Fatal error")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())

