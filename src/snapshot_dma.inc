.segment "NEOCODE"
.export snapshot_prefetch_begin, snapshot_prefetch_done
; The front atlas remains visible until the complete new atlas/map/OAM can
; publish together. Large frames prefetch into the other 512-tile bank.
snapshot_dma_preflight:
    lda f:STREAM_MODE1
    cmp #3
    jne @ordinary
    lda f:M1_RUN_COUNT
    jeq @ordinary
    lda f:M1_PREFETCH_READY
    jeq @ordinary
    lda f:SA1_PENDING
    jne @ordinary
    ; Cache preparation has finished, and the snapshot atlas is immutable.
    ; Prefetch while the main CPU/SA-1 finish live sprite jobs, rather than
    ; making the completed scene wait for those uploads afterwards.
    lda frame_ready
    beq @prefetch
    lda f:M1_PATTERN_RUNS+2
    clc
    adc m7_row_span
    clc
    adc #1280
    ldx pattern_blanked
    beq :+
    ; First checkpoint publication also replaces the full HUD, meter,
    ; palette and OAM rather than the small steady-state dirty regions.
    clc
    adc #1792
:
    cmp #7201
    bcs @prefetch
@ordinary:
    clc
    rtl
@prefetch:
    lda f:M1_PATTERN_RUNS+2
    cmp #8192
    bcc :+
    lda #8192
:
    sta f:M1_PREFETCH_BYTES
    sta $4355
    lda f:M1_PATTERN_RUNS
    sta $4352
    lsr a
    sta $2116
    sep #$20
    .a8
    lda #$80
    sta $2115
    lda #1
    sta $4350
    lda #$18
    sta $4351
    lda #^M1_CHR_STAGE
    sta $4354
    rep #$20
    .a16
snapshot_prefetch_begin:
    start_dma 32
    lda f:M1_PATTERN_RUNS
    clc
    adc f:M1_PREFETCH_BYTES
    sta f:M1_PATTERN_RUNS
    lda f:M1_PATTERN_RUNS+2
    sec
    sbc f:M1_PREFETCH_BYTES
    sta f:M1_PATTERN_RUNS+2
    bne :+
    sta f:M1_RUN_COUNT
:
    .repeat 5
    lsr a
    .endrepeat
    sta m7_upload_slots
    sta pattern_queue_count
    sec
snapshot_prefetch_done:
    rtl

snapshot_force_complete:
    lda f:STREAM_MODE1
    cmp #3
    bne @done
    lda f:M1_BUILD_BANK
    sta f:M1_FRONT_BANK
    lda #0
    sta f:M1_SNAPSHOT_DIRTY
    sta f:M1_PREFETCH_READY
@done:
    rtl
.segment "CODE"
