; Trial extended blanking uses only the empty top/bottom eight-pixel HUD
; margins. The playfield (32..175), title, score, meter and status keep
; their original positions and full update rate.
.segment "NEOCODE"
early_dma_suspend:
    lda #0
    sta f:EARLY_DMA_ENABLE
    sta f:EARLY_DMA_WARMUP
    sep #$20
    .a8
    lda #$81
    sta $4200
    lda #$C0
    sta $420C
    sta DMA_COMMANDS+1
    sta DMA_COMMANDS+3
    sta DMA_COMMANDS+5
    rep #$20
    .a16
    rtl

early_dma_show_loaded:
    lda f:EARLY_DMA_ENABLE
    bne @done
    sep #$20
    .a8
    lda #$0F
    sta $2100
    rep #$20
    .a16
@done:
    ; During an early commit HDMA owns the brightness. A checkpoint must
    ; not unblank the border while that same IRQ is still uploading.
    rtl

early_pad_ready:
    .a8
    ; Any short NMI can arrive before auto-joypad's busy bit
    ; rises. Waiting only for busy=0 then reads the shifting result.
    ; Leave scanline 225 first, then the ordinary busy loop waits for
    ; completion. Late/nested NMIs do not wait an additional frame.
@line:
    lda $213F
    lda $2137
    lda $213D
    pha
    lda $213D
    and #1
    bne @high
    pla
    cmp #225
    beq @line
    rtl
@high:
    pla
@ready:
    rtl
    .a16
snapshot_seed_header:
    lda f:STREAM_MODE1
    cmp #3
    bne @done
    sep #$20
    .a8
    data_read8
    sta f:M1_SNAPSHOT_BYTES
    data_read8
    sta f:M1_SNAPSHOT_BYTES+1
    rep #$20
    .a16
    lda #0
    sta f:M1_SNAPSHOT_DIRTY
    sta f:M1_SNAPSHOT_PENDING
    sta f:M1_FRONT_BANK
    sta f:M1_BUILD_BANK
    sta f:CLONE_COUNT
    sta f:M1_PREFETCH_READY
    lda f:M1_SNAPSHOT_BYTES
    bpl @done
    and #$7FFF
    sta f:M1_SNAPSHOT_BYTES
    ; Versioned seeds retain the native copy cameras across checkpoints.
    sep #$20
    .a8
    ldx #0
@copies:
    data_read8
    sta f:CLONE_COUNT,x
    inx
    cpx #42
    bcc @copies
    rep #$20
    .a16
@done:
    rtl

early_dma_nmi_gate:
    lda #0
    sta f:EARLY_DMA_WARMUP
    lda f:EARLY_DMA_ENABLE
    beq @ordinary
@active:
    lda f:EARLY_IRQ_RUNNING
    inc a
    rtl
@ordinary:
    ; A checkpoint seed is deliberately blanked, but its first staged
    ; atlas can still exceed one transfer budget. Use the same back-bank
    ; prefetch as gameplay before publishing that initial scene.
    lda pattern_blanked
    beq @no_prefetch
    lda frame_ready
    beq @no_prefetch
    jsl snapshot_dma_preflight
    bcc @no_prefetch
    lda #1
    rtl
@no_prefetch:
    lda #0
    rtl

early_dma_configure:
    lda f:EARLY_DMA_ENABLE
    pha
    lda #0
    ldx m7_loading
    bne @flag
    ldx pattern_blanked
    bne @flag
    ldx state
    cpx #1
    bcc @retain
    cpx #5
    bcs @retain
@scene:
    ; Death, pause and results can retain a gameplay atlas still queued.
    ; Retain its upload window and preflight until leaving the song; an
    ; ordinary VBlank cannot safely drain a full snapshot at this boundary.
    ldx selected_level
    lda f:level_early_dma,x
    and #255
    bra @flag
@retain:
    ; Returning to a menu can precede the last atlas commit. Keep the
    ; loaded scene's safe window until the next load explicitly suspends
    ; it; selecting another menu item does not load that chart's graphics.
    lda f:EARLY_DMA_ENABLE
@flag:
    sta f:EARLY_DMA_ENABLE
    ; Select the HDMA mask once per frame. Individual DMA sites retain
    ; their original inline cost instead of a banked dispatch per run.
    sep #$20
    .a8
    cmp #1
    lda #$C0
    bcc :+
    lda #$D0
:
    sta DMA_COMMANDS+1
    sta DMA_COMMANDS+3
    sta DMA_COMMANDS+5
    rep #$20
    .a16
    lda f:EARLY_DMA_ENABLE
    cmp #0
    beq @full
    pla
    bne :+
    jsr early_dma_bootstrap
:
    ldx #.loword(early_brightness)
    lda #$A1
    bra @active
@full:
    pla
    beq @disable
    lda m7_loading
    ora msu_data_busy
    ora pattern_blanked
    bne @disable
    sep #$20
    .a8
    lda #$0F
    sta $2100
    rep #$20
    .a16
@disable:
    sep #$20
    .a8
    lda #$81
    sta $4200
    lda #$C0
    sta $420C
    rep #$20
    .a16
    rtl
@active:
    stx $4342
    sep #$20
    .a8
    sta $4200
    lda #^early_brightness
    sta $4344
    stz $4340
    stz $4341
    lda #216
    sta $4209
    stz $420A
    lda #$D0
    sta $420C
    rep #$20
    .a16
    rtl

early_irq:
    php
    rep #$30
    .a16
    .i16
    pha
    phx
    phy
    phb
    pea $0000
    plb
    plb
    sep #$20
    .a8
    lda $4211
    rep #$20
    .a16
    lda f:EARLY_DMA_ENABLE
    beq @return
    lda f:EARLY_DMA_WARMUP
    bne @return
@scene:
    lda #1
    sta f:EARLY_IRQ_RUNNING
    jsl snapshot_dma_preflight
    bcc :+
    jml early_irq_done
:
    ; NMI still samples input/music at its normal time. Its nested path
    ; skips all PPU/DMA state while this immutable scene is committing.
    jml $800000+nmi_commit_entry
@return:
    plb
    ply
    plx
    pla
    plp
    rti

early_irq_done:
    lda #0
    sta f:EARLY_IRQ_RUNNING
    jsl $800000+early_audio_tick
    plb
    ply
    plx
    pla
    plp
    rti

; The port-write verifier checks actual DMA bytes, independently of this
; trailing CPU diagnostic. The PPU stays blank only through line 7.
early_dma_is_blank:
    lda f:EARLY_IRQ_RUNNING
    beq @no
    sep #$20
    .a8
    lda $213F
    lda $2137
    lda $213D
    sta scratch
    lda $213D
    and #1
    sta scratch+1
    rep #$20
    .a16
    lda scratch
    cmp #216
    bcs @yes
    cmp #8
    bcc @yes
@no:
    clc
    rtl
@yes:
    sec
    rtl

early_brightness: .byte 8,$80,127,$0F,81,$0F,8,$80,0

; Enabling HDMA after frame-zero initialization must not resume a stale
; current table pointer. Hold normal brightness for that partial frame.
; The real border table starts at the next hardware frame initialization.
early_dma_bootstrap:
    ldx #.loword(early_visible)
    stx $4348
    lda #1
    sta f:EARLY_DMA_WARMUP
    sep #$20
    .a8
    sta $434A
    lda $213F
    lda $2137
    lda $213D
    pha
    lda $213D
    and #1
    bne @before_zero
    pla
    cmp #225
    bcc @ready
    bra @clear
@before_zero:
    pla
@clear:
    lda #0
    sta f:EARLY_DMA_WARMUP
@ready:
    rep #$20
    .a16
    rts
early_visible: .res 512,$0F

snapshot_commit_palette:
    lda f:M1_CGRAM_BYTES
    beq @clean
    sta $4305
    lda f:M1_CGRAM_BEGIN
    lsr a
    clc
    adc #32
    sep #$20
    .a8
    sta $2121
    stz $4300
    lda #$22
    sta $4301
    lda #^M1_CGRAM
    sta $4304
    rep #$20
    .a16
    lda f:M1_CGRAM_BEGIN
    clc
    adc #.loword(M1_CGRAM)
    sta $4302
    start_dma 1
@clean:
    lda #0
    sta f:TRACK_PALETTE_DIRTY
    sta f:M1_READY
    sta f:M1_CGRAM_BYTES
    rtl
.segment "CODE"
.include "snapshot_dma.inc"
.include "camera_copies.inc"
.segment "CODE"
early_audio_tick:
    jsr msu_audio_tick
    rtl
