; ADOFAI official-world packs. Eight MiB ExHiROM, stock 65816/PPU/SPC700.
.p816
.smart -
.macro jeq target
 bne :+
 jmp target
:
.endmacro
.macro jne target
 beq :+
 jmp target
:
.endmacro
.macro jcc target
 bcs :+
 jmp target
:
.endmacro
.macro jcs target
 bcc :+
 jmp target
:
.endmacro
.include "addresses.inc"
.macro start_dma channel
.ifdef NEO_BUILD
.if channel = 1
    lda DMA_COMMANDS
.elseif channel = 16
    lda DMA_COMMANDS+2
.elseif channel = 32
    lda DMA_COMMANDS+4
.else
    .error "Unsupported DMA command slot"
.endif
.else
    lda #$C000|channel
.endif
    sta $420B
.endmacro
.macro data_read8
.ifdef ROM_DATA_BUILD
    lda [rom_data_ptr]
    inc rom_data_ptr
    bne :+
    inc rom_data_ptr+1
    bne :+
    inc rom_data_ptr+2
.ifdef SA1_BUILD
    bne :+
    pha
    jsr sa1_next_rom_page
    pla
.endif
:
.else
    lda $2001
.endif
.endmacro
.ifndef MAX_NOTE_CAPACITY
MAX_NOTE_CAPACITY=2048
.endif
.ifndef MAP_OFFSET_SHIFT
MAP_OFFSET_SHIFT=0
.endif
.ifdef SA1_BUILD
M7_SHARED_BASE=$410000
.else
M7_SHARED_BASE=$7F0000
.endif
OAM=$0200
DMA_COMMANDS=$0778
.ifdef MSU_BUILD
BEST_SCORES=$7FDC00
.else
BEST_SCORES=$0700
.endif
DESC=$0460
.ifdef SA1_WRAM_RENDERER
HUD=$6800
.else
HUD=$0800
.endif
TRACK=$1000
.ifdef SA1_BUILD
TRACK_SYMBOL_FLOORS=$40A000
.assert TRACK_SYMBOL_FLOORS+4352*2 <= $40C800, error, "Track symbol index overlaps pause data"
.endif
.ifdef MSU_BUILD
.ifdef LARGE_CHART_BUILD
; Keep moving coordinates in DMA-accessible WRAM. Each array reserves
; $2200 bytes for 4352 floors; the high CHR shadow moves into the gap
; between cell state and the audio FIFO. Pause/judgments stay in BW-RAM.
NOTE_X=$7F8000
NOTE_Y=$7FA200
NOTE_PAUSE=$40C800
NOTE_JUDGMENTS=$40EA00
NOTE_TIME=$7E2000
NOTE_ANGLE=$7E4200
NOTE_FLAGS=$7E5300
NOTE_RATE=$7E6400
NOTE_PROGRESS=$7E8600
NOTE_CCW=$7E9700
.else
NOTE_X=$7E2000
NOTE_Y=$7E3800
NOTE_TIME=$7E5000
NOTE_ANGLE=$7E6800
NOTE_FLAGS=$7E7400
NOTE_RATE=$7E8000
NOTE_PROGRESS=$7E9800
NOTE_CCW=$7EA400
NOTE_PAUSE=$7EB000
NOTE_JUDGMENTS=$7FCC00
.endif
CHECKPOINTS=$7FD800
DYNAMIC_CACHE=$7EC800
DYNAMIC_NEXT=$7FF000
.else
NOTE_X=$7E2000
NOTE_Y=$7E3000
NOTE_TIME=$7E4000
NOTE_ANGLE=$7E5000
NOTE_FLAGS=$7E5800
NOTE_RATE=$7E6000
NOTE_PROGRESS=$7E7000
NOTE_CCW=$7E7800
NOTE_PAUSE=$7E8000
NOTE_JUDGMENTS=$7EA000
CHECKPOINTS=$7E9000
DYNAMIC_CACHE=$7EC000
DYNAMIC_NEXT=$7EC800
.endif
MAP_RAM=$7F0000
POSITION_X=$7F0000
POSITION_Y=$7F2000
POSITION_NEXT_X=$7F4000
POSITION_NEXT_Y=$7F6000
CELL_STATE=$7F0000
.ifdef LARGE_CHART_BUILD
FLOOR_ALPHA=$7EA800
.else
FLOOR_ALPHA=$7FE000
.endif
PATTERN_CURRENT=M7_SHARED_BASE+$F800
PATTERN_NEXT=$7F8800
.ifdef MSU_BUILD
.ifdef SA1_BUILD
PATTERN_QUEUE=$416E00
.else
PATTERN_QUEUE=$417C00
.endif
.else
PATTERN_QUEUE=$7EF000
.endif
CELL_HASH_HEAD=$7ED000
CELL_HASH_NEXT=$7ED800
PATTERN_QUEUE_LOOKUP=$7EE000
M7_MAP=M7_SHARED_BASE+$8000
.ifdef MSU_BUILD
m7_cell_x=cell_hash_key
m7_cell_y=cell_hash_slot
.endif
M7_RUN_VALUES=$7FC880
M7_DIRTY_BITS=M7_SHARED_BASE+$C800
.ifdef SA1_BUILD
M7_DMA_LIST=$408000
.else
M7_DMA_LIST=M7_SHARED_BASE+$C900
.endif
M7_DIRTY_BOUNDS=M7_SHARED_BASE+$CA00
M7_CHR_LOW=$7EC800
.ifdef LARGE_CHART_BUILD
M7_CHR_HIGH=$7F6800
.else
M7_CHR_HIGH=$7FC000
.endif
.export NOTE_X, NOTE_Y, M7_CHR_HIGH
M7_PATTERN_HEAP=M7_SHARED_BASE+$F000
M7_PATTERN_DEADLINE=M7_SHARED_BASE+$F200
M7_PATTERN_POSITION=M7_SHARED_BASE+$F400
M7_PATTERN_SELECTED=M7_SHARED_BASE+$F600
M7_PATTERN_RELEASE=M7_SHARED_BASE+$6600
M7_PATTERN_VRAM=M7_SHARED_BASE+$6800
M7_VISIBLE_PATTERNS=M7_SHARED_BASE+$6A00
.ifdef SA1_BUILD
M7_STAGE_MAP=$404000
M7_STAGE_MASK=$3FFF
M7_ROT_COS=$41FCB0
M7_ROT_SIN=$41FCB2
M7_ROT_DISPLAY_COS=$41FCB4
M7_ROT_DISPLAY_SIN=$41FCB6
M7_VIEW_X=$41FCB8
M7_VIEW_Y=$41FCBA
M7_VIEW_W=$41FCBC
M7_VIEW_H=$41FCBE
M7_ROT_PHASE=$41FCC0
M7_ROT_DISPLAY_PHASE=$41FCC2
M7_SNAPSHOT_EXTRA=$41FCC4
M7_UPLOAD_LIMIT=$41FCC6
M7_DISPLAY_BASE_X=$41FCC8
M7_DISPLAY_BASE_Y=$41FCCA
M7_PROJECT_COS=$41FCCC
M7_PROJECT_SIN=$41FCCE
M7_RASTER_SHIFT=$41FCD0
M7_RASTER_X=$41FCD2
M7_RASTER_Y=$41FCD4
M7_RASTER_DISPLAY_X=$41FCD6
M7_RASTER_DISPLAY_Y=$41FCD8
M7_ORIGIN_X=$41FCDA
M7_ORIGIN_Y=$41FCDC
VBLANK_DIAG_ROWS=$41FCDE
VBLANK_DIAG_SPAN=$41FCE0
VBLANK_DIAG_SLOTS=$41FCE2
VBLANK_DIAG_LIMIT=$41FCE4
ROT_X=$400020
ROT_Y=$400022
ROT_SUM=$400024
ROT_SIGN=$400026
ROT_VALUE=$400028
ROT_FACTOR=$40002A
.else
M7_STAGE_MAP=M7_SHARED_BASE+$6C00
M7_STAGE_MASK=$0FFF
.endif
M7_LOGICAL_TO_PPU=M7_SHARED_BASE+$F000
M7_DISPLAY_TO_PPU=M7_SHARED_BASE+$F100
M7_NEW_VISIBLE=M7_SHARED_BASE+$F400
M7_OLD_VISIBLE=M7_SHARED_BASE+$F500
M7_CACHE_READY=M7_SHARED_BASE+$FC46
M7_CACHE_SCAN=M7_SHARED_BASE+$FC48
M7_CACHE_FREE=M7_SHARED_BASE+$FC4A
M7_CACHE_REMAIN=M7_SHARED_BASE+$FC4C
M7_CACHE_FINAL=M7_SHARED_BASE+$FC4E
M7_CACHE_ERRORS=M7_SHARED_BASE+$FC50
M7_CACHE_WAIT=M7_SHARED_BASE+$FC52
M7_CACHE_MAX_VISIBLE=M7_SHARED_BASE+$FC54
M7_CACHE_LOGICAL=M7_SHARED_BASE+$FC56
M7_CACHE_PHYSICAL=M7_SHARED_BASE+$FC58
M7_CACHE_ATOMIC=M7_SHARED_BASE+$FC5A
M7_CACHE_ABORT=M7_SHARED_BASE+$FC5C
M7_CACHE_BUDGET=M7_SHARED_BASE+$FC5E
AUDIO_FIFO=$7F7C00
.assert M7_BITMAP_BUFFER+64 <= AUDIO_FIFO, error, "Bitmap scratch overlaps audio"
AUDIO_FIFO_HEAD=$7FFC60
AUDIO_FIFO_TAIL=$7FFC62
AUDIO_PACKET_INFLIGHT=$7FFC64
AUDIO_FIFO_PACKETS=$7FFC66
AUDIO_FIFO_BYTES=$7FFC68
AUDIO_FIFO_FREE=$7FFC6A
CAMERA_FOLLOW_TICK=$7FFC6C
CAMERA_FOLLOW_STEPS=$7FFC6E
M7_CACHE_ACTIVE_COUNT=M7_SHARED_BASE+$FC70
M7_CACHE_ACTIVE_CURSOR=M7_SHARED_BASE+$FC72
M7_VISIBLE_LIST=M7_SHARED_BASE+$6B00
CAMERA_SCRIPT_X=$7FFC74
CAMERA_SCRIPT_Y=$7FFC76
CAMERA_SCRIPT_ACTIVE=$7FFC78
M7_CACHE_DIRTY=M7_SHARED_BASE+$FC7A
M7_CACHE_LOCAL_X=M7_SHARED_BASE+$FC7C
M7_CACHE_LOCAL_Y=M7_SHARED_BASE+$FC7E
M7_CACHE_LOCAL_W=M7_SHARED_BASE+$FC80
M7_CACHE_LOCAL_H=M7_SHARED_BASE+$FC82
M7_CACHE_TARGET_X=M7_SHARED_BASE+$FC84
M7_CACHE_TARGET_Y=M7_SHARED_BASE+$FC86
M7_CACHE_UNCHANGED=M7_SHARED_BASE+$FC88
M7_CACHE_RESET_SERIAL=M7_SHARED_BASE+$FCF0
M7_CACHE_SERIAL_SEEN=$416C7C
M7_RESIDENT_HASH=M7_SHARED_BASE+$F200
M7_RESIDENT_NEXT=M7_SHARED_BASE+$6600
M7_GLOBAL_REFS_ACTIVE=M7_SHARED_BASE+$FC8A
M7_REFERENCE_SLOT=M7_SHARED_BASE+$FC8C
M7_REFERENCE_INDEX=M7_SHARED_BASE+$FC8E
M7_TRANSITION_DEFERRALS=M7_SHARED_BASE+$FC90
M7_POOL_DIRTY=M7_SHARED_BASE+$FC92
M7_HASH_DIRTY=M7_SHARED_BASE+$FC94
M7_MASKS_CHANGED=M7_SHARED_BASE+$FC96
M7_STAGE_BASE_X=M7_SHARED_BASE+$FC98
M7_STAGE_BASE_Y=M7_SHARED_BASE+$FC9A
M7_STAGE_FIRST=M7_SHARED_BASE+$FC9C
M7_STAGE_FORCE=M7_SHARED_BASE+$FC9E
M7_IDENTITY_MODE=M7_SHARED_BASE+$FCA0
M7_DIRECT_COUNT=M7_SHARED_BASE+$FCA2
M7_RENDER_TIME=M7_SHARED_BASE+$FCA4
M7_EXPOSE_FIRST=M7_SHARED_BASE+$FCA6
M7_EXPOSE_END=M7_SHARED_BASE+$FCA8
OAM_PREVIOUS_COUNT=$41FCAE
SYMBOL_MIN_X=$416C00
SYMBOL_MIN_Y=$416C02
SYMBOL_WIDTH_X=$416C04
SYMBOL_WIDTH_Y=$416C06
SYMBOL_VISIBLE_COUNT=$416C08
SYMBOL_COORDS_DIRTY=$416C0A
SYMBOL_DIRTY_BEGIN=$416C0C
SYMBOL_DIRTY_END=$416C0E
M7_BITMAP_HEAD=$416C10
M7_BITMAP_TAIL=$416C12
M7_BITMAP_ENABLED=$416C14
M7_BITMAP_TAG=$416C16
M7_BITMAP_DEADLINE=$416C18
M7_BITMAP_CURSOR=$416C1A
M7_BITMAP_CHOICE=$416C1C
M7_BITMAP_BEST=$416C1E
M7_BITMAP_EXPIRES=$416C20
M7_TAG_COUNT=$416C22
M7_PATTERN_RUN_COUNT=$416C24
M7_PATTERN_STAGE=$434000
M7_PATTERN_RUNS=$438000
M7_PATTERN_DIRTY=$438400
M7_BITMAP_META=$420000
M7_FUTURE_DEADLINES=$417600
M7_FUTURE_TAGS=$417800
M7_BITMAP_BUFFER=$7F7000
M7_BITMAP_SRAM=$424000
M7_BITMAP_COUNT=1024
SPILL_TAGS=$438800
SPILL_DEADLINES=$438900
SPILL_OLD=$438A00
SPILL_NEW=$438A80
SPILL_LOGICAL=$438B00
SPILL_FRAME=$438C00
SPILL_CHR=$439000
SPILL_QUEUE=$43A000
SPILL_QUEUED=$43A100
SPILL_COUNT=$416C30
SPILL_VISIBLE=$416C32
SPILL_CHOICE=$416C34
SPILL_BEST=$416C36
SPILL_SCAN=$416C38
SPILL_PLANE0=$416C3A
SPILL_PLANE1=$416C3C
SPILL_X=$416C3E
SPILL_Y=$416C40
SPILL_COL=$416C42
SPILL_ROW=$416C44
SPILL_REMAIN=$416C46
SPILL_TILE=$416C48
SPILL_DRAW_CURSOR=$416C4A
M7_SPILL_ELIGIBLE=$416C50
SPILL_ENABLED=$416C4C
SPILL_QUEUE_INDEX=$416C4E
SPILL_RUN_COUNT=$416C52
SPILL_TAG_COUNT=$416C54
M7_BITMAP_WORK=$416C58
M7_BITMAP_WORK_LIMIT=$416C5A
M7_BITMAP_TARGET=$416C5C
M7_BITMAP_URGENT=$416C5E
M7_RAW_TO_SPILL=$420000
M7_RAW_TO_PPU=$422000
SPILL_RUNS=$43A200

SYMBOL_X=$410000
SYMBOL_Y=$412200
SYMBOL_VISIBLE=$414400
SYMBOL_SCREEN_X=$43A400
SYMBOL_SCREEN_Y=$43C600
SYMBOL_CENTER_X=$416C60
SYMBOL_CENTER_Y=$416C62
M7_WRAM_STAGE_REQUIRED=$416C80
SPILL_MAP_ACTIVE=$416C82
ROM_SOURCE_PAGE=$416C84
M7_MAP_PREPARED=$416C86
M7_FORCE_SKIP_HUD=$416C88
M7_CACHE_CODE_VALID=$416C8A
M7_BULK_ROWS=$416C98
M7_ROW_CODE_VALID=$416C8C
NATIVE_SOURCE_PAGE=$416C8E
NATIVE_ROW_TAIL=$416C92
NATIVE_ROW_BASE=$416C94
NATIVE_ROW_UNDO=$416C96
; Stream jobs own this arena only in non-resident Neo charts. AR-X's
; resident row-undo and bitmap prefetch arenas are inactive for those jobs.
STREAM_CONFIG=$43EF00
STREAM_ENABLED=STREAM_CONFIG
STREAM_COUNT=STREAM_CONFIG+2
STREAM_TABLE=STREAM_CONFIG+4
STREAM_MSU=STREAM_CONFIG+8
STREAM_MODE1=STREAM_CONFIG+12
M1_ICON_INFO=$422000
M1_ICON_ATTACK=$43EF28
M1_ICON_CHECKPOINT=$43EF2A
EARLY_DMA_ENABLE=$43EF2C
EARLY_IRQ_RUNNING=$43EF2E
M1_SNAPSHOT_BYTES=$43EF30
M1_SNAPSHOT_DIRTY=$43EF32
M1_SNAPSHOT_PENDING=$43EF34
M1_SNAPSHOT_OFFSET=$43EF36
M1_CGRAM_BEGIN=$43EF3A
M1_CGRAM_BYTES=$43EF3C
EARLY_DMA_WARMUP=$43EF3E
M1_FRONT_BANK=$43EF80
M1_BUILD_BANK=$43EF82
M1_PREFETCH_BYTES=$43EF84
CLONE_COUNT=$43EF86
CLONE_PARAMS=$43EF88 ; four (cos,sin,shift-x,shift-y,arc-phase) Q8/Q4 transforms
CLONE_INPUT_BYTES=$43EFB0
CLONE_OUTPUT_BYTES=$43EFB2
M1_PREFETCH_READY=$43EFB4
CLONE_INPUT=$429620
CLONE_OUTPUT=$429840
CLONE_TEMP=$429A80
CLONE_LINES=$429B00
.assert CLONE_INPUT >= M1_PATTERN_RUNS+4, error, "Copy job overlaps the snapshot DMA descriptor"
.assert CLONE_LINES+448 <= $429E00, error, "Copy job overlaps snapshot palette state"
M1_BINDINGS=$422000
M1_PENDING_GLYPHS=$424000
M1_MAP_STAGE=$428000
M1_DIRTY=$429000
M1_PALETTE=$429400
M1_MAP_RUNS=$429480
M1_PATTERN_RUNS=$429600
M1_ROW_MIN=$429E00
M1_ROW_MAX=$429E40
M1_CGRAM=$429E80
M1_CHR_STAGE=$430000
M1_RUN_COUNT=$43EF20
M1_READY=$43EF22
M1_SEED_CURSOR=$43EF24
M1_SEED_SYMBOL_BYTES=$43EF26
M1_DIRTY_BLOCKS=$43EF40
M1_GLYPH_COUNT=STREAM_CONFIG+30
; Inline Mode 7 descriptors use bit 15 instead of a Mode 1 glyph count.
STREAM_DELTA_FLAGS=STREAM_CONFIG+30
M1_SEEDS_LO=STREAM_CONFIG+14
M1_SEEDS_HI=STREAM_CONFIG+18
STREAM_DECODING=STREAM_CONFIG+16
STREAM_PATTERNS=STREAM_CONFIG+20
STREAM_ROWS=STREAM_CONFIG+24
STREAM_PAGE=STREAM_CONFIG+28
; Inline Mode 7 pixels must not overlap the raw-pattern lookup at
; $422000..$429FFF. Mode 1's glyph arena is inactive for these jobs.
STREAM_DELTA_BASE=$42B300
STREAM_DELTA_SPAN=$42B500
STREAM_DELTA_BUDGET=$42B700
STREAM_SHADOW_TAG=$42B800
STREAM_DELTA_TARGET=$42BA00
STREAM_UPLOAD_SPAN=$42BC00
; Reuse the abandoned delta-shadow scratch; these do not alias live tags.
STREAM_SPILL_CELLS_COUNT=$42B800
STREAM_SPILL_PALETTE=$42B802
STREAM_SPILL_CELLS=$42B820
; Retain the fast object snapshot after the packet arena becomes row undo.
STREAM_SPILL_SNAPSHOT=$42BE00
STREAM_SPILL_CHR_BYTES=$42BC00
STREAM_SPILL_BUFFER_ID=$42BC02
STREAM_SPILL_VRAM_ID=$42BC04
STREAM_SPILL_LINES=$42BC06
STREAM_SPILL_NEG_COUNT=$42BC26
STREAM_SPILL_NEGATIVE=$42BC28
STREAM_SPILL_FAST_PTR=$42BC68
STREAM_SPILL_DIRECT=$42BC6A
STREAM_PATTERN_DIRECT=$42BC6C
STREAM_OAM_DIRECT=$42BC6E
STREAM_ROUTE_BEGIN=$42BC70
STREAM_ROUTE_END=$42BC72
STREAM_ROUTE_DEST=$42BC74
STREAM_ROUTE_INDEX=$42BC76
STREAM_ROUTE_LEFT=$42BC78
STREAM_SPILL_BASE_ID=$42BC7A
STREAM_SPILL_DELTA_START=$42BC7C
STREAM_SPILL_DELTA_BYTES=$42BC7E
STREAM_SPILL_EXACT=$42BC80
STREAM_SPILL_STRIDE=$42BC8C
.assert STREAM_SPILL_NEGATIVE+64 <= STREAM_SPILL_FAST_PTR, error, "Spill metadata overlaps fast pointer"
.assert STREAM_DELTA_TARGET+512 <= STREAM_SPILL_SNAPSHOT, error, "Spill snapshot overlaps live pattern tags"
.assert STREAM_SPILL_DELTA_BYTES+2 <= STREAM_SPILL_SNAPSHOT, error, "Spill snapshot overlaps live metadata"
.assert STREAM_SPILL_SNAPSHOT+512 <= $42C000, error, "Spill snapshot overlaps packet/rollback arena"
.assert STREAM_OAM_DIRECT+2 <= STREAM_ROUTE_BEGIN, error, "Transport overlaps spill flags"
.assert STREAM_ROUTE_LEFT+2 <= $42C000, error, "Transport overlaps animation packet"
.assert STREAM_SPILL_DELTA_BYTES+2 <= $42C000, error, "Sprite delta state overlaps animation packet"
.assert STREAM_SPILL_CELLS+80*6 <= STREAM_DELTA_TARGET, error, "Stream OBJ cells overlap delta tags"
.assert STREAM_SPILL_CELLS+120*4 <= STREAM_DELTA_TARGET, error, "Compact OBJ cells overlap delta tags"

STREAM_CHR=$430000
.assert STREAM_CHR >= M7_RAW_TO_PPU+$8000, error, "Inline textures overlap raw pattern lookup"
.assert STREAM_CHR+256*64 <= M7_PATTERN_STAGE, error, "Inline textures overlap staged PPU textures"
STREAM_BUFFER=$42C000
.assert STREAM_DELTA_BASE+512 <= STREAM_DELTA_SPAN, error, "Delta tags overlap spans"
.assert STREAM_DELTA_SPAN+512 <= STREAM_DELTA_BUDGET, error, "Delta spans overlap budget"
.assert STREAM_DELTA_BUDGET+2 <= STREAM_SHADOW_TAG, error, "Delta budget overlaps shadow tags"
.assert STREAM_SHADOW_TAG+512 <= STREAM_DELTA_TARGET, error, "Delta tags overlap target tags"
.assert STREAM_DELTA_TARGET+512 <= STREAM_UPLOAD_SPAN, error, "Delta targets overlap upload spans"
.assert STREAM_UPLOAD_SPAN+512 <= STREAM_BUFFER, error, "Delta metadata overlaps packets"
.ifdef SA1_BUILD
.assert PATTERN_QUEUE+128*16 <= M7_FUTURE_DEADLINES, error, "Pattern queue overlaps future deadlines"
.endif
stream_cursor=$05A2
stream_lo=$05A4
stream_hi=$05A6
stream_mid=$05A8
stream_length=$05AA
stream_offset=$05AC
stream_skip=$05B0
stream_choices=$05B2
stream_more=$05D2
stream_remaining=$05D4
stream_destination=$05D6
stream_copy_length=$05D8
stream_hud_pending=$05DA
stream_prefetch_valid=$05DC
stream_prefetch_cursor=$05DE
stream_prefetch_choices=$05E0
STREAM_PREFETCH_OFFSET=$42BC80
STREAM_PREFETCH_LENGTH=$42BC84
STREAM_PREFETCH_BYTES=$42BC86
STREAM_SPILL_SEED_MASK=$42BC88
STREAM_SPILL_PALETTE_DIRTY=$42BC8A
.assert stream_prefetch_choices+32 <= $0600, error, "Stream prefetch choices exceed reserved WRAM"
.assert STREAM_SPILL_SEED_MASK+2 <= $42C000, error, "Stream prefetch state overlaps animation packet"
NATIVE_STAGE_UNDO=$42C000
NATIVE_PALETTE=$42A000
NATIVE_ALPHA=$42A100
NATIVE_READY=$42B200
NATIVE_OFFSET=$42B202
NATIVE_RESULT=$42B206
NATIVE_ZOOM=$42B20A
NATIVE_INVERSE=$42B20C
NATIVE_PALETTE_DIRTY=$42B20E
NATIVE_ALPHA_DIRTY=$42B210
NATIVE_SYMBOL_BYTES=$42B212
NATIVE_TARGET=$42B214
NATIVE_ALPHA_BEGIN=$42B216
NATIVE_ALPHA_END=$42B218
NATIVE_CAMERA_X=$42B21A
NATIVE_CAMERA_Y=$42B21C
M7_SPARSE_BATCH=$43E800
M7_MISSING_LIST=$43F400
M7_CACHE_MISSING_COUNT=$416C64
SPILL_LIVE_COUNT=$416C66
TRAIL_JOB=$43F500
TRAIL_JOB_BUDGET=TRAIL_JOB+$20
TRAIL_JOB_OAM=TRAIL_JOB+$40
TRAIL_JOB_HIGH=TRAIL_JOB+$80
SPILL_OAM_OUT=$43EC00
SPILL_OAM_HIGH=$43EE00
SPILL_OAM_BUDGET=$43EE20
SPILL_OAM_PREFIX=$43EE40
SPILL_OAM_BYTES=$43EE42
M7_DIRECT_LIST=M7_SHARED_BASE+$EE00
M7_REFERENCE_POSITIONS=M7_SHARED_BASE+$FD00
M7_REFERENCE_COUNTS=M7_SHARED_BASE+$FE00
M7_PREFETCH_CURSOR=M7_SHARED_BASE+$FC36
M7_PATTERN_WRITING=M7_SHARED_BASE+$FC38
M7_PREFETCH_ENABLED=M7_SHARED_BASE+$FC3A
M7_PREFETCH_REMAINING=M7_SHARED_BASE+$FC3C
M7_PREFETCH_SCANNED=M7_SHARED_BASE+$FC3E
M7_PREFETCH_INDEX=M7_SHARED_BASE+$FC40
M7_PREFETCH_PATTERN=M7_SHARED_BASE+$FC42
M7_PREFETCH_COUNT=M7_SHARED_BASE+$FC44
TRAIL_TICKS=$7FFA00
TRACK_PALETTE_DIRTY=$7FFA04
TRACK_PALETTE=$7FFA20
TRACK_PALETTE_BATCH=$7FFAE0
MENU_REPEAT_MASK=$7FFC00
MENU_REPEAT_DELAY=$7FFC02
MENU_REPEAT_STATE=$7FFC04
CALIBRATION_SAMPLES=$7FFC10
HIT_SOUND_COMMAND=$7FFC32
CALIBRATION_CENTER=$7FFC34
HIT_SOUND_COUNT=$7FFC36
SOUND_PENDING=$7FFC30
SOUND_NOTE=$7FFC06
SOUND_TICKS=$7FFC08
SOUND_FRAC=$7FFC0A
SOUND_FRAMES=$7FFC0C
SOUND_NOW=$7FFC0E
.ifdef MSU_BUILD
CALIBRATION_LIMIT=30
CALIBRATION_PERIOD=125
CALIBRATION_HALF=63
CALIBRATION_RESULT_BIAS=576
.else
CALIBRATION_LIMIT=8
CALIBRATION_PERIOD=125
CALIBRATION_HALF=63
CALIBRATION_RESULT_BIAS=1024
.endif
.ifdef MSU_BUILD
m7_upload_slots=pattern_slot
m7_service_tick=pattern_global_next
m7_visual_step=cell_hash_dirty
m7_logical_step=cell_hash_bucket
m7_pattern_budget=pattern_next_min
.endif
M7_HDMA_STAGE=$0540
M7_HDMA_DISPLAY=$0560
EVENT_LIST=$0600
SPRITE_BUDGET=$0600
FIRE_X=$0480
FIRE_Y=$04A0
ICE_X=$04C0
ICE_Y=$04E0
HIT_TIMES=$0520
.ifdef MSU_BUILD
CHR_RAM=M7_CHR_LOW
.else
CHR_RAM=$7E8000
.endif
TAP_MASK=$CFF0
TAP_QUEUE_MASK=255
START=$1000
SELECT=$2000

.segment "ZEROPAGE"
tick: .res 2
last_tick: .res 2
joy: .res 2
old_joy: .res 2
pressed: .res 2
pending_pressed: .res 2
state: .res 2 ; title, playing, failed, clear, paused, calibrating, cal result
display_state: .res 2
selected_level: .res 2
step: .res 2
last_note: .res 2
first_hit: .res 2
song_end: .res 2
beat_frames: .res 2
first_arc_frames: .res 2
elapsed: .res 2
chart_time: .res 2
combo: .res 2
best: .res 2
perfects: .res 2
misses: .res 2
practice: .res 2
autoplay: .res 2
calibration: .res 2
feedback: .res 2
feedback_time: .res 2
timing_error: .res 2
last_error: .res 2
fail_reason: .res 2
cam_x: .res 2
cam_y: .res 2
angle: .res 2
orbit_x: .res 2
orbit_y: .res 2
sprite_x: .res 2
sprite_y: .res 2
sprite_tile: .res 2
sprite_attr: .res 2
oam_pos: .res 2
render_i: .res 2
scratch: .res 2
scratch2: .res 2
text_ptr: .res 2
number: .res 2
digit: .res 2
music_ptr: .res 3
packet_seq: .res 2
packets_left: .res 2
music_active: .res 2
hud_state: .res 2
audio_ticks: .res 2
stream_ticks: .res 2
sa1_async: .res 2
clock_version: .res 2
clock_fraction: .res 2
transfer_ptr: .res 3
transfer_len: .res 2
transfer_dest: .res 2
transfer_wbank: .res 2
frame_ready: .res 2
track_dirty: .res 2
commits: .res 2
skipped_commits: .res 2
map_x: .res 2
map_y: .res 2
map_last_x: .res 2
map_last_y: .res 2
map_height: .res 2
map_ptr: .res 3
map_skip: .res 2
map_run: .res 2
map_tile: .res 2
map_left: .res 2
map_row: .res 2
map_dest: .res 2
mul_rate: .res 2
mul_delta: .res 2
mul_product: .res 2
cal_count: .res 2
cal_sum: .res 2
cal_phase: .res 2
cal_beat: .res 2
cal_last_beat: .res 2
cal_error: .res 2
cal_recommend: .res 2
profile_phase: .res 2
event_pos: .res 2
view_x: .res 2
view_y: .res 2
view_count: .res 2
view_rows: .res 2
trail_head: .res 2
trail_count: .res 2
trail_i: .res 2
fx_i: .res 2
fx_left: .res 2
fx_age: .res 2
menu_first: .res 2
menu_i: .res 2
menu_row: .res 2
chart_count: .res 2
chart_array: .res 2
event_end: .res 2
budget_first: .res 2
budget_last: .res 2
difficulty: .res 2 ; 0 strict, 1 normal, 2 looser
hit_window: .res 2 ; exclusive absolute-error limit, in NTSC frames
music_origin: .res 2 ; absolute song frame at the BRR seek entry
checkpoint_floor: .res 2
checkpoint_record: .res 2 ; byte offset + 1; zero means no checkpoint
checkpoint_next: .res 2
checkpoint_preroll: .res 2
checkpoint_ready: .res 2
checkpoint_beat: .res 2
checkpoint_flash: .res 2
checkpoints_used: .res 2
rough_window: .res 2
overload: .res 2 ; 8.8 pressure; 128 per rough/extra hit, fail above 256
overload_phase: .res 2
overload_last: .res 2
visibility_index_ptr: .res 3
visibility_ptr: .res 3
map_base_ptr: .res 3
.ifdef ROM_DATA_BUILD
rom_data_ptr: .res 3
.endif

.segment "BSS"
checkpoint_bytes: .res 2 ; loading-only length; leave direct page for ROM pointers
speed_tenths: .res 2
speed_pitch: .res 2
speed_scale: .res 2
event_count: .res 2
event_cursor: .res 2
menu_selection: .res 2
menu_group: .res 2
menu_depth: .res 2
speed_stream: .res 2
speed_offset: .res 2
speed_offset_frac: .res 2
chart_frac: .res 2
hit_window_real: .res 2
clock_ticks: .res 2
clock_song_frac: .res 2
clock_song_frames: .res 2
run_centis: .res 2
run_cs_frac: .res 2
finish_cs: .res 2
time_attack: .res 2
settings_row: .res 2
fire_color: .res 2
ice_color: .res 2
palette_dirty: .res 2
orb_palette: .res 64
.ifdef NEO_BUILD
; WRAM scratch gap between the HDMA tables and event/OAM budget buffer.
; SA-1's similarly named $0580 is in its separate internal RAM.
third_palette=$0580
neo_orb_roles=third_palette+32
.endif
last_judgment: .res 2
judge_signed: .res 2
judge_abs: .res 2
judgment_counts: .res 22
score_lo: .res 2
score_hi: .res 2
result_origin: .res 2
result_prepared: .res 2
cal_return: .res 2
hud_decode_attr: .res 2
hud_decode_count: .res 2
math_lo: .res 2
math_hi: .res 2
math_a: .res 2
math_b: .res 2
math_rem: .res 2
math_index: .res 2
result_i: .res 2
result_row: .res 2
result_total: .res 2
trail_orb: .res 2
trail_age: .res 2
trail_current: .res 2
trail_previous: .res 2
trail_dx: .res 2
trail_dy: .res 2
trail_abs_x: .res 2
trail_abs_y: .res 2
trail_pieces: .res 2
trail_move_x: .res 2
trail_move_y: .res 2
trail_pos_x: .res 2
trail_pos_y: .res 2
trail_stroke: .res 2
trail_oam: .res 2
tap_head: .res 2
tap_tail: .res 2
tap_buttons: .res 256
tap_stamps: .res 256
tap_stamp: .res 2
tap_clock: .res 2
tap_frac: .res 2
tap_delta: .res 2
tap_latency: .res 2
tap_mask_remaining: .res 2
tap_overruns: .res 2
tap_queue_peak: .res 2
input_edges: .res 2
input_sound_mask: .res 2
input_version: .res 2
nmi_audio_ticks: .res 2
.ifdef NEO_BUILD
tap_release: .res 2
input_releases: .res 2
neo_hold_keys: .res 2
neo_hold_x: .res 2
neo_hold_y: .res 2
neo_hold_phase: .res 2
neo_hold_duration: .res 2
neo_free_step: .res 2
neo_free_record: .res 2
neo_free_mode: .res 2
neo_free_x: .res 2
neo_free_y: .res 2
neo_free_from_x: .res 2
neo_free_from_y: .res 2
neo_free_angle: .res 2
neo_free_time: .res 2
neo_free_hops: .res 2
neo_free_clock: .res 2
neo_coin_mask: .res 2
neo_free_collected: .res 2
neo_free_checked: .res 2
neo_free_index: .res 2
neo_free_mask: .res 2
neo_free_count: .res 2
neo_free_pointer: .res 2
neo_free_object_x: .res 2
neo_free_object_y: .res 2
neo_cam_active: .res 2
neo_cam_x: .res 2
neo_cam_y: .res 2
neo_free_autocursor: .res 2
neo_return_x: .res 2
neo_return_y: .res 2
neo_return_begin: .res 2
neo_return_until: .res 2
neo_return_fade: .res 2
neo_return_shade: .res 2
neo_laser_left: .res 2
neo_laser_top: .res 2
neo_laser_right: .res 2
neo_laser_bottom: .res 2
neo_laser_axis: .res 2
.endif
checkpoint_counts: .res 22
checkpoint_score_lo: .res 2
checkpoint_score_hi: .res 2
checkpoint_rewind: .res 2
visibility_nodes: .res 2
visibility_low: .res 2
visibility_high: .res 2
visibility_middle: .res 2
visibility_last_time: .res 2
visibility_next: .res 2
visibility_index_hi: .res 2
visibility_bank: .res 2
moving_tiles: .res 2
position_i: .res 2
floor_x: .res 2
floor_y: .res 2
map_offset_hi: .res 2
hud_dirty: .res 2
.ifdef SA1_BUILD
hud_full_dirty: .res 2
hud_meter_dirty: .res 2
.endif
hud_last_combo: .res 2
hud_last_step: .res 2
hud_last_feedback: .res 2
hud_last_feedback_on: .res 2
hud_last_checkpoint_on: .res 2
hud_last_risk: .res 2
hud_last_error: .res 2
hud_last_timer: .res 2
meter_head: .res 2
meter_count: .res 2
meter_average: .res 2
meter_dirty: .res 2
note_taps: .res 2
meter_next_tick: .res 2
meter_bitmap_valid: .res 2
meter_uniform: .res 2
meter_last_uniform: .res 2
meter_uniform_bright: .res 2
meter_bitmap_dirty: .res 2
meter_positions: .res 32
meter_times: .res 32
meter_grades: .res 32
project_limit_x: .res 2
project_limit_y: .res 2
camera_delta: .res 2
map_scan_valid: .res 2
map_scan_x: .res 2
map_scan_y: .res 2
.ifdef MSU_BUILD
msu_present: .res 2
msu_pcm: .res 2
msu_track: .res 2
msu_checkpoint_base: .res 2
msu_song_base: .res 4
msu_seek_offset: .res 4
msu_command_saved: .res 2
msu_volume: .res 2
msu_volume_scaled: .res 2
msu_elapsed_frames: .res 2
input_margin: .res 2
input_rough_window: .res 2
pattern_base: .res 4
pattern_nodes: .res 2
pattern_slot: .res 2
pattern_raw: .res 2
pattern_hi: .res 2
pattern_queue_count: .res 2
pattern_dma_index: .res 2
pattern_global_next: .res 2
pattern_next_min: .res 2
pattern_skip_hud: .res 2
pattern_blanked: .res 2
msu_stream_cursor: .res 4
msu_checkpoint_index: .res 2
animation_base: .res 4
animation_table: .res 4
animation_cursor: .res 4
animation_cells: .res 2
animation_header: .res 2
animation_time: .res 2
animation_kind: .res 2
animation_index: .res 2
animation_value: .res 2
animation_mode: .res 2
animation_bytes: .res 2
snapshot_header: .res 18
display_chart_time: .res 2
cell_hash_dirty: .res 2
cell_hash_bucket: .res 2
cell_hash_slot: .res 2
cell_hash_key: .res 2
pattern_peak_queued: .res 2
pattern_vblank_overruns: .res 2
pattern_queue_epoch: .res 2
msu_data_busy: .res 2
animation_seek_dirty: .res 2
apu_busy: .res 2
audio_pending_packets: .res 2
audio_saved_scratch: .res 2
audio_saved_scratch2: .res 2
animation_deferred: .res 2
vblank_first_time: .res 2
vblank_first_state: .res 2
vblank_first_music: .res 2
vblank_first_queue: .res 2
camera_zoom: .res 2
display_cam_x: .res 2
display_cam_y: .res 2
display_zoom: .res 2
display_inverse: .res 2
camera_inverse: .res 2
object_small: .res 2
m7_timeline_base: .res 4
m7_node_base: .res 4
m7_coord: .res 2
m7_row_count: .res 2
m7_row_key: .res 2
m7_row_span: .res 2
m7_cache_key: .res 2
m7_window_left: .res 2
m7_window_right: .res 2
m7_vtop: .res 2
m7_vbottom: .res 2
m7_project_sign: .res 2
m7_radius: .res 2
m7_loading: .res 2
m7_run_index: .res 2
m7_snapshot_cursor: .res 4
m7_snapshot_chr: .res 4
m7_map_deferrals: .res 2
m7_pattern_head: .res 2
m7_pattern_tail: .res 2
m7_pattern_count: .res 2
m7_cache_width: .res 2
m7_cache_height: .res 2
m7_old_width: .res 2
m7_old_height: .res 2
.endif

.macro GFX addr,dest,size
    lda #.loword(addr)
    sta transfer_ptr
    sep #$20
    .a8
    lda #.bankbyte(addr)
    sta transfer_ptr+2
    rep #$20
    .a16
    lda #dest
    sta transfer_dest
    lda #size
    sta transfer_len
    jsr upload_vram
.endmacro
.macro DESC_PTR offset
    lda DESC+offset
    sta transfer_ptr
    sep #$20
    .a8
    lda DESC+offset+2
    sta transfer_ptr+2
    rep #$20
    .a16
.endmacro

; Countdown state is not pointer data; keep scarce direct page for ROM reads.
.segment "BSS"
checkpoint_click_next: .res 2
checkpoint_clicks_left: .res 2
neo_curve_cache_step: .res 2
neo_curve_cache_level: .res 2
neo_curve_cache_record: .res 2
sprite_limit: .res 2

.segment "CODE"
.a16
.i16
reset:
    sei
    ; The reset/NMI copy lives at $00:8000; execute gameplay through the
    ; identical FastROM copy at $C0:8000 while DB stays zero for SNES I/O.
.ifndef SA1_BUILD
    jml $C00000+fast_reset
.endif
fast_reset:
    clc
    xce
    rep #$38
    ldx #$1FFF
    txs
    lda #0
    tcd
    pea $0000
    plb
    plb
    sep #$20
    .a8
    lda #$80
    sta $2100
    stz $4200
    stz $420B
    stz $420C
    lda #1
    sta $420D
    rep #$20
    .a16
    ldx #0
@ram:
    stz $0000,x
    inx
    inx
    cpx #$1E00
    bne @ram
    lda #512
    sta oam_pos
.ifdef SA1_BUILD
    jsr sa1_init
    lda #512
    sta f:OAM_PREVIOUS_COUNT
.endif
.ifdef SA1_FASTROM_MIRROR
    ; $2222 maps bank $80 to the third MiB. The packer reserves a copy
    ; of this code bank there. Bank $80 mirrors low WRAM and SNES I/O.
    jml $800000+sa1_fast_main
sa1_fast_main:
.endif
.ifdef MSU_BUILD
    ldx #0
    lda #0
@best_ram:
    sta f:BEST_SCORES,x
    inx
    inx
    cpx #LEVEL_COUNT*6
    bcc @best_ram
    sta f:TRACK_PALETTE_DIRTY
    ldx #0
@track_palette_ram:
    sta f:TRACK_PALETTE,x
    inx
    inx
    cpx #192
    bcc @track_palette_ram
.endif
    lda #0
    sta f:MENU_REPEAT_MASK
    sta f:MENU_REPEAT_DELAY
    sta f:HIT_SOUND_COMMAND
    sta f:HIT_SOUND_COUNT
.ifdef MSU_BUILD
    sta f:AUDIO_FIFO_HEAD
    sta f:AUDIO_FIFO_TAIL
    sta f:AUDIO_PACKET_INFLIGHT
.endif
    lda #$FFFF
    sta f:MENU_REPEAT_STATE
    sta hud_state
    sta map_last_x
    sta map_last_y
    lda #1
    sta difficulty
    sta ice_color
    lda #10
    sta speed_tenths
    jsr prepare_speed
    jsr init_menu
    jsr update_orb_colors
    jsr set_difficulty
    sep #$20
    .a8
    ldx #$2101
@ppu:
    stz $0000,x
    inx
    cpx #$2134
    bne @ppu
    lda #$80
    sta $2115
    stz $2116
    stz $2117
    lda #9
    sta $4300
    lda #$18
    sta $4301
    ldx #.loword(zero_word)
    stx $4302
    stz $4304
    stz $4305
    stz $4306
    lda #1
    sta $420B
    rep #$20
    .a16
    lda #.loword(PALETTE_ADDR)
    sta transfer_ptr
    sep #$20
    .a8
    lda #.bankbyte(PALETTE_ADDR)
    sta $4304
    stz $2121
    stz $4300
    lda #$22
    sta $4301
    ldx transfer_ptr
    stx $4302
    ldx #512
    stx $4305
    lda #1
    sta $420B
    rep #$20
    .a16
.ifdef SA1_BUILD
    ; Preserve the editable palette's bright text color. The two lower
    ; planes of palette 7 are reserved for the meter's half/quarter fade.
    lda f:PALETTE_ADDR+62
    and #$7BDE
    lsr a
    sta scratch
    and #$7BDE
    lsr a
    pha
    sep #$20
    .a8
    lda #29
    sta $2121
    rep #$20
    .a16
    pla
    sep #$20
    .a8
    sta $2122
    xba
    sta $2122
    lda scratch
    sta $2122
    lda scratch+1
    sta $2122
    rep #$20
    .a16
.endif
    GFX BACKGROUND_CHR_ADDR,$4000,BACKGROUND_CHR_BYTES
    GFX BACKGROUND_MAP_ADDR,$4800,2048
.ifdef SA1_BUILD
    ; Static HUD glyphs are monochrome. Put their ink in color 3 so the
    ; meter can use colors 1/2 for fading without dimming ordinary text.
    ; This boot-only staging area is reused by meter/alpha data in play.
    ldx #0
@font_ink:
    lda f:FONT_ADDR,x
    sta scratch
    xba
    ora scratch
    and #255
    sta scratch
    xba
    ora scratch
    sta f:$7FDE00,x
    inx
    inx
    cpx #2048
    bcc @font_ink
    GFX $7FDE00,$5000,2048
.else
    GFX FONT_ADDR,$5000,2048
.endif
    GFX OBJECTS_ADDR,$6000,8192
.ifdef NEO_BUILD
    ; OBJ tiles 448..511: beyond the spill cache and the HUD tilemap.
    GFX NEO_OBJECTS_ADDR,$7C00,2048
.endif
    sep #$20
    .a8
.ifdef MSU_BUILD
    lda #$03
.else
    lda #$63
.endif
    sta $2101
    lda #9
    sta $2105
    lda #$70
    sta $2107
    lda #$48
    sta $2108
    lda #$78
    sta $2109
    lda #$40
    sta $210B
    lda #5
    sta $210C
    stz $210D
    stz $210D
    stz $210F
    stz $210F
    lda #$FF
    sta $210E
    sta $210E
    sta $2110
    sta $2110
    stz $2111
    stz $2111
    lda #$FF
    sta $2112
    sta $2112
    lda #$16
    sta $212C
    stz $212D
    stz $4370
    lda #$2C
    sta $4371
    ldx #.loword(hdma_hide)
    stx $4372
    stz $4374
.ifdef MSU_BUILD
    stz $4360
    lda #5
    sta $4361
    ldx #.loword(hdma_mode1)
    stx $4362
    stz $4364
    lda #3
    sta $2123
    sta $2125
    lda #$C0
.else
    lda #$80
.endif
    sta $420C
    rep #$20
    .a16
    jsr spc_upload
    jsr draw_hud
    jsr render
    lda #1
    sta frame_ready
    sep #$20
    .a8
    ; Enabling NMI late inside an existing VBlank can dispatch the first
    ; full HUD upload with only a few scanlines left. Start on a fresh one.
@boot_vblank_end:
    lda $4212
    bmi @boot_vblank_end
    lda $4210
    lda #$81
    sta $4200
    lda #$0F
    sta $2100
    rep #$20
    .a16
.ifdef NEO_BUILD
    cli
.endif
main:
.ifdef MSU_BUILD
    jsr audio_pump
.endif
    lda tick
    cmp last_tick
    beq main
    lda frame_ready
    bne main
    lda tick
    sta last_tick
    lda pending_pressed
    trb pending_pressed
    sta pressed
    lda joy
    sta old_joy
    lda #1
    sta profile_phase
    lda state
    jeq @title
    cmp #1
    jeq @play
    cmp #4
    jeq @pause
    cmp #5
    jeq @calibrate
    cmp #6
    jeq @cal_result
    cmp #7
    jeq @settings
    cmp #8
    jeq @statistics
    cmp #3
    bne @result
    jsr update_tail
@result:
    lda pressed
    bit #SELECT
    jne @quit
    bit #START
    jeq @draw
    jsr retry_game
    jmp @draw
@title:
    jsr update_title
    jmp @draw
@play:
    jsr update_game
    jmp @draw
@pause:
    lda pressed
    bit #SELECT
    bne @quit
    bit #START
    beq @draw
    lda #$83
    jsr spc_command
    lda #1
    sta state
    bra @draw
@calibrate:
    jsr update_calibration
    bra @draw
@cal_result:
    jsr update_cal_result
    bra @draw
@settings:
    jsr update_settings
    bra @draw
@statistics:
    jsr update_statistics
    bra @draw
@quit:
    jsr return_title
@draw:
    lda #2
    sta profile_phase
.ifdef SA1_MODE1_BUILD
    jsr mode1_hud_before
.else
    jsr draw_hud
.endif
    lda #3
    sta profile_phase
    jsr render
.ifdef SA1_MODE1_BUILD
    jsr mode1_hud_after
.endif
    lda state
    cmp #1
    bne @publish
    lda #4
    sta profile_phase
    jsr build_track_view
@publish:
.ifdef MSU_BUILD
    lda state
    cmp #1
    bne @publish_ready
    lda f:M7_CACHE_ABORT
    jne main
.ifdef SA1_BUILD
    jsr spill_reserve_symbols
    lda step
    pha
    lda m7_visual_step
    sta step
    jsr render_symbols
    pla
    sta step
.ifdef NEO_BUILD
    jsl neo_camera_copies
.endif
.endif
@publish_ready:
.endif
.ifdef SA1_FASTROM_HELPERS
    jsl stream_prefetch_next
.endif
    lda #1
    sta frame_ready
    jmp main

upload_vram:
    lda transfer_dest
    sta $2116
    lda transfer_ptr
    sta $4302
    lda transfer_len
    sta $4305
    sep #$20
    .a8
    lda transfer_ptr+2
    sta $4304
    lda #1
    sta $4300
    lda #$18
    sta $4301
    lda #1
    sta $420B
    rep #$20
    .a16
    rts
upload_wram:
.ifdef LARGE_CHART_BUILD
    lda transfer_wbank
    cmp #$40
    bne :+
    jsl upload_cartridge_arrays
    rts
:
.endif
    lda transfer_ptr
    sta $4302
    lda transfer_len
    sta $4305
    lda transfer_dest
    sta $2181
    sep #$20
    .a8
    lda transfer_wbank
    sta $2183
    lda transfer_ptr+2
    sta $4304
    stz $4300
    lda #$80
    sta $4301
    lda #1
    sta $420B
    rep #$20
    .a16
    rts

load_selected_level:
.ifdef NEO_BUILD
    jsl early_dma_suspend
.endif
.ifdef ROM_PATTERN_PAGED
    ; Chart/map data for other levels can occupy C0. The resident worker
    ; is idle here, so restore the standard mapping before touching it.
    sep #$20
    .a8
    stz $2220
    rep #$20
    .a16
    lda #1
    sta f:SA1_ROM_CURRENT
.endif
.ifdef SA1_STREAM_BUILD
    lda selected_level
    .repeat 5
    asl a
    .endrepeat
    tay
    ldx #0
@stream_descriptor:
    phx
    tyx
    lda f:STREAM_DESCRIPTORS_ADDR,x
    plx
    sta f:STREAM_CONFIG,x
    inx
    inx
    iny
    iny
    cpx #32
    bcc @stream_descriptor
.ifdef STREAM_FALLBACK_DESCRIPTORS_ADDR
    lda f:STREAM_MODE1
    cmp #1
    bne @stream_loaded
    lda speed_tenths
    cmp #11
    bcc @stream_loaded
    lda selected_level
    .repeat 5
    asl a
    .endrepeat
    tay
    ldx #0
@stream_fallback:
    phx
    tyx
    lda f:STREAM_FALLBACK_DESCRIPTORS_ADDR,x
    plx
    sta f:STREAM_CONFIG,x
    inx
    inx
    iny
    iny
    cpx #32
    bcc @stream_fallback
@stream_loaded:
.endif
    lda #0
    sta f:STREAM_DECODING
.endif
    stz map_scan_valid
    jsr load_visibility
    lda selected_level
    asl a
    asl a
    asl a
    asl a
    asl a
    tax
    ldy #0
@desc:
    lda f:level_descriptors,x
    sta DESC,y
    inx
    inx
    iny
    iny
    cpy #32
    bne @desc
    lda DESC+12
    sta last_note
    lda DESC+14
    sta first_hit
    lda DESC+16
    sta song_end
    lda DESC+18
    sta beat_frames
    lda DESC+24
    sta map_height
    lda DESC+26
    sta first_arc_frames
    DESC_PTR 6
    jsr unpack_track_chr
    lda #$8000
    sta transfer_ptr
    sep #$20
    .a8
    lda #$7E
    sta transfer_ptr+2
    rep #$20
    .a16
    lda DESC+20
    sta transfer_len
    stz transfer_dest
.ifdef MSU_BUILD
.ifdef SA1_MODE1_BUILD
    jsr mode1_load_initial_chr
.else
    jsr mode7_upload_chr
.endif
.else
    jsr upload_vram
.endif
    ; The temporary expanded graphics are now in VRAM. The pause table can
    ; safely reuse their WRAM space for the duration of gameplay.
    DESC_PTR 0
    jsr load_chart_arrays
    jsr reset_motion_cache
    ldx #0
    lda #0
@judgments:
    sta f:NOTE_JUDGMENTS,x
    inx
    inx
    cpx #MAX_NOTE_CAPACITY
    bcc @judgments
    lda DESC+30
    xba
    and #255
    sta checkpoint_bytes
    asl a
    clc
    adc checkpoint_bytes
    asl a
    asl a
    clc
    adc checkpoint_bytes
    adc checkpoint_bytes
    sta checkpoint_bytes
    beq @no_checkpoints
    sta transfer_len
    DESC_PTR 28
    lda #.loword(CHECKPOINTS)
    sta transfer_dest
    stz transfer_wbank
.ifdef MSU_BUILD
    inc transfer_wbank
.endif
    jsr upload_wram
@no_checkpoints:
.ifdef HIT_SOUND_BANKS
    jsr load_hit_bank
.endif
    ; Sparse map rows are read directly from their bank-aligned ROM asset.
    ; This leaves WRAM available for long tech charts and avoids overlap.
    lda DESC+3
    sta music_ptr
    sep #$20
    .a8
    lda DESC+5
    sta music_ptr+2
    rep #$20
    .a16
.ifdef MSU_BUILD
    jsr msu_load_song
    jsr load_patterns
.ifdef SA1_MODE1_BUILD
    jsr mode1_load_chart_ready
.endif
.endif
    jsr best_score_index
    lda BEST_SCORES,x
    sta best
    lda #0
    jsr floor_position
    lda floor_x
    sec
.ifdef MSU_BUILD
    sbc #128
.else
    sbc #96
.endif
    sta cam_x
    lda floor_y
    sec
.ifdef MSU_BUILD
    sbc #96
.else
    sbc #116
.endif
    sta cam_y
.ifdef MSU_BUILD
    lda tick
    sta f:CAMERA_FOLLOW_TICK
.endif
    lda #$FFFF
    sta map_last_x
    sta map_last_y
    sta hud_state
    rts

load_chart_arrays:
    lda last_note
    inc a
    sta chart_count
    stz chart_array
    stz transfer_wbank
@array:
    ldx chart_array
    lda chart_destinations,x
    sta transfer_dest
.ifdef LARGE_CHART_BUILD
    lda chart_destination_banks,x
    sta transfer_wbank
.endif
    lda chart_count
    cpx #6
    bcc @word
    cpx #10
    beq @word
    cpx #16
    bne @length
@word:
    asl a
@length:
    sta transfer_len
.ifdef ZERO_PAUSE_TABLES
    lda chart_array
    cmp #16
    bne @copy
    ldx selected_level
    lda zero_pause_tables,x
    and #255
    beq @copy
    jsl clear_pause_array
    bra @advance
@copy:
.endif
    jsr upload_wram
@advance:
    lda transfer_ptr
    clc
    adc transfer_len
    sta transfer_ptr
    inc chart_array
    inc chart_array
    lda chart_array
    cmp #18
    bcc @array
.ifdef SA1_BUILD
    jsr reset_symbol_index
.endif
    rts

.ifdef SA1_BUILD
reset_symbol_index:
    ; Loading a checkpoint starts with a conservative full list. Subsequent
    ; authored symbol-set records replace it without losing visible icons.
    stz event_count
    ldx #0
@event_index:
    lda f:NOTE_FLAGS,x
    and #255
    bit #128
    bne @event_next
    and #119
    beq @event_next
    txa
    phx
    ldx event_count
    sta f:TRACK_SYMBOL_FLOORS,x
    plx
    inc event_count
    inc event_count
@event_next:
    inx
    cpx chart_count
    bcc @event_index
.endif
    rts

start_game:
.ifdef MSU_BUILD
    jsr msu_detect
    bcs @available
    lda #.loword(text_msu_missing)
    ldy #19*64+2*2
    jsr put_text
    rts
@available:
.endif
    stz music_active
    jsr reset_run_stats
    stz music_origin
    stz checkpoint_floor
    stz checkpoint_record
    stz checkpoint_next
    stz checkpoint_preroll
    stz checkpoint_clicks_left
    stz checkpoint_flash
    stz checkpoints_used
    stz overload
    stz overload_phase
    stz overload_last
    stz fail_reason
    lda #$80
    jsr spc_command
    lda #.loword(text_loading)
    ldy #19*64+8*2
    jsr put_text
    lda #1
    sta frame_ready
@consume:
    lda frame_ready
    bne @consume
    sep #$20
    .a8
    lda #$80
    sta $2100
    rep #$20
    .a16
    stz step
    stz elapsed
    stz chart_time
    stz stream_ticks
    stz combo
    stz perfects
    stz misses
    stz feedback
    stz feedback_time
    stz last_error
    stz packet_seq
    stz music_active
    stz trail_head
    stz trail_count
    ldx #0
@effects:
    stz HIT_TIMES,x
    inx
    inx
    cpx #16
    bne @effects
    jsr load_selected_level
    jsr prepare_speed
    jsr apply_audio_speed
    lda #5460
    sta packets_left
    jsr stream_packets
    lda #1
    sta state
    jsr draw_hud
    jsr render
    jsr build_track_view
    lda #1
    sta frame_ready
@sync:
    lda frame_ready
    bne @sync
.ifdef NEO_BUILD
    jsl early_dma_show_loaded
.else
    sep #$20
    .a8
    lda #$0F
    sta $2100
    rep #$20
    .a16
.endif
    lda tick
    sta last_tick
    lda #$81
    jsr spc_command
    lda #1
    sta music_active
    rts

.include "src/checkpoints.inc"
.include "src/settings.inc"
.include "src/statistics.inc"
.include "src/input.inc"
.include "src/visibility.inc"

.include "src/gameplay.inc"
.include "src/render.inc"
.ifdef NEO_BUILD
.include "src/neo.inc"
.endif
.include "src/effects.inc"
.include "src/hud.inc"
.ifdef SA1_BUILD
.include "src/hud_dma.inc"
.endif
.include "src/hit_meter.inc"
.include "src/audio.inc"
.ifdef MSU_BUILD
.include "src/msu.inc"
.ifdef ROM_DATA_BUILD
.include "src/rom_data.inc"
.endif
.include "src/mode7.inc"
.include "src/mode7_cache.inc"
.include "src/mode7_references.inc"
.include "src/animation_mode7.inc"
.include "src/mode7_nmi.inc"
.endif
.include "src/nmi.inc"

.segment "RODATA"
zero_word: .word 0
xhigh_masks: .word 1,4,16,64
trail_ages: .word 6,12,18
timing_windows: .word 3,5,7
difficulty_text: .word text_strict,text_normal,text_looser
text_strict: .byte "STRICT",0
text_normal: .byte "NORMAL",0
text_looser: .byte "LOOSER",0
text_checkpoint: .byte "CHECKPOINT!",0
text_checkpoint_clear: .byte "CHECKPOINT CLEAR",0
text_checkpoints_used: .byte "CHECKPOINTS USED",0
text_checkpoint_retry: .byte "START CHECKPOINT  SELECT MENU",0
text_overload: .byte "TIMING OVERLOAD",0
text_mode_normal: .byte "MODE: NORMAL    ",0
text_mode_watch: .byte "MODE: WATCH     ",0
text_mode_practice: .byte "MODE: PRACTICE  ",0
chart_destinations: .word .loword(NOTE_X),.loword(NOTE_Y),.loword(NOTE_TIME),.loword(NOTE_ANGLE),.loword(NOTE_FLAGS),.loword(NOTE_RATE),.loword(NOTE_PROGRESS),.loword(NOTE_CCW),.loword(NOTE_PAUSE)
.ifdef ZERO_PAUSE_TABLES
.include "zero_pause_tables.inc"
.endif
.ifdef LARGE_CHART_BUILD
chart_destination_banks: .word 1,1,0,0,0,0,0,0,$40
.endif
.ifdef MSU_BUILD
.ifdef NEO_BUILD
.segment "NEOCODE"
.else
.ifdef LARGE_CHART_BUILD
.segment "CAMERA"
.endif
.endif
msu_descriptors: .incbin "msu_descriptors.bin"
.segment "RODATA"
text_msu_missing: .byte "MSU DATA MISSING: SEE README",0
.endif
hdma_show: .byte 32,$16,127,$17,33,$17,32,$16,0
hdma_hide: .byte 127,$16,97,$16,0
.ifdef NEO_BUILD
.segment "NEOCODE"
.endif
level_descriptors: .incbin "descriptors.bin"
visibility_descriptors: .incbin "visibility_descriptors.bin"
.segment "RODATA"
.ifndef SPC_DRIVER_ADDR
spc_image: .incbin "spc.bin"
spc_image_end:
.endif
hud_templates: .word hud0,hud1,hud2,hud3,hud4,hud5,hud6,hud7,hud8
hud0: .incbin "hud0.bin"
hud1: .incbin "hud1.bin"
hud2: .incbin "hud2.bin"
hud3: .incbin "hud3.bin"
hud4: .incbin "hud4.bin"
hud5: .incbin "hud5.bin"
hud6: .incbin "hud6.bin"
hud7: .incbin "hud7.bin"
hud8: .incbin "hud8.bin"
.include "tables.inc"
.ifdef SA1_BUILD
.include "hit_timing.inc"
.endif
.segment "HEADER"
.res 16,0
.byte "ADOFAI SNES OFFICIAL "
.ifdef SA1_BUILD
.byte $23,$35,$0D,$08,$01,$33,$01
.else
.byte $35,$00,$0D,$00,$01,$33,$01
.endif
.word $0000,$FFFF
.segment "VECTORS"
.word 0,0,irq,irq,irq,nmi,0,irq
.word 0,0,irq,0,irq,nmi,reset,irq
.ifdef SA1_BUILD
.segment "CODE"
.include "sa1.inc"
.include "native_animation.inc"
.include "mode1_cpu.inc"
.include "mode7_spill.inc"
.include "sprite_budget.inc"
.ifdef NEO_BUILD
.include "early_dma.inc"
.endif
.segment "SA1CODE"
.incbin "sa1_worker.bin", 0, $7000
.segment "SA1PAYLOAD"
.ifdef NEO_BUILD
.ifdef NEO_CODE_BYTES
.incbin "sa1_payload.bin", NEO_CODE_BYTES
.else
.incbin "sa1_payload.bin", $2000
.endif
.else
.incbin "sa1_payload.bin"
.endif
.else
.segment "PAYLOAD0"
.incbin "payload0.bin"
.segment "PAYLOAD1"
.incbin "payload1.bin"
.endif
