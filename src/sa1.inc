; Shared cartridge RAM is independent of the SNES WRAM/audio buffers.
.import __FASTNMI_LOAD__, __FASTNMI_RUN__, __FASTNMI_SIZE__
.import __FASTWRAM_LOAD__, __FASTWRAM_RUN__, __FASTWRAM_SIZE__
SA1_COMMAND=$400000
SA1_DONE=$400002
SA1_DMA_REQUEST=$400004
SA1_DMA_ACTIVE=$400006
SA1_JOBS=$400008
SA1_PENDING=$40000A

sa1_init:
    sep #$20
    .a8
    lda #$20
    sta $2200
    stz $2201
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
    ; Run the tight PPU transfer loops from SA-1 IRAM's CPU-visible
    ; mirror. This uses six-cycle internal accesses without FastROM.
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
    lda f:SA1_DONE
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
    sta $2200
    rep #$20
    .a16
@wait:
    lda f:SA1_DONE
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
    lda msu_pcm
    sta f:$400000+msu_pcm
    lda pattern_peak_queued
    sta f:$400000+pattern_peak_queued
    lda #0
    sta f:SA1_DONE
    sta f:SA1_DMA_ACTIVE
    lda #1
    sta f:SA1_PENDING
    sta f:SA1_COMMAND
    sep #$20
    .a8
    lda #$80
    sta $2200
    rep #$20
    .a16
    rts
.segment "FASTWRAM"
sa1_cache_finish:
@poll:
    jsr audio_pump
    lda f:SA1_DMA_ACTIVE
    bne @dma_active
    lda f:SA1_DMA_REQUEST
    beq @completion
    lda f:$400000+pattern_queue_count
    sta pattern_queue_count
    lda f:$400000+m7_upload_slots
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
    lda f:SA1_DONE
    beq @poll
    lda f:$400000+pattern_queue_count
    sta pattern_queue_count
    lda f:$400000+m7_upload_slots
    sta m7_upload_slots
    lda f:$400000+m7_row_count
    sta m7_row_count
    lda f:$400000+m7_row_span
    sta m7_row_span
    lda f:$400000+pattern_peak_queued
    sta pattern_peak_queued
    lda #0
    sta f:SA1_PENDING
    rts


.segment "CODE"
