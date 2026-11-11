; Shared cartridge RAM is independent of the SNES WRAM/audio buffers.
.import __FASTNMI_LOAD__, __FASTNMI_RUN__, __FASTNMI_SIZE__
.import __FASTWRAM_LOAD__, __FASTWRAM_RUN__, __FASTWRAM_SIZE__
SA1_COMMAND=$003780
SA1_DONE=$003782
SA1_DMA_REQUEST=$003784
SA1_DMA_ACTIVE=$003786
SA1_JOBS=$003788
SA1_PENDING=$00378A
SA1_ROM_REQUEST=$00378C
SA1_ROM_CURRENT=$003790
; Internal RAM is separate from the worker's BW-RAM pattern buffers.
; tools/sa1_layout.py assigns these ten private words and preserves aliases.
SA1_LOCAL_QUEUE=$003700
SA1_LOCAL_UPLOADS=$003702
SA1_LOCAL_ROWS=$003704
SA1_LOCAL_SPAN=$003706
SA1_LOCAL_PEAK=$003708
SA1_LOCAL_PCM=$00370A
SA1_LOCAL_EVENTS=$00370C
.ifdef SA1_WRAM_RENDERER
.assert __FASTNMI_SIZE__ <= $600, lderror, "NMI overlaps polling WRAM"
.else
.assert __FASTNMI_SIZE__ <= $600, lderror, "NMI overlaps SA-1 private temporaries"
.endif

sa1_init:
    sep #$20
    .a8
    lda #$20
    sta $2200
    stz $2201
    lda #$80
    sta $2202
    stz $220A
    stz $2220
    lda #1
    sta $2221
    inc a
    sta $2222
    inc a
    sta $2223
    stz $2224
    stz $2225
    stz $2228
    lda #$80
    sta $2226
    sta $2227
    lda #$FF
    sta $2229
    sta $222A
    rep #$20
    .a16
    ; Copy the PPU and polling loops into their fixed RAM execution
    ; buffers before starting the independent cartridge worker.
    phb
    lda #__FASTNMI_SIZE__-1
    ldx #__FASTNMI_LOAD__
    ldy #__FASTNMI_RUN__
    mvn #$00,#$00
    lda #__FASTWRAM_SIZE__-1
    ldx #.loword(__FASTWRAM_LOAD__)
    ldy #__FASTWRAM_RUN__
    mvn #.bankbyte(__FASTWRAM_LOAD__),#$00
    plb
    lda #0
    sta f:SA1_COMMAND
    sta f:SA1_DONE
    sta f:SA1_DMA_REQUEST
    sta f:SA1_DMA_ACTIVE
    sta f:SA1_JOBS
    sta f:SA1_PENDING
    sta f:SA1_ROM_REQUEST
    sta f:SA1_ROM_CURRENT
    ldx #0
@clear:
    sta f:$410000,x
    inx
    inx
    bne @clear
    lda #sa1_reset_vector
    sta $2203
    lda #sa1_irq_vector
    sta $2207
    sep #$20
    .a8
    stz $2200
    rep #$20
    .a16
@boot:
    lda $2300
    and #$80
    beq @boot
    rts

sa1_reset_vector:
    jml $018000
sa1_irq_vector:
    jml $018003

; Frame publication owns the worker now. Copy its residency masks on the
; SA-1 instead of spending hundreds of slow CPU block moves inside NMI.
.segment "FASTNMI"
sa1_cache_commit:
    lda display_state
    sta a:$3000+display_state
    lda #0
    sta f:SA1_DONE
    lda #3
    sta f:SA1_COMMAND
    sep #$20
    .a8
    lda #$80
    sta $2202
    sta $2200
    rep #$20
    .a16
@wait:
    lda $2300
    and #$80
    beq @wait
    rts
.segment "CODE"

sa1_cache_prepare:
    lda f:SA1_PENDING
    jne sa1_cache_finish
    jsr sa1_cache_begin
    jmp sa1_cache_finish

sa1_cache_begin:
    ; Only immutable job inputs cross CPUs. Scratch registers and cache
    ; temporaries belong to the worker; copying the whole 1 KiB BSS here
    ; costs more than a millisecond on every rendered frame.
    lda state
    sta a:$3000+state
    lda selected_level
    sta a:$3000+selected_level
    lda msu_pcm
    sta a:SA1_LOCAL_PCM
    lda pattern_peak_queued
    sta a:SA1_LOCAL_PEAK
    lda #0
    sta f:SA1_DONE
    sta f:SA1_DMA_ACTIVE
    lda #1
    sta f:SA1_PENDING
    sta f:SA1_COMMAND
    sep #$20
    .a8
    lda #$80
    sta $2202
    sta $2200
    rep #$20
    .a16
    rts
.segment "FASTWRAM"
sa1_cache_finish:
@poll:
    jsr audio_pump
.ifdef ROM_PATTERN_PAGED
    jsr sa1_service_rom_bank
.endif
    lda f:SA1_DMA_ACTIVE
    bne @dma_active
    lda f:SA1_DMA_REQUEST
    beq @completion
    cmp #3
    beq @completion
    cmp #2
    bne @dma_publish
    lda a:SA1_LOCAL_QUEUE
    sta pattern_queue_count
    jsr sa1_stage_patterns
    lda #3
    sta f:SA1_DMA_REQUEST
    bra @completion
@dma_publish:
    lda a:SA1_LOCAL_QUEUE
    sta pattern_queue_count
    lda a:SA1_LOCAL_UPLOADS
    sta m7_upload_slots
    lda #1
    sta f:SA1_DMA_ACTIVE
    sta f:M7_CACHE_READY
    bra @completion
@dma_active:
    lda f:M7_CACHE_READY
    bne @completion
    lda #0
    sta f:SA1_DMA_ACTIVE
    sta f:SA1_DMA_REQUEST
@completion:
    lda $2300
    and #$80
    beq @poll
    lda a:SA1_LOCAL_QUEUE
    sta pattern_queue_count
    lda a:SA1_LOCAL_UPLOADS
    sta m7_upload_slots
    lda a:SA1_LOCAL_ROWS
    sta m7_row_count
    lda a:SA1_LOCAL_SPAN
    sta m7_row_span
    lda a:SA1_LOCAL_PEAK
    sta pattern_peak_queued
    lda #0
    sta f:SA1_PENDING
    jsr sa1_stage_patterns
    rts


.segment "CODE"

.ifdef ROM_PATTERN_PAGED
; Only the C0 window changes. Low-bank code stays fixed, and the SNES's
; independent F0 audio/animation reader retains its own selected bank.
sa1_service_rom_bank:
    lda f:SA1_ROM_REQUEST
    beq @done
    pha
    lda #0
    sta f:SA1_ROM_REQUEST
    lda 1,s
    and #255
    dec a
    sep #$20
    .a8
    sta $2220
    rep #$20
    .a16
.ifdef ROM_NATIVE_ADDR
    lda 1,s
    and #$0100
    beq @static_d
    lda 1,s
    and #255
    bra @write_d
@static_d:
    lda #1
@write_d:
    sep #$20
    .a8
    sta $2221
    rep #$20
    .a16
.endif
    pla
    sta f:SA1_ROM_CURRENT
@done:
    rts
.endif

sa1_symbols:
    lda event_count
    sta a:SA1_LOCAL_EVENTS
    lda f:SYMBOL_COORDS_DIRTY
    jeq @dispatch
    lda #1
    sta msu_data_busy
    sep #$20
    .a8
    lda #$80
    sta $4340
    sta $4341
    lda #$41
    sta $4344
    rep #$20
    .a16
    lda f:SYMBOL_DIRTY_BEGIN
    clc
    adc #.loword(NOTE_X)
    sta $2181
    lda #(^NOTE_X)&1
    sep #$20
    .a8
    sta $2183
    rep #$20
    .a16
    lda f:SYMBOL_DIRTY_BEGIN
    clc
    adc #.loword(SYMBOL_X)
    sta $4342
    lda f:SYMBOL_DIRTY_END
    sec
    sbc f:SYMBOL_DIRTY_BEGIN
    sta $4345
    lda #$C010
    sta $420B
    lda f:SYMBOL_DIRTY_BEGIN
    clc
    adc #.loword(NOTE_Y)
    sta $2181
    lda #(^NOTE_Y)&1
    sep #$20
    .a8
    sta $2183
    rep #$20
    .a16
    lda f:SYMBOL_DIRTY_BEGIN
    clc
    adc #.loword(SYMBOL_Y)
    sta $4342
    lda f:SYMBOL_DIRTY_END
    sec
    sbc f:SYMBOL_DIRTY_BEGIN
    sta $4345
    lda #$C010
    sta $420B
    stz msu_data_busy
    lda #0
    sta f:SYMBOL_COORDS_DIRTY
    sta f:SYMBOL_DIRTY_END
    dec a
    sta f:SYMBOL_DIRTY_BEGIN
@dispatch:
    lda a:SA1_LOCAL_EVENTS
    jeq @empty
    lda #0
    sta f:SA1_DONE
    lda #4
    sta f:SA1_COMMAND
    sep #$20
    .a8
    lda #$80
    sta $2202
    sta $2200
    rep #$20
    .a16
@wait:
    jsr audio_pump
    lda $2300
    and #$80
    beq @wait
    rts
@empty:
    sta f:SYMBOL_VISIBLE_COUNT
    rts

sa1_draw_arc:
    lda trail_pos_x
    sta f:TRAIL_JOB
    lda trail_pos_y
    sta f:TRAIL_JOB+2
    lda trail_current
    sta f:TRAIL_JOB+4
    lda trail_previous
    sta f:TRAIL_JOB+6
    lda trail_pieces
    sta f:TRAIL_JOB+8
    lda trail_age
    sta f:TRAIL_JOB+10
    lda trail_orb
    sta f:TRAIL_JOB+12
    lda oam_pos
    sta f:TRAIL_JOB+14
    ldx #0
@budget_in:
    lda SPRITE_BUDGET,x
    sta f:TRAIL_JOB_BUDGET,x
    inx
    inx
    cpx #32
    bcc @budget_in
    lda #0
    sta f:SA1_DONE
    lda #6
    sta f:SA1_COMMAND
    sep #$20
    .a8
    lda #$80
    sta $2202
    sta $2200
    rep #$20
    .a16
@wait:
    jsr audio_pump
    lda $2300
    and #$80
    beq @wait
    ldx #0
@budget_out:
    lda f:TRAIL_JOB_BUDGET,x
    sta SPRITE_BUDGET,x
    lda f:TRAIL_JOB_HIGH,x
    ora OAM+512,x
    sta OAM+512,x
    inx
    inx
    cpx #32
    bcc @budget_out
    lda f:TRAIL_JOB+4
    sta trail_current
    lda f:TRAIL_JOB+8
    sta trail_pieces
    lda f:TRAIL_JOB+20
    sta trail_stroke
    lda f:TRAIL_JOB+16
    asl a
    asl a
    sta trail_oam
    beq @done
    ldy #0
@oam:
    tyx
    lda f:TRAIL_JOB_OAM,x
    ldx oam_pos
    sta OAM,x
    iny
    iny
    inc oam_pos
    inc oam_pos
    cpy trail_oam
    bcc @oam
@done:
sa1_arc_complete:
    rts

sa1_draw_spills:
    lda f:SPILL_VISIBLE
    jeq @done
    lda oam_pos
    sta f:SPILL_OAM_PREFIX
    ldx #0
@budget_in:
    lda SPRITE_BUDGET,x
    sta f:SPILL_OAM_BUDGET,x
    inx
    inx
    cpx #32
    bcc @budget_in
    lda #0
    sta f:SA1_DONE
    lda #7
    sta f:SA1_COMMAND
    sep #$20
    .a8
    lda #$80
    sta $2202
    sta $2200
    rep #$20
    .a16
@wait:
    jsr audio_pump
    lda $2300
    and #$80
    beq @wait
    ldx #0
@budget_out:
    lda f:SPILL_OAM_BUDGET,x
    sta SPRITE_BUDGET,x
    lda f:SPILL_OAM_HIGH,x
    ora OAM+512,x
    sta OAM+512,x
    inx
    inx
    cpx #32
    bcc @budget_out
    lda f:SPILL_OAM_BYTES
    beq @done
    sta transfer_len
    lda #1
    sta msu_data_busy
    lda oam_pos
    clc
    adc #OAM
    sta $2181
    sep #$20
    .a8
    stz $2183
    stz $4300
    lda #$80
    sta $4301
    lda #^SPILL_OAM_OUT
    sta $4304
    rep #$20
    .a16
    lda #.loword(SPILL_OAM_OUT)
    sta $4302
    lda transfer_len
    sta $4305
    lda #$C001
    sta $420B
    stz msu_data_busy
    lda oam_pos
    clc
    adc transfer_len
    sta oam_pos
@done:
sa1_spill_complete:
    rts


; A = first changed coordinate byte; X = contiguous byte count.
; Only changed ranges cross the SNES/SA-1 memory buses.
symbol_coords_changed:
    pha
    cmp f:SYMBOL_DIRTY_BEGIN
    bcs :+
    sta f:SYMBOL_DIRTY_BEGIN
:
    txa
    clc
    adc 1,s
    cmp f:SYMBOL_DIRTY_END
    bcc :+
    sta f:SYMBOL_DIRTY_END
:
    lda #1
    sta f:SYMBOL_COORDS_DIRTY
    pla
    rts

symbol_coords_reset:
    lda #0
    sta f:SYMBOL_DIRTY_BEGIN
    lda last_note
    inc a
    asl a
    sta f:SYMBOL_DIRTY_END
    lda #1
    sta f:SYMBOL_COORDS_DIRTY
    rts

; Queue data is immutable until publication. WRAM sources cross the
; cartridge bus once here; SA-1 stages cartridge sources itself.
sa1_stage_patterns:
    lda f:M7_WRAM_STAGE_REQUIRED
    jeq @done
    lda pattern_queue_count
    beq @done
    lda #1
    sta msu_data_busy
    ldx #0
    ldy pattern_queue_count
    sep #$20
    .a8
    lda #$80
    sta $4340
    sta $4341
    lda #$43
    sta $4344
    rep #$20
    .a16
@copy:
    lda f:PATTERN_QUEUE+2,x
    cmp #$C0
    bcs @next
    cmp #$7E
    bcc @next
    and #1
    sep #$20
    .a8
    sta $2183
    rep #$20
    .a16
    lda f:PATTERN_QUEUE,x
    sta $2181
    lda f:PATTERN_QUEUE+4,x
    clc
    adc #.loword(M7_PATTERN_STAGE)
    sta $4342
    lda #64
    sta $4345
    lda #$C010
    sta $420B
@next:
    txa
    clc
    adc #16
    tax
    dey
    bne @copy
    stz msu_data_busy
@done:
    rts
