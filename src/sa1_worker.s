; Executed by the cartridge's SA-1, with its own stack and temporary state.
SA1_WORKER=1
.include "sa1_layout.inc"
.include "sa1_symbols.inc"
.ifdef SA1_WRAM_RENDERER
.import __HOTOBJECTS_LOAD__, __HOTOBJECTS_RUN__, __HOTOBJECTS_SIZE__
.ifdef ROM_PATTERN_COUNT
.import __HOTCACHE_LOAD__, __HOTCACHE_RUN__, __HOTCACHE_SIZE__
.endif
.ifdef ROM_PATTERN_NO_SPILL
.import __HOTROWS_LOAD__, __HOTROWS_RUN__, __HOTROWS_SIZE__
.assert __HOTROWS_SIZE__ <= $80, lderror, "Row kernel exceeds its IRAM overlay"
.endif
.assert __HOTOBJECTS_SIZE__ <= $200, lderror, "Essential OBJ kernel exceeds its IRAM overlay"
.ifdef ROM_PATTERN_COUNT
.assert __HOTCACHE_SIZE__ <= $200, lderror, "Cache kernel exceeds its IRAM overlay"
.endif
.endif
.segment "CODE"
.a16
.i16
    jmp worker_reset
    jmp worker_irq
worker_reset:
    sei
    clc
    xce
    sep #$20
    .a8
    lda #$80
    sta f:$002227
    sta f:$00220A
    lda #$FF
    sta f:$00222A
    lda #0
    sta f:$002225
    sta f:$002250
    rep #$30
    .a16
    ldx #$07FF
    txs
    lda #0
    tcd
    pea $0000
    plb
    plb
    ldx #$0714
    lda #0
@private:
    sta f:$000000,x
    inx
    inx
    cpx #$0780
    bcc @private
    lda #1
    sta f:$000782
    sep #$20
    .a8
    lda #$80
    sta f:$002209
    rep #$20
    .a16
worker_wait:
    cli
    wai
    bra worker_wait
worker_irq:
    sei
    rep #$30
    .a16
    .i16
    ldx #$07FF
    txs
    lda f:$000780
    pha
    lda #0
    sta f:$000780
    sep #$20
    .a8
    lda #$80
    sta f:$00220B
    rep #$20
    .a16
    pla
.ifdef ROM_NATIVE_ADDR
    cmp #8
    jeq @native_animation
.endif
    cmp #7
    beq @spill_objects
    cmp #6
    beq @arc
    cmp #5
    beq @sparse_cells
    cmp #4
    beq @symbols
    cmp #2
    beq @project
    cmp #3
    beq @commit
.ifdef ROM_PATTERN_COUNT
.ifdef ROM_DIRECT_UNTIL
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne @prepare_cache_code
    lda f:M7_RENDER_TIME
    cmp #ROM_DIRECT_UNTIL
    bcc :+
@prepare_cache_code:
.endif
    jsr worker_cache_code
.ifdef ROM_DIRECT_UNTIL
:
.endif
.endif
    jsr mode7_cache_prepare
    jsr worker_pattern_runs
    bra @complete
@commit:
    jsr mode7_cache_commit
    bra @complete
@symbols:
    jsr worker_symbols
    bra @complete
@sparse_cells:
    jsr worker_sparse_cells
    bra @complete
@arc:
    jsr worker_arc
    bra @complete
@spill_objects:
    jsr worker_emit_spills
    bra @complete
@project:
    jsr worker_project
.ifdef ROM_NATIVE_ADDR
    bra @complete
@native_animation:
    jsr worker_native_animation
.endif
@complete:
    lda f:$000788
    inc a
    sta f:$000788
    lda #1
    sta f:$000782
    sep #$20
    .a8
    lda #$80
    sta f:$002209
    rep #$20
    .a16
    jmp worker_wait

audio_pump:
mode7_game_service:
mode7_visible_patterns:
    rts
mode7_floor8:
    .repeat 3
    cmp #$8000
    ror a
    .endrepeat
    rts
mode7_pattern_destination:
    cmp #224
    bcs @high
    .repeat 6
    asl a
    .endrepeat
    clc
    adc #.loword(M7_CHR_LOW)
    sta transfer_dest
    stz transfer_wbank
    rts
@high:
    sec
    sbc #224
    .repeat 6
    asl a
    .endrepeat
    clc
    adc #.loword(M7_CHR_HIGH)
    sta transfer_dest
    lda #1
    sta transfer_wbank
    rts
.include "mode7_cache.inc"
.include "sa1_rows.inc"
.include "sa1_animation.inc"
.include "sa1_arc.inc"
.include "sa1_objects.inc"

worker_emit_spills:
.ifdef SA1_WRAM_RENDERER
    lda #0
    sta M7_CACHE_CODE_VALID
    ; The resident hash is idle after cache preparation. Borrow its 512
    ; internal bytes for the hot OBJ loop, then invalidate it before reuse.
    phb
    lda #__HOTOBJECTS_SIZE__-1
    ldx #__HOTOBJECTS_LOAD__
    ldy #__HOTOBJECTS_RUN__
    mvn #$01,#$00
    plb
.endif
    jsr worker_spill_objects
.ifdef SA1_WRAM_RENDERER
.ifdef ROM_PATTERN_LEVEL
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    beq @done
.endif
    lda #1
    sta f:M7_HASH_DIRTY
.endif
@done:
    rts

worker_cache_code:
.if .defined(SA1_WRAM_RENDERER) .and .defined(ROM_PATTERN_COUNT)
    lda M7_CACHE_CODE_VALID
    bne @ready
    phb
    lda #__HOTCACHE_SIZE__-1
    ldx #__HOTCACHE_LOAD__
    ldy #__HOTCACHE_RUN__
    mvn #$01,#$00
    plb
    lda #1
    sta M7_CACHE_CODE_VALID
@ready:
.endif
    rts

; Four signed multiplications on SA-1 replace the SNES's byte products.
; Projection jobs finish before the map job starts, so the arithmetic
; unit and these shared inputs have one owner at a time.
worker_project:
    lda f:M7_PROJECT_COS
    tax
    lda f:ROT_X
    jsr worker_multiply
    sta f:ROT_SUM
    lda f:M7_PROJECT_SIN
    tax
    lda f:ROT_Y
    jsr worker_multiply
    eor #$FFFF
    inc a
    clc
    adc f:ROT_SUM
    sta f:$40002C
    lda f:ROT_X
    jsr worker_multiply
    sta f:ROT_SUM
    lda f:M7_PROJECT_COS
    tax
    lda f:ROT_Y
    jsr worker_multiply
    clc
    adc f:ROT_SUM
    sta f:$40002E
    rts
worker_multiply:
    sta f:$002251
    txa
    sta f:$002253
    nop
    nop
    sep #$20
    .a8
    lda f:$002306
    clc
    adc #128
    rep #$20
    .a16
    lda f:$002307
    adc #0
    rts

worker_symbols:
    lda #0
    sta f:SYMBOL_VISIBLE_COUNT
    ldy #0
@symbol:
    tyx
    lda f:TRACK_SYMBOL_FLOORS,x
    sta scratch
    asl a
    tax
    lda f:SYMBOL_X,x
    sec
    sbc f:SYMBOL_MIN_X
    cmp f:SYMBOL_WIDTH_X
    jcs @next
    lda f:SYMBOL_Y,x
    sec
    sbc f:SYMBOL_MIN_Y
    cmp f:SYMBOL_WIDTH_Y
    jcs @next
    lda f:SYMBOL_VISIBLE_COUNT
    sta scratch2
    tax
    lda scratch
    sta f:SYMBOL_VISIBLE,x
    asl a
    tax
    lda f:SYMBOL_X,x
    sec
    sbc f:SYMBOL_CENTER_X
    sta f:ROT_X
    lda f:SYMBOL_Y,x
    sec
    sbc f:SYMBOL_CENTER_Y
    sta f:ROT_Y
    lda f:M7_PROJECT_COS
    cmp #256
    bne @project
    lda f:M7_PROJECT_SIN
    bne @project
    ldx scratch2
    lda f:ROT_X
    clc
    adc #120
    sta f:SYMBOL_SCREEN_X,x
    lda f:ROT_Y
    clc
    adc #96
    sta f:SYMBOL_SCREEN_Y,x
    bra @projected
@project:
    jsr worker_project
    ldx scratch2
    lda f:$40002C
    clc
    adc #120
    sta f:SYMBOL_SCREEN_X,x
    lda f:$40002E
    clc
    adc #96
    sta f:SYMBOL_SCREEN_Y,x
@projected:
    lda f:SYMBOL_SCREEN_X,x
    cmp #$FFF1
    bcs @x_visible
    cmp #256
    jcs @next
@x_visible:
    lda f:SYMBOL_SCREEN_Y,x
    cmp #32
    jcc @next
    cmp #191
    jcs @next
    lda f:SYMBOL_VISIBLE_COUNT
    inc a
    inc a
    sta f:SYMBOL_VISIBLE_COUNT
@next:
    iny
    iny
    cpy event_count
    jcc @symbol
    rts

worker_sparse_cells:
    ldy #0
@cell:
    tyx
    lda f:M7_SPARSE_BATCH+4,x
    and #255
    sta scratch
    lda f:M7_SPARSE_BATCH+2,x
    pha
    tax
    sep #$20
    .a8
    lda scratch
    cmp f:M7_MAP,x
    beq @same
    sta f:M7_MAP,x
    rep #$20
    .a16
    lda #1
    sta f:M7_CACHE_DIRTY
    pla
    pha
    and #127
    sta scratch
    pla
    .repeat 7
    lsr a
    .endrepeat
    tax
    sep #$20
    .a8
    lda f:M7_DIRTY_BITS,x
    bne @bounds
    lda #1
    sta f:M7_DIRTY_BITS,x
    rep #$20
    .a16
    txa
    asl a
    tax
    lda scratch
    xba
    ora scratch
    sta f:M7_DIRTY_BOUNDS,x
    bra @next
@bounds:
    rep #$20
    .a16
    txa
    asl a
    tax
    sep #$20
    .a8
    lda scratch
    cmp f:M7_DIRTY_BOUNDS,x
    bcs :+
    sta f:M7_DIRTY_BOUNDS,x
:
    cmp f:M7_DIRTY_BOUNDS+1,x
    bcc @next8
    sta f:M7_DIRTY_BOUNDS+1,x
@next8:
    rep #$20
    .a16
    bra @next
@same:
    rep #$20
    .a16
    pla
@next:
    tya
    clc
    adc #5
    tay
    dec event_count
    jne @cell
    rts


; Independent upcoming bitmaps may enter any unused PPU slot. Their
; deadlines retain the closest future work when the free pool is crowded.
worker_prefetch_bitmaps:
    jsr mode7_cache_hash
    lda #0
    sta M7_BITMAP_WORK
    lda #16
    sta M7_BITMAP_WORK_LIMIT
.ifdef ROM_PATTERN_COUNT
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne @ordinary_growth
    lda m7_upload_slots
    clc
    adc #16
    bra @growth_ready
@ordinary_growth:
.endif
    lda m7_upload_slots
    clc
    adc #4
.ifdef ROM_PATTERN_COUNT
@growth_ready:
.endif
    cmp f:M7_UPLOAD_LIMIT
    bcc :+
    lda f:M7_UPLOAD_LIMIT
:
    sta M7_BITMAP_TARGET
    lda M7_BITMAP_URGENT
    beq :+
    lda #1024
    sta M7_BITMAP_WORK_LIMIT
    lda f:M7_UPLOAD_LIMIT
    sta M7_BITMAP_TARGET
:
    lda #0
    ldx #0
@reserved:
    sta f:M7_DIRECT_LIST,x
    inx
    inx
    cpx #256
    bcc @reserved
@next:
    lda m7_upload_slots
    cmp M7_BITMAP_TARGET
    jcs @done
    lda M7_BITMAP_WORK
    cmp M7_BITMAP_WORK_LIMIT
    jcs @done
    lda f:M7_BITMAP_TAIL
    cmp f:M7_BITMAP_HEAD
    jeq @done
    sta M7_BITMAP_CURSOR
.ifdef ROM_FUTURE_ADDR
    jsr worker_future_read
    jcc @done
    lda M7_BITMAP_EXPIRES
.else
    asl a
    asl a
    asl a
    tax
    lda f:M7_BITMAP_META+4,x
 .endif
    cmp f:M7_RENDER_TIME
    jcc @pop
.ifdef ROM_FUTURE_ADDR
    lda M7_BITMAP_URGENT
    bne @future_urgent
    ; The demand pass already reserved every bitmap needed at this time.
    ; Do not duplicate those uploads in the optional future cache.
    lda M7_BITMAP_DEADLINE
    cmp f:M7_RENDER_TIME
    jcc @pop
    jeq @pop
@future_urgent:
.endif
    lda M7_BITMAP_WORK
    inc a
    sta M7_BITMAP_WORK
.ifndef ROM_FUTURE_ADDR
    lda f:M7_BITMAP_META+2,x
    sta M7_BITMAP_DEADLINE
    lda f:M7_BITMAP_META,x
    sta M7_BITMAP_TAG
.endif
    lda M7_BITMAP_TAG
    jsr mode7_cache_find
    cmp #$FFFF
    jeq @allocate
    jmp @mark_deadline
@allocate:
    jsr worker_spill_prefetch
    jcs @pop
    lda #$FFFF
    sta M7_BITMAP_CHOICE
    lda #0
    sta M7_BITMAP_BEST
    ldy #0
@slot:
    tyx
    lda M7_NEW_VISIBLE,x
    ora M7_OLD_VISIBLE,x
    ora f:M7_DIRECT_LIST,x
    and #255
    jne @slot_next
    tya
    asl a
    tax
    lda f:M7_PATTERN_VRAM,x
    cmp f:M7_FUTURE_TAGS,x
    bne @free
    lda f:M7_FUTURE_DEADLINES,x
    cmp f:M7_RENDER_TIME
    bcc @free
    cmp M7_BITMAP_DEADLINE
    bcc @slot_next
    cmp M7_BITMAP_BEST
    bcc @slot_next
    sta M7_BITMAP_BEST
    tya
    sta M7_BITMAP_CHOICE
    bra @slot_next
@free:
    tya
    sta M7_BITMAP_CHOICE
    bra @chosen
@slot_next:
    iny
    cpy #256
    bcc @slot
@chosen:
    lda M7_BITMAP_CHOICE
    cmp #$FFFF
    jeq @done
    sta M7_CACHE_PHYSICAL
    tax
    sep #$20
    .a8
    lda #1
    sta f:M7_DIRECT_LIST,x
    rep #$20
    .a16
    lda pattern_queue_count
    .repeat 4
    asl a
    .endrepeat
    tax
 .ifdef ROM_PATTERN_ADDR
    lda M7_BITMAP_TAG
    jsr worker_rom_source
    lda transfer_ptr
    sta f:PATTERN_QUEUE,x
    lda transfer_ptr+2
    and #255
    sta f:PATTERN_QUEUE+2,x
.ifdef ROM_PATTERN_PAGED
    lda ROM_SOURCE_PAGE
    sta f:PATTERN_QUEUE+10,x
.endif
.else
    lda M7_BITMAP_CURSOR
    .repeat 6
    asl a
    .endrepeat
    clc
    adc #.loword(M7_BITMAP_SRAM)
    sta f:PATTERN_QUEUE,x
    lda #.bankbyte(M7_BITMAP_SRAM)
    adc #0
    sta f:PATTERN_QUEUE+2,x
.endif
    lda M7_CACHE_PHYSICAL
    .repeat 6
    asl a
    .endrepeat
    sta f:PATTERN_QUEUE+4,x
    lda #64
    sta f:PATTERN_QUEUE+6,x
    lda M7_BITMAP_TAG
    sta f:PATTERN_QUEUE+8,x
    inc pattern_queue_count
    inc m7_upload_slots
    lda m7_upload_slots
    cmp pattern_peak_queued
    bcc :+
    sta pattern_peak_queued
:
    ; A preloaded bitmap occupies an unused physical slot. Neither the
    ; visible logical map nor its mapping changed, so no remap is needed.
    lda M7_CACHE_PHYSICAL
@mark_deadline:
    asl a
    tax
    lda M7_BITMAP_TAG
    cmp f:M7_FUTURE_TAGS,x
    bne @new_deadline
    lda f:M7_FUTURE_DEADLINES,x
    cmp f:M7_RENDER_TIME
    bcc @new_deadline
    cmp M7_BITMAP_DEADLINE
    bcc @pop
@new_deadline:
    lda M7_BITMAP_TAG
    sta f:M7_FUTURE_TAGS,x
    lda M7_BITMAP_DEADLINE
    sta f:M7_FUTURE_DEADLINES,x
@pop:
    lda M7_BITMAP_CURSOR
    inc a
 .ifndef ROM_FUTURE_ADDR
    cmp #M7_BITMAP_COUNT
    bcc :+
    lda #0
:
.endif
    sta f:M7_BITMAP_TAIL
    jmp @next
@done:
    rts

worker_recover_prefetch:
    lda f:M7_BITMAP_ENABLED
    jeq @done
    lda f:M7_BITMAP_HEAD
    cmp f:M7_BITMAP_TAIL
    jeq @done
    phb
    lda #255
    ldx #.loword(M7_OLD_VISIBLE)
    ldy #.loword(M7_NEW_VISIBLE)
    mvn #.bankbyte(M7_OLD_VISIBLE),#.bankbyte(M7_NEW_VISIBLE)
    plb
    stz pattern_queue_count
    stz m7_upload_slots
    lda f:M7_UPLOAD_LIMIT
    pha
    lda #40
    sta f:M7_UPLOAD_LIMIT
    lda #1
    sta M7_BITMAP_URGENT
    jsr worker_prefetch_bitmaps
    lda #0
    sta M7_BITMAP_URGENT
    pla
    sta f:M7_UPLOAD_LIMIT
    lda pattern_queue_count
    ora f:SPILL_COUNT
    beq @done
    jsr worker_pattern_runs
    lda #2
    sta f:M7_CACHE_READY
@wait:
    lda f:M7_CACHE_READY
    cmp #3
    bne :+
    lda #1
    sta f:M7_CACHE_READY
:
    lda f:M7_CACHE_READY
    bne @wait
    jsr worker_commit_tags
@done:
    rts

; Native DMA halts SA-1 until completion. ROM source, bank-$43 BW-RAM
; destination in X, byte count in A; it does not use the SNES DMA channels.
worker_rom_dma:
    sta f:$002238
    lda transfer_ptr
    sta f:$002232
    txa
    sta f:$002235
    sep #$20
    .a8
    lda transfer_ptr+2
    sta f:$002234
    lda #$84
    sta f:$002230
    lda #$43
    sta f:$002237
    lda #0
    sta f:$002230
    lda #$20
    sta f:$00220B
    rep #$20
    .a16
    rts

worker_pattern_runs:
    lda #0
    sta f:M7_PATTERN_RUN_COUNT
    sta f:M7_WRAM_STAGE_REQUIRED
    ldx #0
@clear:
    sta f:M7_PATTERN_DIRTY,x
    inx
    inx
    cpx #256
    bcc @clear
    lda pattern_queue_count
    jeq @done
    sta map_left
    stz map_scan_x
@entry:
    ldx map_scan_x
    lda f:PATTERN_QUEUE+4,x
    .repeat 6
    lsr a
    .endrepeat
    tax
    sep #$20
    .a8
    lda #1
    sta f:M7_PATTERN_DIRTY,x
    rep #$20
    .a16
    ldx map_scan_x
    lda f:PATTERN_QUEUE+2,x
    cmp #$C0
    bcs @rom_source
    cmp #$7E
    bcc @cartridge_source
    lda #1
    sta f:M7_WRAM_STAGE_REQUIRED
    jmp @entry_next
@cartridge_source:
    sta scratch2
    lda f:PATTERN_QUEUE,x
    sta scratch
    lda f:PATTERN_QUEUE+4,x
    clc
    adc #.loword(M7_PATTERN_STAGE)
    tay
    lda scratch2
    cmp #$42
    bne @bank43
    phb
    ldx scratch
    lda #63
    mvn #$42,#$43
    plb
    bra @entry_next
@bank43:
    phb
    ldx scratch
    lda #63
    mvn #$43,#$43
    plb
    bra @entry_next
@rom_source:
.ifdef ROM_PATTERN_PAGED
    lda f:PATTERN_QUEUE+10,x
    jsr worker_select_rom_bank
    lda f:PATTERN_QUEUE+2,x
.endif
    sta transfer_ptr+2
    lda f:PATTERN_QUEUE,x
    sta transfer_ptr
    lda f:PATTERN_QUEUE+4,x
    clc
    adc #.loword(M7_PATTERN_STAGE)
    tax
    lda #64
    jsr worker_rom_dma
@entry_next:
    lda map_scan_x
    clc
    adc #16
    sta map_scan_x
    dec map_left
    jne @entry
    ldx #0
    stz map_left
@scan:
    lda f:M7_PATTERN_DIRTY,x
    and #255
    beq @next
    txa
    sta scratch
@run:
    inx
    cpx #256
    bcs @end_run
    lda f:M7_PATTERN_DIRTY,x
    and #255
    bne @run
@end_run:
    phx
    txa
    sec
    sbc scratch
    .repeat 6
    asl a
    .endrepeat
    ldx map_left
    sta f:M7_PATTERN_RUNS+2,x
    lda scratch
    .repeat 6
    asl a
    .endrepeat
    sta f:M7_PATTERN_RUNS,x
    lda f:M7_PATTERN_RUN_COUNT
    inc a
    sta f:M7_PATTERN_RUN_COUNT
    inc map_left
    inc map_left
    inc map_left
    inc map_left
    plx
    bra @check
@next:
    inx
@check:
    cpx #256
    bcc @scan
@done:
    jsr worker_spill_runs
    rts

worker_commit_tags:
    lda f:M7_TAG_COUNT
    beq @spill
    tay
    ldx #0
@tag:
    phx
    lda f:PATTERN_QUEUE+8,x
    pha
    lda f:PATTERN_QUEUE+4,x
    .repeat 5
    lsr a
    .endrepeat
    tax
    pla
    sta f:M7_PATTERN_VRAM,x
.ifdef ROM_PATTERN_COUNT
    jsr worker_rom_commit
.endif
    plx
    txa
    clc
    adc #16
    tax
    dey
    bne @tag
    lda #0
    sta f:M7_TAG_COUNT
@spill:
.ifdef ROM_PATTERN_COUNT
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne :+
    lda #0
    sta f:M7_HASH_DIRTY
:
.endif
    jsr worker_spill_tags
@done:
    rts

.include "sa1_spill.inc"

.ifdef ROM_PATTERN_ADDR
worker_rom_source:
    pha
    .repeat 10
    lsr a
    .endrepeat
    clc
    adc #.bankbyte(ROM_PATTERN_ADDR)
    sta transfer_ptr+2
    pla
    .repeat 6
    asl a
    .endrepeat
    clc
    adc #.loword(ROM_PATTERN_ADDR)
    sta transfer_ptr
    bcc :+
    inc transfer_ptr+2
:
.ifdef ROM_PATTERN_PAGED
    jmp worker_paged_pointer
.endif
    rts
worker_future_read:
    lda M7_BITMAP_CURSOR
    pha
    .repeat 13
    lsr a
    .endrepeat
    clc
    adc #.bankbyte(ROM_FUTURE_ADDR)
    sta transfer_ptr+2
    pla
    asl a
    asl a
    asl a
    clc
    adc #.loword(ROM_FUTURE_ADDR)
    sta transfer_ptr
    bcc :+
    inc transfer_ptr+2
:
.ifdef ROM_PATTERN_PAGED
.ifndef ROM_FUTURE_STATIC
    jsr worker_paged_pointer
    lda ROM_SOURCE_PAGE
    jsr worker_select_rom_bank
.endif
.endif
    lda [transfer_ptr]
    cmp f:M7_RENDER_TIME
    beq @due
    bcc @due
    clc
    rts
@due:
    ldy #2
    lda [transfer_ptr],y
    sta M7_BITMAP_TAG
    iny
    iny
    lda [transfer_ptr],y
    sta M7_BITMAP_EXPIRES
    iny
    iny
    lda [transfer_ptr],y
    sta M7_BITMAP_DEADLINE
    sec
    rts
.endif

.ifdef ROM_PATTERN_PAGED
; Physical file pointer -> C0-window pointer plus its immutable page tag.
worker_paged_pointer:
    lda transfer_ptr+2
    and #255
    pha
    lsr a
    lsr a
    lsr a
    lsr a
    inc a
    sta ROM_SOURCE_PAGE
    pla
    and #15
    ora #$C0
    sta transfer_ptr+2
    rts

; Request page+1 through the CPU mailbox. Zero denotes an ordinary source.
; The acknowledgment follows the hardware write, so DMA cannot race it.
worker_select_rom_bank:
    beq @done
    cmp f:$000790
    beq @done
    sta f:$00078C
@wait:
    cmp f:$000790
    bne @wait
@done:
    rts
.endif

.ifdef ROM_PATTERN_COUNT
.assert ROM_PATTERN_COUNT <= 32768,error,"Resident bitmap index exceeds lookup arena"
worker_rom_hash:
    lda f:M7_HASH_DIRTY
    beq @done
    ldy #0
@slot:
    tya
    asl a
    tax
    lda f:M7_PATTERN_VRAM,x
    cmp #ROM_PATTERN_COUNT
    bcs @next
    tax
    tya
    sep #$20
    .a8
    sta f:M7_RAW_TO_PPU,x
    rep #$20
    .a16
@next:
    iny
    cpy #256
    bcc @slot
    lda #0
    sta f:M7_HASH_DIRTY
@done:
    rts
worker_rom_find:
    sta M7_CACHE_LOGICAL
    cmp #ROM_PATTERN_COUNT
    bcs @absent
    tax
    lda f:M7_RAW_TO_PPU,x
    and #255
    tay
    asl a
    tax
    lda f:M7_PATTERN_VRAM,x
    cmp M7_CACHE_LOGICAL
    bne @absent
    tyx
    lda M7_NEW_VISIBLE,x
    and #255
    cmp #2
    beq @absent
    tya
    rts
@absent:
    lda #$FFFF
    rts
worker_rom_commit:
    lda selected_level
    cmp #ROM_PATTERN_LEVEL
    bne @done
    phy
    phx
    txa
    lsr a
    sta scratch2
    lda f:M7_PATTERN_VRAM,x
    cmp #ROM_PATTERN_COUNT
    bcs @skip
    tax
    lda scratch2
    sep #$20
    .a8
    sta f:M7_RAW_TO_PPU,x
    rep #$20
    .a16
@skip:
    plx
    ply
@done:
    rts
.endif
