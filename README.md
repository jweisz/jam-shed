# Jam Shed 🎸🥁

**Jam Shed** is an AI-powered interactive music jamming application that lets you jam with virtual musicians. Play your MIDI instrument and watch AI agents respond in real-time, learn your grooves, and trade solos with you.

## Features

- 🎵 **Real-time MIDI jamming** with AI virtual musicians
- 🧠 **Rhythmic learning** - AI learns from your playing patterns
- 🎭 **Multiple virtual instrumentalists**: Bass, Lead Guitar, Rhythm Guitar, Keys
- 🎨 **Musical styles**: Rock, Jazz, Hip-Hop, Blues, Funk, Latin
- 🔄 **Trading solos** with AI agents in structured jam sessions
- 📊 **Visual groove patterns** - see what you and the AI are playing
- 🎼 **Music theory integration** - scales, chords, progressions
- 🖥️ **TUI Interface** powered by Textual

## Requirements

- Python 3.11+
- MIDI input device (keyboard, drum pads, etc.)
- macOS, Linux, or Windows

## Installation

### Using `uv` (recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/jam-shed.git
cd jam-shed

# Install with uv
uv pip install -e .

# Download soundfonts (optional, for local audio playback)
uv run python scripts/download_soundfonts.py
```

### Using `pip`

```bash
pip install -e .
python scripts/download_soundfonts.py
```

## Quick Start

1. **Connect your MIDI device** (keyboard, drum pads, etc.)

2. **Launch the app:**
```bash
uv run python -m jam_shed.tui.app
# or if installed globally:
# python -m jam_shed.tui.app
```

3. **Configure MIDI**:
   - Select your MIDI input device from the dropdown
   - Choose MIDI output (use "Local (Fluidsynth)" for built-in audio)
   - Click "Connect" for both

4. **Start jamming**:
   - Choose "Shed" mode to practice and have AI learn
   - Enable virtual agents (Bass, Lead Guitar, Rhythm Guitar, Keys)
   - Select a musical key and scale
   - Start playing - AI will listen and respond!

## Modes

### Shed Mode
Practice mode where AI agents listen to your playing and learn your grooves. The AI builds rhythmic patterns based on your performance and can play them back.

### Jam Mode
(Coming soon) Full band coordination with structured trading and call-and-response.

## AI Virtual Musicians

All virtual instrumentalists inherit from `VirtualInstrumentalist` and can be configured with different playing styles:

- **VirtualBassist** - Lays down the low end with 8th note grooves
- **VirtualLeadGuitarist** - Takes solos with 16th note runs
- **VirtualRhythmGuitarist** - Provides rhythm with chord strums
- **VirtualKeyboardist** (coming soon) - Adds harmonic color
- **VirtualDrummer** (coming soon) - Drives the rhythm section

### Musical Styles

Each agent can play in different styles that affect their playing characteristics:
- **Rock** - Straight-ahead, driving rhythms
- **Jazz** - Complex, syncopated patterns
- **Hip-Hop** - Laid-back, groove-oriented
- **Blues** - Swing feel with space
- **Funk** - Tight, rhythmic emphasis
- **Latin** - Clave-based patterns

## Project Structure

```
jam-shed/
├── src/jam_shed/
│   ├── agent.py          # Virtual instrumentalist classes
│   ├── app.py            # Main Textual TUI application
│   ├── audio.py          # FluidSynth audio engine
│   ├── brain.py          # Rhythmic learning system
│   ├── midi_engine.py    # MIDI I/O handling
│   ├── session.py        # Jam session management
│   └── theory.py         # Music theory (scales, chords)
├── scripts/
│   └── download_soundfonts.py
├── tests/                # (coming soon)
└── README.md
```

## Development

### Running from source

```bash
# Install in development mode
uv pip install -e .

# Run the app
uv run python -m jam_shed.tui.app
```

### Running tests

```bash
pytest tests/ -v
```

## How It Works

1. **MIDI Input**: Your MIDI device sends note and timing information
2. **Rhythmic Brain**: Analyzes timing and builds groove patterns from your playing
3. **Music Theory**: Determines appropriate notes based on key/scale/chord
4. **Virtual Agents**: AI musicians respond using learned patterns and musical context
5. **MIDI Output**: Sends notes to your synthesizer or built-in FluidSynth

## Troubleshooting

**MIDI device not showing up?**
- Make sure your MIDI device is connected before launching the app
- On macOS, check Audio MIDI Setup to verify the device is recognized
- Try restarting the app after connecting the device

**No sound?**
- If using "Local (Fluidsynth)", make sure soundfonts are downloaded
- Check that your MIDI output device has sound enabled
- Verify volume levels in your system and on the output device

**Agents not playing?**
- Make sure you've enabled agents via the checkboxes
- Verify MIDI output is connected
- Check that you're in Shed mode and have started playing

## Contributing

Contributions welcome! Please feel free to submit issues or pull requests.

##License

MIT License - see LICENSE file for details

## Credits

Built with:
- [Textual](https://textual.textualize.io/) - TUI framework
- [python-rtmidi](https://spotlightkid.github.io/python-rtmidi/) - MIDI I/O
- [FluidSynth](https://www.fluidsynth.org/) - Software synthesizer

---

**Happy Jamming! 🎶**
