# NOUS Overleveringsdokument v1.9

**Dato:** 27. april 2026
**Forfatter:** Dan + Claude (assistance)
**Forrige version:** v1.8 (26. april 2026, sen aften)
**Sessioner foldet ind:** 5d (systemd service deployment)

---

## 1. Formål

v1.9 erstatter v1.8 fordi voice_assistant.py nu er deployet som persistent systemd service (nous-voice-assistant.service) der auto-starter ved boot. NOUS er gået fra demo-status til fast inventar.

Det er en signifikant milepæl: NOUS er nu et lokalt-hostet, dansktalende, always-on stemmeassistent-system der overlever reboots, kører i baggrunden, og responderer på "Hey Jarvis" når Pi 5 er tændt.

Ud over systemd-integrationen retter v1.9 et IP-dokumentationsmismatch: Pi 5 kører på 192.168.1.87 (ikke .150 som v1.7/v1.8 angav).

---

## 2. Hardware-arkitektur

### 2.1 Aktive enheder

| Enhed | Rolle | IP | Specs |
|---|---|---|---|
| Pi 5 16GB (Nous-Pi) | Sluse, RAG, TTS, proxy, ingest, wake-word, voice-orchestration | **192.168.1.87** (rettet) | 16GB RAM, ARM Cortex-A76 |
| Jetson Orin Nano 8GB | LLM-inference, STT | 192.168.1.100 | 8GB shared, 1024 CUDA |
| ReSpeaker XVF3800 | Mikrofon-array | USB Pi 5 (hw:2,0) | card 2, device 0, 2 ch |
| Speaker | Lyd ud | 3.5mm/USB Pi 5 | sox + ALSA 48kHz stereo |
| Seagate 1TB HDD | Backup | USB 3 Pi 5 | /mnt/backup-primary |
| Gigabit switch | Pi 5 ↔ Jetson | LAN | Dedikeret med uplink |

### 2.2 Air-gap

Jetson uden default route. Pi 5 = sluse via nous-proxy.

### 2.3 Hardware-opgradering

Jetson Orin NX 16GB anmodet via buddy. Når den kommer: Nano demoteres, NX overtager primær LLM + evt. whisper-large-v3.

---

## 3. Netværk

- Hovedrouter: 192.168.1.0/24
- **Pi 5: 192.168.1.87** (eth0, statisk reserveret i hovedrouter, verificeret stabil over reboots)
- Jetson: 192.168.1.100 (eth0, statisk reserveret)

**VIGTIGT:** v1.7 og v1.8 dokumenterede fejlagtigt Pi 5 på .150. Den faktiske og stabile IP er .87.

---

## 4. Services på Pi 5

### 4.1 nous-voice-assistant.service (NY i v1.9)

Persistent systemd service. Auto-starter ved boot. Restart on failure efter 5 sek. Verificeret end-to-end virker:
- Wake-word detection (scores 0.66-0.97)
- Spawn af voice_chat.py som subprocess
- Whisper STT på dansk via Jetson
- Qwen3-4B LLM med native tool-calling
- Piper TTS streaming via sox + ALSA
- Cooldown og retur til wake-word listening

Service-fil: `/etc/systemd/system/nous-voice-assistant.service`. Status: **enabled** (auto-start).

#### Fuld service-fil

```ini
[Unit]
Description=NOUS Voice Assistant (wake-word watchdog)
Documentation=file:///srv/nous/docs/NOUS_v1.9_Status.md
After=network-online.target sound.target nous-proxy.service
Wants=network-online.target nous-proxy.service
Requires=sound.target

[Service]
Type=simple
User=nous
Group=nous
SupplementaryGroups=audio input plugdev
WorkingDirectory=/srv/nous/scripts
Environment=PYTHONUNBUFFERED=1
Environment=HOME=/home/nous
Environment=PATH=/srv/nous/pipeline/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/srv/nous/pipeline/.venv/bin/python3 /srv/nous/scripts/voice_assistant.py
Restart=on-failure
RestartSec=5
TimeoutStopSec=10
StandardOutput=journal
StandardError=journal

# Security hardening
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=read-only
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

#### Designvalg

1. **Group=nous + SupplementaryGroups=audio input plugdev** - Hardware-permissions for ALSA + USB
2. **Restart=on-failure (ikke always)** - Forhindrer crash-loops ved ren exit
3. **Environment=PATH med venv først** - KRITISK: Uden dette finder service ikke piper/sox
4. **Environment=HOME=/home/nous** - openWakeWord cacher modeller i ~/.local/share/openwakeword/
5. **Requires=sound.target** - Forhindrer fejl-loops hvis lyd-system er nede
6. **ProtectHome=read-only + PrivateTmp=true** - Mild security hardening

#### Operationelle kommandoer

```bash
# Status
sudo systemctl status nous-voice-assistant.service

# Live logs
journalctl -u nous-voice-assistant.service -f

# Stop / start / restart
sudo systemctl stop nous-voice-assistant.service
sudo systemctl start nous-voice-assistant.service
sudo systemctl restart nous-voice-assistant.service

# Disable auto-start
sudo systemctl disable nous-voice-assistant.service
```

### 4.2 voice_assistant.py (uændret fra v1.8)

Wake-word watchdog. Ved detection: `stream.close()`, 0.8s ALSA release, Piper "Ja?" ack, voice_chat.py spawnes.

Konstanter: SAMPLE_RATE 16000, CHUNK_SIZE 1280, THRESHOLD 0.5, DEVICE_RELEASE_WAIT 0.8, COOLDOWN_SEC 2.0, SESSION_TIMEOUT 60.

### 4.3 voice_chat.py (uændret fra v1.8)

One-shot voice session. Eksplicit XVF3800 matching, Whisper temperature=0.0, LLM SYSTEM-prompt med STT-fejl-mønstre, "Brugeren hedder Dan".

### 4.4 nous-proxy (uændret)

Port 8090. /health /time /weather /search /fetch.

### 4.5 SearXNG (uændret)

Docker, localhost:8080.

### 4.6 Backup-pipeline (uændret)

Daglig 03:00 cron. GPG. /mnt/backup-primary.

---

## 5. Services på Jetson (uændret fra v1.8)

### 5.1 whisper-server (port 8080)
ggml-medium.bin. CUDA. --language da. RAM ~1.3GB.

### 5.2 llama-server (port 8081)
Qwen3-4B-Instruct-2507-Q4_K_M.gguf. CUDA 100% offload. Native tool-calling.

### 5.3 Headless mode
multi-user.target. ~1.5GB RAM frigjort.

---

## 6. Voice-pipeline

### 6.1 Komplet flow

```
ReSpeaker XVF3800 (Pi 5 hw:2,0)
    ↓
openWakeWord (hey_jarvis, threshold 0.5)
    ↓ [WAKE detected]
Stream close + 0.8s release wait
    ↓
Piper TTS "Ja?" (akustisk ack)
    ↓
voice_chat.py subprocess spawned
    ↓
Silero VAD (threshold 0.4, pre-roll 16 frames)
    ↓
Whisper STT (Jetson:8080, language=da, temp=0.0)
    ↓
llama-server (Jetson:8081, Qwen3-4B + tools + fuzzy SYSTEM)
    ↓
nous-proxy (Pi 5:8090, tool execution)
    ↓
Tekst-rensning
    ↓
Piper TTS streaming (da.onnx)
    ↓
sox + ALSA 48kHz stereo → speaker
    ↓
Subprocess afsluttes → cooldown 2.0s → ny stream
    ↓
Tilbage til wake-word listening
```

### 6.2 Performance benchmarks

| Trin | Tid |
|---|---|
| Service init (openWakeWord load) | ~2 sek |
| VAD detection start | < 100ms |
| Whisper-medium transkription | 1-2 sek for 5 sek audio |
| LLM tænkning + tool-call | 3-8 sek |
| TTS streaming start | ~2 sek efter LLM-svar |
| End-to-end voice query | 10-15 sek |
| Wake-word til "Ja?"-start | ~3 sek |

---

## 7. Tool-calling (uændret)

llama-server `/v1/chat/completions` med tools-parameter.

- `get_time` - aktuel dato/tid Danmark
- `get_weather(location)` - vejr dansk by
- `search_web(query)` - SearXNG

---

## 8. Privacy Guard og scopes (uændret)

DK_PHONE og DK_ADDRESS regex-issues er P1.

---

## 9. Software-stack (uændret)

### Pi 5
- Raspberry Pi OS Debian, kernel 6.12.75
- Python 3.13 i /srv/nous/pipeline/.venv
- fastapi, uvicorn, httpx, silero-vad 6.2.1, torch 2.11.0+cpu, sounddevice, piper, openwakeword 0.4.0

### Jetson
- Ubuntu 22.04 LTS, JetPack R36.5.0
- CUDA 12.6
- whisper.cpp + llama.cpp bygget fra source 26. april med GGML_CUDA=1

---

## 10. Hvad virker (verificeret end-to-end 27. april)

- ✅ Hardware-installation, air-gap, switch
- ✅ GPG-backup setup
- ✅ Whisper-medium STT på dansk
- ✅ llama-server med Qwen3-4B native tool-calling
- ✅ nous-proxy med 5 endpoints
- ✅ Voice-pipeline mikrofon → speaker
- ✅ Streaming TTS med pre-buffer
- ✅ Tekst-rensning før TTS
- ✅ VAD pre-roll
- ✅ Headless mode på Jetson
- ✅ ReSpeaker XVF3800 explicit matching
- ✅ openWakeWord wake-word detection
- ✅ voice_assistant.py watchdog
- ✅ ALSA device release timing
- ✅ LLM fuzzy-match SYSTEM-prompt
- ✅ Bruger-context "Dan" i LLM
- ✅ **nous-voice-assistant.service som persistent systemd (NYT)**
- ✅ **Auto-start ved boot enabled (NYT)**
- ✅ **PATH-environment med venv-bin (NYT)**
- ✅ **HOME-environment for openWakeWord cache (NYT)**
- ✅ **Restart on-failure med 5s delay (NYT)**
- ✅ **Pi 5 statisk IP .87 verificeret (NYT, korrektion fra v1.7/v1.8)**

---

## 11. Kendte begrænsninger og mitigationer

### 11.1 Whisper-medium på dansk samtaletale

Dokumenteret WER 12-18%. Observerede fejlmønstre:

| Sagt | Whisper transkriberede | Diagnose |
|---|---|---|
| sig noget sjovt | Si' noget job | Korte vokaler + sjældne ord |
| fortæl noget om Dan | Fortæl noget om Danmark | Frequency bias |
| fortæl noget om mig | Jeg vil fortælle | Hard ASR-fejl |
| sig noget sjovt | Se no other shot | Engelsk fallback |
| hvad er klokken | Hvad er klapen | Korte ord svage (NYT obs) |
| hvad laver du | Hvad laver du | Korrekt |

### 11.2 Mitigationer aktive

1. LLM fuzzy-match SYSTEM-prompt
2. Bruger-context "Brugeren hedder Dan"
3. Whisper temperature=0.0

### 11.3 Hvad mitigationerne ikke kan løse

Hard ASR-fejl. Kræver bedre STT-model. Whisper-large-v3 venter på Jetson NX 16GB.

### 11.4 Mikrofon-afstand

Wake-word: 1-2m fungerer godt. VAD i voice_chat: tydeligere tale ved 1.5m+. ReSpeaker firmware-gain-tuning planlagt efter NX-ankomst.

---

## 12. Hvad mangler

### P0 - Næste session
1. Streaming under LLM-generation (token-by-token til TTS)
2. Konsolidering af voice_assistant.py + voice_chat.py til én proces
3. VAD-tærskel justering for længere afstand

### P1 - Snart
4. Multi-model arkitektur (Base + Legacy + Legal)
5. Tidszone i /time
6. v1.6 → v1.9 reconciliation af scope-rules
7. Arducam IMX519 (kabel ankommet 27. april)
8. Fix DK_PHONE og DK_ADDRESS regex

### P2 - Hardware-afhængigt
9. NVMe-flytning af /srv/nous
10. Jetson NX 16GB ankomst
11. Whisper-large-v3 deployment
12. Multilingual-e5-large embeddings
13. XTTS-v2 voice-cloning

### P3 - Fremtid
14. Custom "Hey NOUS" wake-word træning
15. Legacy Engine med menneskelig verifikation
16. 3-node pilot WireGuard
17. Fine-tuning Legacy-model på SOUL.md
18. ACE refleksions-loop
19. Claude Code review

---

## 13. Genskabelses-procedure

### Hvis Pi 5 dør
1. Frisk Raspberry Pi OS, statisk IP .87
2. Restore GPG fra ThinkCentre eller paperkey
3. Mount Seagate → /mnt/backup-primary
4. Restore Qdrant fra GPG-backup
5. Geninstaller services (§4)
6. Re-deploy /srv/nous/
7. `pip install openwakeword`
8. **NYT:** Genoprett systemd service (se §4.1)
9. **NYT:** `sudo systemctl daemon-reload && sudo systemctl enable --now nous-voice-assistant.service`

### Hvis Jetson dør
1. Genflash JetPack R36.5.0
2. Build whisper.cpp og llama.cpp med GGML_CUDA=1
3. Kopier modeller
4. Geninstaller services (§5)
5. set-default multi-user.target

### Modeller
- ggml-medium.bin: huggingface.co/ggerganov/whisper.cpp
- Qwen3-4B-Instruct-2507-Q4_K_M.gguf: huggingface.co/unsloth
- Piper da.onnx: lokalt på backup-disk
- openWakeWord: auto-download

---

## 14. Kreditering

- Whisper (OpenAI / ggerganov whisper.cpp) - MIT
- llama.cpp (ggerganov) - MIT
- Piper TTS (Rhasspy) - MIT
- Qwen3 (Alibaba) - Apache 2.0
- Unsloth GGUF-quantization - MIT
- SearXNG - AGPL-3.0
- Qdrant - Apache 2.0
- FastAPI - MIT
- Silero VAD - MIT
- openWakeWord (David Scripka) - Apache 2.0
- Inspiration: jetson-orin-kian (aschweig) - MIT

---

## 15. Designprincipper bevaret fra v1.6

- Lokalt-først
- Privacy by default
- Air-gap
- Open source
- Familie-fokus (Legacy Engine)

---

## 16. Beslutninger truffet i deploy-sessionen

1. **Systemd service-arkitektur** - Type=simple, persistent, ikke user-service
2. **PATH-environment kritisk** - Uden venv-bin finder service ikke piper/sox
3. **Restart=on-failure** foretrukket over always
4. **Security hardening mildt** - ProtectSystem=full, ProtectHome=read-only, PrivateTmp=true. Stærkere ville bryde audio/netværk
5. **Pi 5 IP rettet** - .87 (faktisk) ikke .150 (tidligere fejlnoteret)
6. **Voice-pipeline forbliver subprocess-baseret** - Konsolidering udskudt til P0

---

## 17. Bilag: ReSpeaker XVF3800 (uændret)

| Felt | Værdi |
|---|---|
| sounddevice navn | `reSpeaker XVF3800 4-Mic Array: USB Audio (hw:2,0)` |
| ALSA card | 2 |
| ALSA device | 0 |
| max_input_channels | 2 (ch 0 = DSP mono, ch 1 = AEC ref) |
| default_samplerate | 48000 Hz |
| asound.conf default | respeaker_out (dmix på hw:2,0) |
| asound.conf ctl default | type hw, card 2 |

```python
if 'xvf3800' in d['name'].lower() or 'respeaker' in d['name'].lower()
```

---

## 18. Bilag: Systemd troubleshooting (NYT i v1.9)

### Fejl: FileNotFoundError: 'piper'
**Symptom:** Service kører, wake-word detekteres, men subprocess til piper fejler. Voice_chat session viser rc=1.
**Årsag:** Service uden venv aktiv. PATH inkluderer ikke venv-bin.
**Fix:** `Environment=PATH=/srv/nous/pipeline/.venv/bin:...` i service-fil.

### Fejl: ALSA device busy / Invalid number of channels
**Symptom:** voice_chat fejler ved Stream open. PaErrorCode -9998.
**Årsag:** voice_assistant holdt ALSA-handle ved kun stream.stop().
**Fix:** Implementeret i v1.8. stream.close() + del + 0.8s wait.

### Fejl: openWakeWord finder ikke modeller
**Symptom:** ImportError eller "could not load wakeword model".
**Årsag:** HOME ikke sat. openWakeWord cacher i ~/.local/share/openwakeword/.
**Fix:** `Environment=HOME=/home/nous`.

### Fejl: Permission denied på /dev/snd
**Symptom:** ALSA fejler ved device-åbning.
**Årsag:** Service-bruger ikke i 'audio' gruppe.
**Fix:** `SupplementaryGroups=audio input plugdev`.

### Debug-kommandoer

```bash
# Vis fuld service-config
sudo systemctl cat nous-voice-assistant.service

# Vis service environment
sudo systemctl show nous-voice-assistant.service -p Environment

# Live logs siden boot
journalctl -u nous-voice-assistant.service -b

# Test som service-bruger
sudo -u nous bash -c 'echo test | piper --model /srv/nous/models/tts/da.onnx --output_raw | sox -t raw -r 22050 -e signed-integer -b 16 -c 1 - -r 48000 -c 2 -t alsa default'

# Check fildscriptors / mikrofon-låsning
fuser /dev/snd/*

# Find zombier
pgrep -af voice_assistant
```
