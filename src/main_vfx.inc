; Scenery owns only BG2's reserved atlas/map and CGRAM 0..15.
; CHR/map DMA happens under forced blank when a level is loaded.
; During play: four ROM bytes, four scroll writes, and at most 32 palette
; bytes. No SA-1 track job, tile packet or OAM object is added.
.segment "CODE"
main_vfx_load:
    stz main_vfx_active
    lda #$FFFF
    sta main_vfx_last_palette
    lda #$117F
    sta main_vfx_layer_top
    lda #$1111
    sta main_vfx_layer_tail
    lda selected_level
    asl a
    asl a
    asl a
    asl a
    sta main_vfx_index
    tax
    lda f:MAIN_VFX_DESCRIPTORS_ADDR+6,x
    sta main_vfx_pointer
    sep #$20
    .a8
    lda f:MAIN_VFX_DESCRIPTORS_ADDR+8,x
    sta main_vfx_pointer+2
    lda #$80
    sta $2115
    stz $210F
    stz $210F
    stz $2110
    stz $2110
    rep #$20
    .a16
    lda vfx_enabled
    beq @default
    lda f:MAIN_VFX_DESCRIPTORS_ADDR+2,x
    and #255
    beq @default
    lda f:MAIN_VFX_DESCRIPTORS_ADDR,x
    sta transfer_ptr
    sep #$20
    .a8
    lda f:MAIN_VFX_DESCRIPTORS_ADDR+2,x
    sta transfer_ptr+2
    rep #$20
    .a16
    lda #$5500
    sta transfer_dest
    lda f:MAIN_VFX_DESCRIPTORS_ADDR+14,x
    sta transfer_len
    jsr upload_vram
    ldx main_vfx_index
    lda f:MAIN_VFX_DESCRIPTORS_ADDR+3,x
    sta transfer_ptr
    sep #$20
    .a8
    lda f:MAIN_VFX_DESCRIPTORS_ADDR+5,x
    sta transfer_ptr+2
    rep #$20
    .a16
    lda #$5C00
    sta transfer_dest
    lda #2048
    sta transfer_len
    jsr upload_vram
    lda #2
    sta main_vfx_active
    lda #$137F
    sta main_vfx_layer_top
    lda #$1311
    sta main_vfx_layer_tail
    bra @palette
@default:
    jsr main_vfx_default_art
@palette:
    lda main_vfx_active
    beq @default_palette
    ldx main_vfx_index
    lda f:MAIN_VFX_DESCRIPTORS_ADDR+9,x
    sta $4302
    lda #32
    sta $4305
    sep #$20
    .a8
    lda f:MAIN_VFX_DESCRIPTORS_ADDR+11,x
    sta $4304
    jsr main_vfx_palette_apply
    .a16
    stz main_vfx_last_palette
    bra @activate
@default_palette:
    jsr main_vfx_default_palette
@activate:
    lda main_vfx_active
    beq @loaded
    ; Faster compressed-audio transport competes with scenery ROM reads.
    ; Keep the loaded background, but animate only at the tested 1x speed.
    lda speed_tenths
    cmp #10
    bne @loaded
    ldx main_vfx_index
    lda f:MAIN_VFX_DESCRIPTORS_ADDR+12,x
    bmi @loaded
    lda #1
    sta main_vfx_active
@loaded:
    rts
main_vfx_default_art:
    GFX BACKGROUND_CHR_ADDR,$5500,BACKGROUND_CHR_BYTES
    GFX MAIN_VFX_DEFAULT_MAP_ADDR,$5C00,2048
    rts
main_vfx_default_palette:
    lda #.loword(PALETTE_ADDR)
    sta $4302
    lda #32
    sta $4305
    sep #$20
    .a8
    lda #.bankbyte(PALETTE_ADDR)
    sta $4304
main_vfx_palette_apply:
    .a8
    stz $2121
    stz $4300
    lda #$22
    sta $4301
    lda #1
    sta $420B
    rep #$20
    .a16
    rts

; The caller has stopped music and is returning to the menu. Restore
; scenery under forced blank; the next complete HUD commit reveals it.
main_vfx_restore_menu:
    lda main_vfx_active
    beq @done
@wait:
    lda frame_ready
    bne @wait
    stz main_vfx_active
.ifdef NEO_BUILD
    jsl early_dma_suspend
.endif
    sep #$20
    .a8
    lda #$80
    sta $2100
    sta $2115
    stz $210F
    stz $210F
    stz $2110
    stz $2110
    rep #$20
    .a16
    jsr main_vfx_default_art
    jsr main_vfx_default_palette
    lda #1
    sta pattern_blanked
@done:
    rts

main_vfx_idle:
    .a8
    ; The guaranteed idle window ends after scanline 228. Cosmetics may
    ; run during a nested IRQ, but never while a palette transfer is pending.
    lda $213F
    lda $2137
    lda $213D
    cmp #225
    bne main_vfx_idle_return
@joy_start:
    lda $4212
    and #1
    beq @joy_start
    rep #$20
    .a16
    lda main_vfx_active
    cmp #1
    bne main_vfx_idle_skip
    lda palette_dirty
    ora f:TRACK_PALETTE_DIRTY
    ora f:M1_READY
    ora f:M1_CGRAM_BYTES
    bne main_vfx_idle_skip
    lda f:SPILL_VISIBLE
    beq :+
    lda f:STREAM_SPILL_PALETTE_DIRTY
    bne main_vfx_idle_skip
:
    jsr main_vfx_tick
main_vfx_idle_complete:
    sep #$20
    .a8
    rts
main_vfx_idle_skip:
    .a16
    sep #$20
    .a8
main_vfx_idle_return:
    rts

main_vfx_tick:
    .a16
    lda main_vfx_active
    cmp #1
    bne @done
    lda m7_loading
    bne @done
    lda display_state
    cmp #1
    beq @scene
    cmp #2
    beq @scene
@done:
    rts
@scene:
    ldx main_vfx_index
    lda display_chart_time
    bpl :+
    lda #0
:
    cmp f:MAIN_VFX_DESCRIPTORS_ADDR+12,x
    bcc :+
    lda f:MAIN_VFX_DESCRIPTORS_ADDR+12,x
    dec a
:
    asl a
    asl a
    tay
    lda [main_vfx_pointer],y
    sep #$20
    .a8
    sta $210F
    stz $210F
    xba
    sta $2110
    stz $2110
    rep #$20
    .a16
    iny
    iny
    lda [main_vfx_pointer],y
    cmp main_vfx_last_palette
    beq @done
    sta main_vfx_last_palette
    clc
    adc f:MAIN_VFX_DESCRIPTORS_ADDR+9,x
    sta $4332
    lda #32
    sta $4335
    sep #$20
    .a8
    lda f:MAIN_VFX_DESCRIPTORS_ADDR+11,x
    sta $4334
    stz $2121
    stz $4330
    lda #$22
    sta $4331
    lda #$08
    sta $420B
    lda $4212
    bmi :+
    rep #$20
    .a16
.ifdef NEO_BUILD
    jsl early_dma_is_blank
    bcs :+
.endif
    inc pattern_vblank_overruns
    rts
:
    rep #$20
    .a16
    rts
