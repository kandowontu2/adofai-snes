.ifdef SA1_BUILD
.segment "FASTNMI"
.endif
; Shared staging buffers are immutable from publication until this commit.
; If a render overruns, retain the entire previous PPU frame. Never DMA an
; OAM buffer being cleared or a partially built HUD/track map.
nmi:
.ifdef MSU_BUILD
.ifndef SA1_BUILD
    jml $C00000+nmi_fast
.endif
.endif
nmi_fast:
    php
    rep #$30
    .a16
    .i16
    pha
    phx
    phy
    phb
.ifdef MSU_BUILD
    pea $0000
    plb
    plb
.else
    phk
    plb
.endif
    sep #$20
    .a8
    lda $4210
    rep #$20
    .a16
.ifdef MSU_BUILD
    lda music_active
    beq @msu_clock_done
    lda msu_pcm
    beq @msu_clock_done
    lda state
    cmp #1
    beq @msu_clock
    cmp #3
    bne @msu_clock_done
@msu_clock:
    inc msu_elapsed_frames
@msu_clock_done:
.endif
    lda frame_ready
    jeq @skip
    lda state
    sta display_state
.ifdef MSU_BUILD
    cmp #2
    beq :+
    lda f:M7_RENDER_TIME
    sta display_chart_time
:
    jsr mode7_prime_hdma
.endif
    sep #$20
    .a8
.ifdef MSU_BUILD
    lda display_state
    cmp #2
    beq @oam_done
.endif
    stz $2102
    stz $2103
    stz $4300
    lda #4
    sta $4301
    ldx #OAM
    stx $4302
    stz $4304
    ldx #544
    stx $4305
    lda #1
    sta $420B
.ifdef MSU_BUILD
@oam_done:
.endif
.ifdef MSU_BUILD
    rep #$20
    .a16
    jsr mode7_commit_map
    jsr mode7_commit_patterns
    sep #$20
    .a8
    stz $4304
    lda pattern_queue_count
    cmp #17
    bcc :+
    lda #1
    sta pattern_skip_hud
:
    lda pattern_skip_hud
    bne @hud_done
.endif
    lda hud_dirty
    beq @hud_done
    ldx #$7800
    stx $2116
    lda #1
    sta $4300
    lda #$18
    sta $4301
    ldx #HUD
    stx $4302
    stz $4304
    ldx #2048
    stx $4305
    lda #1
    sta $420B
    stz hud_dirty
@hud_done:
    lda #1
    sta $4300
    lda #$18
    sta $4301
.ifndef MSU_BUILD
    lda track_dirty
    beq @scroll
    ldx #$7000
    stx $2116
    ldx #TRACK
    stx $4302
    ldx #2048
    stx $4305
    lda #1
    sta $420B
    stz track_dirty
.endif
@scroll:
    lda palette_dirty
    beq @camera
    lda #$C0
    sta $2121
    stz $4300
    lda #$22
    sta $4301
    ldx #orb_palette
    stx $4302
    stz $4304
    ldx #64
    stx $4305
    lda #1
    sta $420B
    stz palette_dirty
@camera:
.ifdef MSU_BUILD
    lda f:TRACK_PALETTE_DIRTY
    beq @track_palette_done
    lda state
    cmp #2
    beq @track_palette_done
    lda #32
    sta $2121
    stz $4300
    lda #$22
    sta $4301
    ldx #.loword(TRACK_PALETTE)
    stx $4302
    lda #$7F
    sta $4304
    ldx #192
    stx $4305
    lda #1
    sta $420B
    lda #0
    sta f:TRACK_PALETTE_DIRTY
@track_palette_done:
.endif
    ; VRAM, OAM and CGRAM must finish in VBlank. The Mode 7 registers
    ; and remaining HDMA table data may finish in the fixed top HUD band.
.ifdef MSU_BUILD
    sep #$20
    .a8
    lda $4212
    bit #$80
    bne @inside_vblank
    rep #$20
    .a16
    lda pattern_vblank_overruns
    bne @overrun_count
    lda chart_time
    sta vblank_first_time
    lda state
    sta vblank_first_state
    lda music_active
    sta vblank_first_music
    lda pattern_dma_index
    sta vblank_first_queue
.ifdef SA1_BUILD
    lda m7_row_count
    sta f:$41FCD0
    lda m7_row_span
    sta f:$41FCD2
    lda m7_upload_slots
    sta f:$41FCD4
    lda f:M7_UPLOAD_LIMIT
    sta f:$41FCD6
.endif
@overrun_count:
    inc pattern_vblank_overruns
    sep #$20
    .a8
@inside_vblank:
    rep #$20
    .a16
    jsr mode7_cache_commit
.endif
.ifdef MSU_BUILD
    rep #$20
    .a16
    jsr mode7_commit_camera
.else
    lda cam_x
    and #255
    sta $210D
    stz $210D
    rep #$20
    .a16
    lda cam_y
    and #255
    dec a
    sep #$20
    .a8
    sta $210E
    xba
    sta $210E
    rep #$20
    .a16
.endif

.ifdef MSU_BUILD
    lda pattern_blanked
    beq @visible
    sep #$20
    .a8
    lda #$0F
    sta $2100
    rep #$20
    .a16
    stz pattern_blanked
@visible:
.endif
    stz frame_ready
    inc commits
.ifdef MSU_BUILD
    lda #1
    sta f:M7_PREFETCH_ENABLED
.endif
    bra @hdma
@skip:
    inc skipped_commits
    lda profile_phase
    asl a
    tax
    inc $0500,x
.ifdef MSU_BUILD
    jsr mode7_prefetch
.endif
@hdma:
.ifdef MSU_BUILD
    ldx #.loword(hdma_mode1)
    lda display_state
    cmp #1
    beq @mode7_scene
    cmp #2
    bne @mode1_scene
@mode7_scene:
    ldx #.loword(hdma_mode7)
    stx $4362
    ldx #M7_HDMA_DISPLAY
    bra @table
@mode1_scene:
    stx $4362
    ldx #.loword(hdma_hide)
.else
    ldx #.loword(hdma_hide)
    lda display_state
    cmp #1
    bcc @table
    cmp #3
    beq @table
    cmp #5
    bcs @table
    ldx #.loword(hdma_show)
.endif
@table:
    stx $4372
    sep #$20
    .a8
@pad:
    lda $4212
    and #1
    bne @pad
    rep #$20
    .a16
    lda music_active
    beq @clock_done
    sep #$20
    .a8
@audio_clock:
    lda $2143
    bit #1
    bne @audio_clock
    sta input_version
    rep #$20
    .a16
    lda $2141
    sta nmi_audio_ticks
    sep #$20
    .a8
    lda $2143
    cmp input_version
    bne @audio_clock
    rep #$20
    .a16
@clock_done:
    lda joy
    eor #$FFFF
    and $4218
    sta input_edges
    ora pending_pressed
    sta pending_pressed
    lda $4218
    sta joy
    lda state
    cmp #1
    beq @tap_state
.ifdef MSU_BUILD
    cmp #5
    beq @tap_state
.endif
    bra @input_done
@tap_state:
    lda music_active
    beq @input_done
    lda input_edges
    and #TAP_MASK
    beq @input_done
    ldx tap_head
    sta tap_buttons,x
    lda nmi_audio_ticks
    sta tap_stamps,x
    txa
    clc
    adc #2
    and #TAP_QUEUE_MASK
    sta tap_head
    cmp tap_tail
    bne @queue_peak
    inc tap_overruns
    lda tap_tail
    clc
    adc #2
    and #TAP_QUEUE_MASK
    sta tap_tail
@queue_peak:
    lda tap_head
    sec
    sbc tap_tail
    and #TAP_QUEUE_MASK
    lsr a
    cmp tap_queue_peak
    bcc @input_done
    sta tap_queue_peak
@input_done:
    jsr service_tap_sounds
    jsr update_menu_repeat
.ifdef MSU_BUILD
    jsr msu_audio_tick
.endif
    inc tick
    plb
    ply
    plx
    pla
    plp
    rti
irq:
    rti

; Only menu directions and shoulder adjustments repeat. Gameplay taps and
; START/SELECT retain rising-edge behavior.
.ifdef SA1_BUILD
.segment "CODE"
.endif
update_menu_repeat:
    lda state
    beq @eligible
    cmp #6
    beq @eligible
    cmp #7
    bne @clear
@eligible:
    cmp f:MENU_REPEAT_STATE
    beq @held
    sta f:MENU_REPEAT_STATE
    lda #0
    sta f:MENU_REPEAT_MASK
@held:
    lda joy
    and #$0F30
    beq @clear
    cmp f:MENU_REPEAT_MASK
    bne @new_hold
    lda f:MENU_REPEAT_DELAY
    beq @repeat
    dec a
    sta f:MENU_REPEAT_DELAY
    bne @done
@repeat:
    lda f:MENU_REPEAT_MASK
    ora pending_pressed
    sta pending_pressed
    lda #5
    sta f:MENU_REPEAT_DELAY
    rts
@new_hold:
    sta f:MENU_REPEAT_MASK
    lda #24
    sta f:MENU_REPEAT_DELAY
    rts
@clear:
    lda #0
    sta f:MENU_REPEAT_MASK
    sta f:MENU_REPEAT_DELAY
@done:
    rts
