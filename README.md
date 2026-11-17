# ZONOS3 Mini on one M5 Ultra

Zyphra's [ZONOS3 Mini](https://huggingface.co/Zyphra/ZONOS3-Mini) text to speech, served by TensorFold's native
Metal engine on one Mac Studio M5 Ultra (256 GB) through an OpenAI-style `/v1/audio/speech`. The release is read as
published (revision `d2d142a8`): the backbone's and the SSL teacher's weights in bf16, the codec's in fp32, every
activation, cache and sum in fp32. Nothing is converted.

It speaks in the release's 27 voices, clones a voice from a clip, and answers in WAV, PCM, FLAC, MP3, Opus or AAC.

The engine branch (`zonos3-metal`, on top of ashhart/TensorFold#3720 and its reply-format branch `zonos3-openai`)
is not pushed yet, so this recipe cannot be rebuilt from its pins by anyone else yet.

| What | Pin |
| --- | --- |
| Checkpoint | `Zyphra/ZONOS3-Mini` at `d2d142a86b1e6aeb4252679673c86ecd86177bf8` (Apache-2.0) |
| Engine | BobClawblaw/TensorFold `zonos3-metal` at `796b1565e` (not pushed), Zig 0.17.0 |

## Serving

    MODELS=/path/to/models TF_SRC=/path/to/TensorFold ./serve.sh     # the API on 127.0.0.1:30117
    MODELS=/path/to/models TF_SRC=/path/to/TensorFold ./run.sh       # the API and the engine's browser test page (:30118)

`TF_SRC` is a TensorFold checkout of the pinned commit built with `zig build native -Doptimize=ReleaseFast`, and
`MODELS` holds the release as `ZONOS3-Mini/` (`lm/`, `autoencoder/`, `registries/`, `gguf/voices/`,
`speaker_encoders/`). One request is spoken at a time; one that arrives meanwhile gets 503.

    curl -s 127.0.0.1:30117/v1/audio/speech -H 'Content-Type: application/json' \
      -d '{"model": "zonos3-mini", "input": "The harbor was quiet this morning.", "voice": "rupert", "seed": 1}' -o reply.wav

- **Voices:** the release's 27 are listed at `/v1/voices`. OpenAI's stock names (`alloy`, `nova`, ...) speak in the
  default voice; `speaker_reference_codes` takes a voice's codes directly.
- **Cloning:** `ref_audio` is a base64 WAV clip, half a second to 60 s (longer is cut at 60 s). The first clip loads
  the clip encoder (about 7 s, 5.26 GiB more); it then stays loaded.
- **Formats:** `response_format` is `wav` (the default), `pcm`, `flac`, `mp3`, `opus` or `aac`, at 44.1 kHz mono
  (Opus at 48 kHz). MP3, Opus and AAC need LAME, libopus and FDK AAC, which the server finds in Homebrew
  (`brew install lame opus fdk-aac`); the others need nothing. `"stream": true` takes `pcm`, and a `pcm` reply names
  its rate in `X-Audio-Sample-Rate`.
- **Sampling:** `temperature`, `top_p`, `top_k` (1 to 4096) and `seed`.

### Kept running, and Hermes

On the measured Mac the server runs as a LaunchAgent (`KeepAlive`, its own copy of the binary, `127.0.0.1:30120`,
the same arguments as `serve.sh`), and Hermes speaks through it with its OpenAI provider:

```yaml
tts:
  provider: openai
  streaming:
    provider: openai
  openai:
    api_key: local            # any value; the server has no key
    base_url: http://127.0.0.1:30120/v1
    model: zonos3-mini
    voice: rupert             # one of /v1/voices
    pcm_sample_rate: 44100
```

Through Hermes's own TTS code: MP3 and Ogg Opus files, and its PCM streamer (6.2 s of audio in 10 chunks at 44.1
kHz).

## Measured

All on one M5 Ultra (256 GB, macOS 27.2), the binary built from `796b1565e`.

### Served, through the recipe harness

`python3 -m harness run zonos3-mini-m5 --plan speech` (run `20261117-134557-speech`, files in `evidence/`): each
case once after a server start, then twice whole and twice streamed.

| Case | Audio | Whole | Streamed first byte | Repeats and streams identical |
| --- | --- | --- | --- | --- |
| passage (Rupert, seed 11) | 17.8 s | 0.93 s (19.1 times real time) | 0.07 s | yes |
| short (default voice, seed 3) | 4.13 s | 0.25 s (16.7) | 0.06 s | yes |
| second voice (Imogen, seed 5) | 5.13 s | 0.30 s (17.1) | 0.06 s | yes |
| clone (the short reply as the clip, seed 4) | 5.13 s | 1.31 s (3.9) | 1.05 s | yes |

- **Clone:** its first request took 9.16 s, the clip encoder's load included. A clip is encoded whole before the
  first frame, so its first streamed byte comes after the encoding.
- **Busy:** three requests at once answered 200, 503, 503, and the spoken one equalled the reply spoken alone.
- **Refusals:** an unknown voice, `top_k` 5000, a `ref_audio` that is no WAV, malformed `speaker_reference_codes` and
  empty input each got 400 with its reason.
- **The same requests on the RTX 5090:** all four replies have the same lengths as the
  [5090 recipe](https://github.com/BobClawblaw/zonos3-mini-rtx-5090)'s, and their 16-bit samples differ by at most 2
  (SNR 90.5 to 98.2 dB, the clone 93.1 dB): Metal drew the same codes.
- **Memory:** 3,828,402,944 bytes (3.57 GiB) after the load at `--context 4096` and 2,000 frames a request, and
  9,471,914,240 bytes (8.82 GiB) with the clip encoder: each the figure the server admits in advance.
- **Formats:** each of the six answered 200 with its type; the FLAC reply decodes to the `pcm` reply's bytes exactly.
- **Not measured:** word error rate (the plan's transcriber is not set up on this Mac), and the quality suite.

### The parts against the reference

`zonos3-generate` (`zig build zonos3-generate -Doptimize=ReleaseFast`) against the publisher's PyTorch code run in fp32
on the CPU over the same weights; the dumps and their commands are in the engine's `docs/recipes/zonos3-mini.md`.

| Check | Result |
| --- | --- |
| Backbone, 30-row and 209-row prompts, 109 captures each | every row's cosine 1.0000000; worst relative difference 2.3e-6 and 5.0e-6 |
| Greedy frames, two voices, prompt chunks of 1, 7, 64 and 256 rows | 78 of 78 and 80 of 80 frames identical at every chunk size |
| Codec decoder, 171 frames, 13 captures | cosine 1.0000000, audio SNR 114.0 dB; decoded in chunks, bit-identical to one pass |
| Text to audio, two voices, greedy | prompt rows equal, every frame identical, SNR 102.7 and 106.7 dB |
| Teacher's features (host), 999 rows | cosine 1.0000000, largest difference 2.4e-7 |
| Encoder, acoustic branch, 101 captures, 145 frames | every row's cosine 1.000000 |
| SSL teacher, 18 captures, 999 rows | worst row's cosine 0.9999253 |
| Clip to codes, one lane (145 frames) and four lanes (710 frames) | 1,450 of 1,450 and 7,100 of 7,100 codes equal |

All 40 of the family's Metal kernels are registered with TensorFold's kernel contract (engine commit `e0299a671`,
which changes no output): `tf-kernel-contract --only zonos3` on this Mac gives 41 of 41 registrations through gates 1
to 4, all 41 planted controls red, and no launch-limit problems on M1 to M5.

Greedy decoding runs at about 350 to 390 frames a second (23 to 26 times real time) in the tool; a 47 s clip encodes
in 8.9 s. No part of the engine is tuned for speed.

## What this recipe does not do yet

- Word error rate on this Mac.
