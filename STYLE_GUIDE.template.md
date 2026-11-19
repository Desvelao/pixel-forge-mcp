# Style guide (copy to STYLE_GUIDE.md in your project and edit)

Claude reads this before drawing any sprite. Keeping it short and concrete is what keeps the art consistent.

## Technical
- Sprite sizes: characters 32x32, items 16x16, tiles 16x16, big enemies 64x64 (pick and stick to them)
- Palette: `db16` (DawnBringer 16). Swap for `pico8` or a custom hex list in `new_sprite(palette=[...])`
- Transparent background, no semi-transparency, 1px empty margin around every sprite
- Game camera: 3/4 top-down  (or: side view)

## Look
- Mood: <e.g. cozy, warm, slightly spooky, hand-drawn>
- Outline: 1px, dark palette color `p0` (no pure black), outside only
- Light direction: top-left (always). Highlights top-left, shadows bottom-right
- Shading: 3 tones per material (shadow / base / highlight), no dithering, no gradients
- Eyes: 2x2 px white with 1px dark pupil, characters look slightly to the facing side
- Proportions: big head, short body (chibi, about 1:1.5) so faces read at 2x size

## Naming
- Static: `<thing>` e.g. `tree_pine`
- Animated frames: `<char>_<anim><n>` e.g. `hero_walk0`..`hero_walk3`
- Godot path: `res://assets/sprites/`

## Reference sprites
Add the names of 1-3 finished sprites you love here. Claude will `preview` them and match their style:
- (none yet, the first sprite you approve becomes the reference)
