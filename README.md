# ZONOS3 Mini on one M5 Ultra

Zyphra's [ZONOS3 Mini](https://huggingface.co/Zyphra/ZONOS3-Mini) text to speech, served by TensorFold's native
Metal engine on one Mac Studio M5 Ultra (256 GB). The release is read as published (revision `d2d142a8`): the
backbone's weights in bf16, the codec's in fp32, every activation, cache and sum in fp32. Nothing is converted.

**Status: not finished.** Speaking works and is measured below. Cloning a voice from a clip (`ref_audio`) is not on
Metal yet: the server answers it with HTTP 500 and "cloning from a clip (ref_audio) is not supported on Metal yet".
The engine branch (`zonos3-metal`, on top of ashhart/TensorFold#3720) is not pushed, so this recipe cannot be
rebuilt from its pins yet.

| What | Pin |
| --- | --- |
| Checkpoint | `Zyphra/ZONOS3-Mini` at `d2d142a86b1e6aeb4252679673c86ecd86177bf8` (Apache-2.0) |
| Engine | BobClawblaw/TensorFold `zonos3-metal` at `a6820a735` (not pushed), Zig 0.17.0 |

## Serving

    MODELS=/path/to/models TF_SRC=/path/to/TensorFold ./serve.sh     # the API on 127.0.0.1:30117
    MODELS=/path/to/models TF_SRC=/path/to/TensorFold ./run.sh       # the API and the engine's browser test page (:30118)

`TF_SRC` is a TensorFold checkout of the pinned commit built with `zig build native -Doptimize=ReleaseFast`, and
`MODELS` holds the release as `ZONOS3-Mini/`. One request is spoken at a time; one that arrives meanwhile gets 503.

    curl -s 127.0.0.1:30117/v1/audio/speech -H 'Content-Type: application/json' \
      -d '{"model": "zonos3-mini", "input": "The harbor was quiet this morning.", "voice": "rupert", "seed": 1}' -o reply.wav

The 27 voices of the release are listed at `/v1/voices`; `speaker_reference_codes` takes a voice's codes directly.
Replies are WAV or raw PCM (16-bit mono, 44.1 kHz), whole or streamed. Sampling fields are `temperature`, `top_p`,
`top_k` (1 to 4096) and `seed`.

## Measured

All on one M5 Ultra (256 GB, macOS 27.2), the binary built from `a6820a735`.

### Served, through the recipe harness

`python3 -m harness run zonos3-mini-m5 --plan speech` (run `20261117-131940-speech`): each case once, then twice whole
and twice streamed, after a server start.

| Case | Audio | Whole | Streamed first byte | Repeats and streams identical |
| --- | --- | --- | --- | --- |
| passage (Rupert, seed 11) | 17.8 s | 1.09 s (16.3 times real time) | 0.07 s | yes |
| short (default voice, seed 3) | 4.13 s | 0.28 s (14.6) | 0.06 s | yes |
| second voice (Imogen, seed 5) | 5.13 s | 0.35 s (14.8) | 0.06 s | yes |
| clone (`ref_audio`) | | HTTP 500, not on Metal yet | | |

- **Busy:** three requests at once answered 200, 503, 503, and the spoken one equalled the reply spoken alone.
- **Refusals:** an unknown voice, `top_k` 5000, a `ref_audio` that is no WAV, malformed `speaker_reference_codes` and
  empty input each got 400 with its reason.
- **The same seeds on the RTX 5090:** the three spoken cases have the same lengths as the
  [5090 recipe](https://github.com/BobClawblaw/zonos3-mini-rtx-5090)'s replies to the same requests, and their 16-bit
  samples differ by at most 2 in 0.1% of samples (SNR 90.5 to 98.2 dB): the Metal engine drew the same codes.
- **Memory:** the engine holds 3,828,402,944 bytes (3.57 GiB) after its load at `--context 4096` and 2,000 frames a
  request, the figure its admission counts in advance.
- **Not measured:** word error rate (the plan's ASR command is not set up on this Mac), and the quality suite.

### The parts against the reference

`zonos3-generate` (`zig build zonos3-generate -Doptimize=ReleaseFast`) against the publisher's PyTorch code run in fp32
on the CPU over the same weights; the dumps and their commands are in the engine's `docs/recipes/zonos3-mini.md`.

| Check | Result |
| --- | --- |
| Backbone, 30-row and 209-row prompts, 109 captures each | every row's cosine 1.0000000; worst relative difference 2.3e-6 and 5.0e-6 |
| Greedy frames, two voices, prompt chunks of 1, 7, 64 and 256 rows | 78 of 78 and 80 of 80 frames identical at every chunk size |
| Codec decoder, 171 frames, 13 captures | cosine 1.0000000, audio SNR 114.0 dB; decoded in chunks, bit-identical to one pass |
| Text to audio, two voices, greedy | prompt rows equal, every frame identical, 205,800 and 211,680 samples, SNR 102.7 and 106.7 dB |

Greedy decoding runs at about 350 frames a second (23 times real time) in the tool. No part of the engine is tuned.

## What this recipe does not do yet

- Clone from a clip: the codec encoder, the SSL teacher and the quantizer are not ported to Metal.
- MP3, Opus, AAC and FLAC replies and OpenAI's stock voice names: these are being added to the shared speech route
  (not Metal-specific) and arrive with the engine's next base.
- The Metal kernel contract records for the family's kernels.
