# Mirror Mode Porting Notes

This document describes the moving parts needed to port mirror mode into another
HackerOoT-based project.

Mirror mode is implemented as a late framebuffer effect: draw the normal 3D
scene, copy it to a scratch buffer, draw it back horizontally flipped, then draw
readable screen-space elements afterward.

## Core Rendering Patch

Add project config flags:

```c
// Include mirror support in the build.
#define ENABLE_MIRROR_MODE true

// Optional: force mirror mode on, ignoring SaveContext.
#define FORCE_MIRROR_MODE false
```

Add a runtime guard alongside your other config safeguards:

```c
#if FORCE_MIRROR_MODE
    #define USE_MIRROR_MODE true
#else
    #define USE_MIRROR_MODE (ENABLE_MIRROR_MODE && gSaveContext.useMirrorMode == true)
#endif
```

Add `PreRender_MirrorFramebuffer(PreRender* this, Gfx** gfxP)` and declare it in
`include/prerender.h`.

The helper mirrors `this->fbufSave` into `this->fbuf` with S2DEX `uObjBg` and
`G_BG_FLAG_FLIPS`. This is preferable to flipping the projection matrix or using
a negative texture rectangle, which can break culling, text, and framebuffer
copies.

In `Play_Draw`, run the mirror pass after scene actors/effects have drawn and
before HUD, messages, title cards, and other readable overlay elements:

```c
this->pauseBgPreRender.fbuf = gfxCtx->curFrameBuffer;
this->pauseBgPreRender.fbufSave = (u16*)gWorkBuf;
PreRender_SaveFramebuffer(&this->pauseBgPreRender, &gfxP);
PreRender_MirrorFramebuffer(&this->pauseBgPreRender, &gfxP);
```

Disable or bypass motion blur while `USE_MIRROR_MODE` is true if both systems
use `gWorkBuf`. If the target project builds without motion blur, provide an
equivalent full-frame RGBA16 scratch buffer instead of reusing `gWorkBuf`.

Pause and game-over screens usually restore a captured gameplay framebuffer
behind their UI. Treat those as frozen-framebuffer modes: do not accept runtime
mirror toggles while the pause menu is open or while the pause prerender state is
active, and skip the normal late mirror pass while `IS_PAUSED` is true so the
pause UI stays readable. To keep the backdrop mirrored, leave the stock pause
capture path alone, restore the captured backdrop normally, copy that restored
image to the mirror scratch buffer, then mirror it behind the pause UI. Do not
mirror directly from the pause capture buffer on every target; debug/MQ builds
can route that buffer through coverage/debug framebuffer behavior and produce a
grayscale-looking backdrop. Do not CPU-mirror the saved `gZBuffer` image after
capture; the pause coverage/AA data will no longer match the color image and the
backdrop can develop severe artifacts. Also avoid running the S2DEX mirror pass
inside the pause capture setup frame, which can hang the graphics thread.
Otherwise the pause pages, prompts, and map/title textures can be mirrored after
the background restore, or the captured backdrop can fall out of sync with the
current mirror setting.

## Runtime Option

This branch stores the active mirror setting in session-level `SaveContext`,
outside the save payload:

```c
u8 useMirrorMode;
```

Initialize it to `false` in `SaveContext_Init`.

The quick in-game toggle mirrors the existing widescreen shortcut:

```c
if (ENABLE_MIRROR_MODE && CHECK_BTN_ALL(gameState->input[0].press.button, BTN_DLEFT) &&
    CHECK_BTN_ALL(gameState->input[0].cur.button, BTN_Z | BTN_R)) {
    gSaveContext.useMirrorMode ^= 1;
}
```

That makes `Z + R + D-Pad Left` toggle mirror mode at runtime, except while the
pause menu is open. A project that wants a real menu option can point the menu
setting at the same `gSaveContext.useMirrorMode` field. Keep the active flag
outside the loaded save payload if the player should be able to toggle mirror
mode across title demos, file select transitions, new-file intro cutscenes, and
other gamestate boundaries. The important part is that gameplay systems check
`USE_MIRROR_MODE`, not only the compile-time `ENABLE_MIRROR_MODE`.

## Draw Order Rule

The important rule is:

```text
mirror world/camera visuals
do not mirror readable screen-space visuals
```

Anything drawn before `PreRender_MirrorFramebuffer` will be flipped. Anything
drawn after it will remain readable.

Audit these categories in each project:

- HUD and item buttons
- Message boxes and text
- Scene title cards
- Boss name cards
- Title logo and title-screen text
- Custom mod overlays
- Debug overlays and FPS counters

In this branch, actor title cards are deferred through `Actor_DrawTitleCard`.
The title logo actor (`ACTOR_EN_MAG`) is skipped during the pre-mirror actor pass
whenever mirror mode is active and redrawn after the mirror pass. Do not key
that skip only on the title-screen game mode, because `En_Mag` switches the next
game mode before the title actor is actually gone.

If a project has custom readable overlays drawn from actor code, they may need
the same treatment.

## Controls

Because the visible world is mirrored, horizontal gameplay input should be
mirrored too.

The central player movement path is `Lib_GetControlStickData`; mirror `relX`
there:

```c
#if ENABLE_MIRROR_MODE
if (USE_MIRROR_MODE) {
    relX = -relX;
}
#endif
```

Also audit raw `rel.stick_x` users that bypass the central player helper. In
this branch, the important raw paths are:

- first-person / aiming behavior in `z_player.c`
- horse steering in `z_en_horse.c`
- fishing rod and lure control in `z_fishing.c`
- shop shelf/cursor browsing in `z_en_ossan.c`

Do not globally flip `Input.rel.stick_x` in the pad manager unless the project
wants menus, file select, pause screens, text entry, and debug tools mirrored
too. Most projects should only flip gameplay-facing reads.

## Spatial Audio

Mirror positional SFX pan so a sound on the mirrored left side comes from the
left speaker.

In the central SFX property setup, after computing pan:

```c
pan = Audio_ComputeSfxPanSigned(*entry->posX, *entry->posZ, entry->token);
#if ENABLE_MIRROR_MODE
if (USE_MIRROR_MODE) {
    pan = 0x80 - pan;
}
#endif
```

This keeps centered sounds centered and swaps left/right positional sounds.

## Porting Checklist

1. Add `ENABLE_MIRROR_MODE`, optional `FORCE_MIRROR_MODE`, and runtime
   `USE_MIRROR_MODE`.
2. Add a session setting such as `gSaveContext.useMirrorMode`.
3. Add an in-game toggle or menu option that changes the session setting.
4. Add and declare `PreRender_MirrorFramebuffer`.
5. Hook the mirror pass late in `Play_Draw`, before overlay/HUD/message drawing,
   and run it on normal gameplay frames while `USE_MIRROR_MODE` is true.
6. Disable conflicting motion blur framebuffer reuse while `USE_MIRROR_MODE`.
7. Defer title cards, boss name cards, and readable overlays until after mirror.
8. Handle title-screen logo/text separately if they are actor-drawn.
9. Mirror player movement stick X in the central movement helper.
10. Audit and mirror raw gameplay `rel.stick_x` paths.
11. Mirror positional SFX pan.
12. Test title screen, file select, scene title cards, boss title cards, HUD,
    messages, aiming, riding, minigames, and positional enemy sounds.

## Known Things To Test Carefully

- Prerendered rooms and fixed-camera scenes
- Pause background capture
- Transitions and screen fills
- Any mod-added 2D actor effects with text or logos
- Minigames with custom analog stick handling
- Surround/headset audio modes

If something is readable text and it appears backward, it is being drawn too
early. Move that draw later or exclude it from the pre-mirror framebuffer.

If movement feels backward, find the code path reading raw stick X and mirror it
only for gameplay.
