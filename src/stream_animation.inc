; Bounded packet transport: short DMA chunks followed by SA-1 decoding.
.ifdef SA1_STREAM_BUILD
.segment "CODE"
.a16
.i16
; A=packet index, return its ROM descriptor in transfer_ptr.
stream_entry:
.if STREAM_INDEX_BYTES = 2
    jmp stream_entry_compact
.else
.ifdef STREAM_INDEX_BYTES
    pha
    asl a
    asl a
    clc
    adc 1,s
    plx
.else
    asl a
    asl a
    asl a
.endif
    clc
    adc f:STREAM_TABLE
    sta transfer_ptr
    lda f:STREAM_TABLE+2
    adc #0
    sta transfer_ptr+2
    rts

.endif

; Loading/checkpoint replay already consumed all events before this header.
stream_find_start:
    stz stream_prefetch_valid
    stz stream_lo
    lda f:STREAM_COUNT
    sta stream_hi
@search:
    lda stream_lo
    cmp stream_hi
    bcs @found
    clc
    adc stream_hi
    lsr a
    sta stream_mid
    jsr stream_entry
    lda [transfer_ptr]
    cmp animation_time
    bcs @upper
    lda stream_mid
    inc a
    sta stream_lo
    bra @search
@upper:
    lda stream_mid
    sta stream_hi
    bra @search
@found:
    sta stream_cursor
.ifdef SA1_MODE1_BUILD
    lda f:STREAM_MODE1
    beq :+
    lda f:M1_SEED_CURSOR
    sta stream_cursor
    rts
:
    lda stream_cursor
.endif
    lda f:STREAM_PAGE
    bne :+
    jmp stream_seed_inline_patterns
:
    lda stream_cursor
    ; Canonical checkpoint snapshots deliberately use reserved FE00+slot
    ; identities. Restore real dictionary IDs before SA-1 can request pixels.
    jsr stream_entry
.ifdef STREAM_INDEX_BYTES
    ldy #2
.else
    ldy #4
.endif
    lda [transfer_ptr],y
    clc
    adc f:STREAM_MSU
    sta msu_seek_offset
    iny
    iny
    lda [transfer_ptr],y
.ifdef STREAM_INDEX_BYTES
    and #255
.endif
    adc f:STREAM_MSU+2
    sta msu_seek_offset+2
    lda msu_seek_offset
    clc
    adc #32
    sta msu_seek_offset
    bcc :+
    inc msu_seek_offset+2
:
    jsr msu_seek_data
    lda #512
    sta transfer_len
    lda #.loword(M7_CHR_LOW)
    sta transfer_dest
    stz transfer_wbank
    jsr animation_dma
    ldx #0
@restore_tags:
    lda f:M7_CHR_LOW,x
    sta f:PATTERN_CURRENT,x
    lda f:M7_PATTERN_VRAM,x
    and #$FF00
    cmp #$FE00
    bne @next_tag
    lda f:M7_PATTERN_VRAM,x
    and #255
    asl a
    phx
    tax
    lda f:M7_CHR_LOW,x
    plx
    sta f:M7_PATTERN_VRAM,x
@next_tag:
    inx
    inx
    cpx #512
    bcc @restore_tags
    lda #1
    sta f:M7_HASH_DIRTY
    sta f:M7_POOL_DIRTY
    rts

stream_animation_update:
    jsr native_animation_seed
    lda f:M7_RENDER_TIME
    sta f:NATIVE_TARGET
@packet:
    lda stream_cursor
    cmp f:STREAM_COUNT
    jcs @done
    jsr stream_entry
    lda [transfer_ptr]
    cmp f:M7_RENDER_TIME
    beq @due
    jcs @done
@due:
    ; NMI audio refills share msu_seek_offset. Lock before constructing
    ; either half of the graphics seek, not just before issuing it.
    lda #1
    sta msu_data_busy
.ifdef SA1_FASTROM_HELPERS
    lda stream_prefetch_valid
    beq @read_choices
    lda stream_cursor
    cmp stream_prefetch_cursor
    bne @read_choices
    jsl stream_prefetch_copy_choices
    bra @choices_ready
@read_choices:
.endif
.ifdef STREAM_INDEX_BYTES
    ldy #2
.else
    ldy #4
.endif
    lda [transfer_ptr],y
    clc
    adc f:STREAM_MSU
    sta msu_seek_offset
    iny
    iny
    lda [transfer_ptr],y
.ifdef STREAM_INDEX_BYTES
    and #255
.endif
    adc f:STREAM_MSU+2
    sta msu_seek_offset+2
    lda #1
    sta msu_data_busy
    jsr msu_seek_data
    lda #stream_choices
    sta transfer_dest
    stz transfer_wbank
    lda #32
    sta transfer_len
    jsr animation_dma
.ifdef SA1_FASTROM_HELPERS
@choices_ready:
.endif
    lda #stream_choices
    sta transfer_ptr
    lda #$7E
    sta transfer_ptr+2
    lda #8
    sta stream_skip
    ldy #24
@choice:
    lda [transfer_ptr],y
    cmp f:M7_RENDER_TIME
    beq @eligible
    bcs @smaller
@eligible:
    iny
    iny
    lda [transfer_ptr],y
    bne @chosen
    dey
    dey
@smaller:
    lsr stream_skip
    tya
    sec
    sbc #8
    tay
    bne @choice
    ldy #2
    lda [transfer_ptr],y
@chosen:
    sta stream_length
    iny
    iny
    lda [transfer_ptr],y
    clc
    adc f:STREAM_MSU
    sta stream_offset
    iny
    iny
    ; The top offset nibble optionally carries an exact packet count.
    ; Zero preserves legacy 1/2/4/8 bundles. Keep the low-word seek carry
    ; while extracting the count from a new descriptor.
    php
    lda [transfer_ptr],y
    pha
    and #$F000
    beq @legacy_count
    xba
    .repeat 4
    lsr a
    .endrepeat
    sta stream_skip
@legacy_count:
    pla
    and #$0FFF
    plp
    adc f:STREAM_MSU+2
    sta stream_offset+2
@send_packet:
    lda stream_length
    and #$8000
    sta stream_more
    lda stream_length
    and #$7FFF
    sta stream_length
    lda #1
    sta msu_data_busy
.ifdef SA1_FASTROM_HELPERS
    jsl stream_prefetch_take
    bcc @read_packet
    bra @cached_packet
@read_packet:
.endif
    lda stream_offset
    sta msu_seek_offset
    lda stream_offset+2
    sta msu_seek_offset+2
    jsr msu_seek_data
    lda stream_length
    sta stream_remaining
    lda #.loword(STREAM_BUFFER)
    sta stream_destination
@copy_chunk:
    ; Inline textures live in bank $43, so this WRAM area is entirely
    ; scratch as in Mode 1. Batch MSU copies without touching live pixels.
    lda f:STREAM_PAGE
    beq @large_chunk
.ifdef SA1_MODE1_BUILD
    ; Mode 1 stages graphics in cartridge RAM, leaving this WRAM scratch
    ; free for larger transfers. No audio servicing occurred between the
    ; old 128-byte chunks, so batching only removes repeated DMA setup.
    lda f:STREAM_MODE1
    beq @small_chunk
.else
    bra @small_chunk
.endif
@large_chunk:
    .assert .loword(M7_CHR_LOW)+8192 <= $10000, error, "Stream scratch DMA crosses WRAM bank"
    lda stream_remaining
    cmp #8192
    bcc @chunk_size
    lda #8192
    bra @chunk_size
@small_chunk:
    lda stream_remaining
    cmp #128
    bcc :+
    lda #128
:
@chunk_size:
    sta stream_copy_length
    sta transfer_len
    lda #.loword(M7_CHR_LOW)
    sta transfer_dest
    stz transfer_wbank
    jsr animation_dma
.ifdef SA1_FASTROM_HELPERS
@cached_packet:
.endif
    ldx #.loword(M7_CHR_LOW)
    ldy stream_destination
    lda stream_copy_length
    jsl stream_copy_packet_chunk
    lda stream_destination
    clc
    adc stream_copy_length
    sta stream_destination
    lda stream_remaining
    sec
    sbc stream_copy_length
    sta stream_remaining
    bne @copy_chunk
    stz msu_data_busy
    lda #1
    sta animation_seek_dirty
    lda #0
    sta f:SA1_DONE
    lda #9
    sta f:SA1_COMMAND
    sep #$20
    .a8
    lda #$80
    sta $2202
    sta $2200
    rep #$20
    .a16
    ; SA-1 now owns the immutable animation packet. Hide the old objects
    ; on the CPU while it decodes, rather than idling and doing this later.
    jsr clear_oam
.ifdef SA1_MODE1_BUILD
    jsl stream_hud_during_decode
.endif
    jsr stream_wait_worker
    jsr native_animation_receive
    lda stream_more
    beq @advance
    lda #1
    sta msu_data_busy
    lda stream_offset
    clc
    adc stream_length
    sta msu_seek_offset
    lda stream_offset+2
    adc #0
    sta msu_seek_offset+2
    lda #1
    sta msu_data_busy
    jsr msu_seek_data
    sep #$20
    .a8
    lda $2001
    sta stream_length
    lda $2001
    sta stream_length+1
    rep #$20
    .a16
    lda msu_seek_offset
    clc
    adc #2
    sta stream_offset
    lda msu_seek_offset+2
    adc #0
    sta stream_offset+2
    jmp @send_packet
@advance:
    lda stream_cursor
    clc
    adc stream_skip
    sta stream_cursor
    jmp @packet
@done:
.ifdef SA1_MODE1_BUILD
    jsl snapshot_fetch_latest
    bcc :+
    jmp @send_packet
:
.endif
    rts
.segment "FASTWRAM"
stream_wait_worker:
    phy
@wait:
    jsr audio_pump
    jsr sa1_service_rom_bank
    ; Poll the completion register from WRAM between services. Continuously
    ; reading the shared ROM/IRAM mailbox stalls the SA-1 we are waiting on.
    ; Thirty-two short polls still service compressed audio well above its
    ; packet rate, without repeatedly taking ownership of cartridge memory.
    ldy #32
@poll:
    lda $2300
    and #$80
    bne @done
    dey
    bne @poll
    bra @wait
@done:
    ply
    rts
.segment "CODE"
.ifdef SA1_FASTROM_HELPERS
stream_prefetch_entry:
    jsr stream_entry
    rtl
stream_prefetch_seek:
    jsr msu_seek_data
    rtl
stream_prefetch_read:
    jsr animation_dma
    rtl
.segment "CAMERA"
stream_prefetch_copy_choices:
    ldx #0
@copy:
    lda stream_prefetch_choices,x
    sta stream_choices,x
    inx
    inx
    cpx #32
    bcc @copy
    rtl
.segment "NEOCODE"
stream_prefetch_take:
    lda stream_prefetch_valid
    beq @miss
    stz stream_prefetch_valid
    lda stream_offset
    cmp f:STREAM_PREFETCH_OFFSET
    bne @miss
    lda stream_offset+2
    cmp f:STREAM_PREFETCH_OFFSET+2
    bne @miss
    lda stream_length
    cmp f:STREAM_PREFETCH_LENGTH
    bne @miss
    sta stream_remaining
    lda f:STREAM_PREFETCH_BYTES
    sta stream_copy_length
    cmp stream_length
    beq @ready
    clc
    adc stream_offset
    sta msu_seek_offset
    lda stream_offset+2
    adc #0
    sta msu_seek_offset+2
    jsl $800000+stream_prefetch_seek
@ready:
    lda #.loword(STREAM_BUFFER)
    sta stream_destination
    stz transfer_wbank
    sec
    rtl
@miss:
    clc
    rtl
.segment "CAMERA"
; Use otherwise idle scanlines to read the next small immutable packet.
; No published OAM/map/CHR is touched. A different catch-up choice falls
; back to the normal reader, and every seed invalidates this cache.
stream_prefetch_next:
    lda state
    cmp #1
    jne @done
    lda f:STREAM_ENABLED
    jeq @done
    lda f:STREAM_MODE1
    ora f:STREAM_PAGE
    ora f:M7_WRAM_STAGE_REQUIRED
    jne @invalidate
    lda f:M7_IDENTITY_MODE
    jeq @invalidate
    lda stream_prefetch_valid
    beq @begin
    lda stream_cursor
    cmp stream_prefetch_cursor
    jeq @done
@begin:
    stz stream_prefetch_valid
    lda stream_cursor
    cmp f:STREAM_COUNT
    jcs @done
    ; Leave over fifty scanlines for a bounded 2 KiB read and publication.
    ; frame_ready is still zero, so NMI cannot overwrite our DMA registers.
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
    cmp #170
    jcs @done
    lda stream_cursor
    sta stream_prefetch_cursor
    jsl $800000+stream_prefetch_entry
    lda #1
    sta msu_data_busy
.ifdef STREAM_INDEX_BYTES
    ldy #2
.else
    ldy #4
.endif
    lda [transfer_ptr],y
    clc
    adc f:STREAM_MSU
    sta msu_seek_offset
    iny
    iny
    lda [transfer_ptr],y
.ifdef STREAM_INDEX_BYTES
    and #255
.endif
    adc f:STREAM_MSU+2
    sta msu_seek_offset+2
    jsl $800000+stream_prefetch_seek
    lda #stream_prefetch_choices
    sta transfer_dest
    stz transfer_wbank
    lda #32
    sta transfer_len
    jsl $800000+stream_prefetch_read
    lda stream_prefetch_choices+2
    beq @unlock
    bmi @unlock
    sta f:STREAM_PREFETCH_LENGTH
    cmp #2048
    bcc :+
    lda #2048
:
    sta transfer_len
    sta f:STREAM_PREFETCH_BYTES
    lda stream_prefetch_choices+4
    clc
    adc f:STREAM_MSU
    sta msu_seek_offset
    sta f:STREAM_PREFETCH_OFFSET
    lda stream_prefetch_choices+6
    and #$0FFF
    adc f:STREAM_MSU+2
    sta msu_seek_offset+2
    sta f:STREAM_PREFETCH_OFFSET+2
    jsl $800000+stream_prefetch_seek
    lda #.loword(M7_CHR_LOW)
    sta transfer_dest
    jsl $800000+stream_prefetch_read
    lda #1
    sta stream_prefetch_valid
@unlock:
    lda #1
    sta animation_seek_dirty
    stz msu_data_busy
@done:
    rtl
@invalidate:
    stz stream_prefetch_valid
    rtl
.segment "CODE"
.endif

.ifdef SA1_MODE1_BUILD
.segment "NEOCODE"
snapshot_fetch_latest:
    lda f:STREAM_MODE1
    cmp #3
    bne @none
    lda f:M1_SNAPSHOT_PENDING
    beq @none
    sta stream_length
    lda #0
    sta f:M1_SNAPSHOT_PENDING
    sta stream_skip
    lda f:M1_SNAPSHOT_OFFSET
    clc
    adc f:STREAM_MSU
    sta stream_offset
    lda f:M1_SNAPSHOT_OFFSET+2
    adc f:STREAM_MSU+2
    sta stream_offset+2
    sec
    rtl
@none:
    clc
    rtl
.segment "CODE"
.endif
.endif

.ifdef SA1_STREAM_BUILD
.segment "FASTWRAM"
; Seed every logical texture after a load or checkpoint, before the packet
; decoder owns it. PAGE=0 uses exact inline pixels instead of a ROM dictionary.
stream_seed_inline_patterns:
    jsl stream_seed_inline_far
    rts
.segment "NEOCODE"
stream_seed_inline_far:
    lda #1
    sta f:STREAM_SPILL_SEED_MASK
    sta f:STREAM_SPILL_PALETTE_DIRTY
    lda #0
    sta f:STREAM_SPILL_CELLS_COUNT
    sta f:STREAM_SPILL_CHR_BYTES
    sta f:STREAM_SPILL_BUFFER_ID
    sta f:STREAM_SPILL_VRAM_ID
    sta f:STREAM_DELTA_BUDGET
    lda #$FFFF
    ldx #0
@delta_reset:
    sta f:STREAM_DELTA_BASE,x
    inx
    inx
    cpx #512
    bcc @delta_reset
    phb
    ldx #.loword(M7_CHR_LOW)
    ldy #.loword(STREAM_CHR)
    lda #224*64-1
    mvn #.bankbyte(M7_CHR_LOW),#.bankbyte(STREAM_CHR)
    ldx #.loword(M7_CHR_HIGH)
    ldy #.loword(STREAM_CHR)+224*64
    lda #32*64-1
    mvn #.bankbyte(M7_CHR_HIGH),#.bankbyte(STREAM_CHR)
    plb
    rtl
.endif

.ifdef SA1_STREAM_BUILD
.segment "FASTWRAM"
stream_entry_compact:
    pha
    asl a
    clc
    adc f:STREAM_TABLE
    sta transfer_ptr
    lda f:STREAM_TABLE+2
    adc #0
    sta transfer_ptr+2
    jsl stream_index_word
    sta stream_choices
    pla
    sta stream_choices+6
    ; i * 544 = i * 32 + i * 512, with full 24-bit carry.
    and #$07FF
    .repeat 5
    asl a
    .endrepeat
    sta stream_choices+2
    sta stream_offset
    lda stream_choices+6
    .repeat 11
    lsr a
    .endrepeat
    sta stream_choices+4
    sta stream_offset+2
    .repeat 4
    asl stream_offset
    rol stream_offset+2
    .endrepeat
    lda stream_offset
    clc
    adc stream_choices+2
    sta stream_choices+2
    lda stream_offset+2
    adc stream_choices+4
    sta stream_choices+4
    lda #stream_choices
    sta transfer_ptr
    lda #$7E
    sta transfer_ptr+2
    rts
.include "stream_transport.inc"
.endif

.ifdef SA1_STREAM_BUILD
.segment "NEOCODE"
; MSU masters can keep immutable timestamp directories in upper ROM.
; The CPU's F0 window is independent of the SA-1 worker's C0 dictionary.
; Restore its ordinary page before returning; no data/audio pump is called
; while this two-byte read temporarily selects the index's physical page.
stream_index_word:
    lda transfer_ptr+2
    cmp #$80
    bcs @direct
    sep #$20
    .a8
    pha
    lsr a
    lsr a
    lsr a
    lsr a
    sta $2223
    pla
    and #15
    ora #$F0
    sta transfer_ptr+2
    rep #$20
    .a16
    lda [transfer_ptr]
    pha
    sep #$20
    .a8
    lda #3
    sta $2223
    rep #$20
    .a16
    pla
    rtl
@direct:
    lda [transfer_ptr]
    rtl
.segment "CODE"
.endif
