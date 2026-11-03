; MSU animation is a sequential event stream. Bulk checkpoint snapshots
; restore mutable cells, positions, alpha and the PPU cache with fixed-source
; MSU-to-WRAM DMA, then replay only the short calibrated lead-in interval.
load_patterns:
    jsr reset_pattern_epoch
    lda #1
    sta cell_hash_dirty
    stz pattern_queue_count
    stz animation_header
    lda animation_base
    sta animation_cursor
    lda animation_base+2
    sta animation_cursor+2
    lda animation_cells
    asl a
    sta animation_bytes
    ldx #0
    lda #0
@cells:
    cpx animation_bytes
    bcs @alpha
    sta f:CELL_STATE,x
    inx
    inx
    bra @cells
@alpha:
    lda last_note
    inc a
    sta animation_bytes
    ldx #0
    sep #$20
    .a8
    lda #3
@floor:
    sta f:FLOOR_ALPHA,x
    inx
    cpx animation_bytes
    bcc @floor
    rep #$20
    .a16
    lda #2
    sta animation_mode
    jsr update_pattern_cache
    stz animation_mode
    rts

animation_advance:
    clc
    adc animation_cursor
    sta animation_cursor
    bcc @done
    inc animation_cursor+2
@done:
    rts

animation_seek:
    lda animation_cursor
    sta msu_seek_offset
    lda animation_cursor+2
    sta msu_seek_offset+2
    jmp msu_seek_data

; Borrow the port only around actual reads; audio may seek between records.
animation_read_begin:
    lda #1
    sta msu_data_busy
    lda animation_seek_dirty
    beq @done
    stz animation_seek_dirty
    jsr animation_seek
@done:
    rts

update_pattern_cache:
    lda #1
    sta msu_data_busy
    stz pattern_queue_count
    inc pattern_queue_epoch
    jsr animation_seek
    stz animation_seek_dirty
    stz msu_data_busy
@record:
    lda animation_header
    bne @time
    jsr animation_read_begin
    sep #$20
    .a8
    lda $2001
    sta animation_time
    lda $2001
    sta animation_time+1
    lda $2001
    sta animation_kind
    lda $2001
    sta animation_index
    lda $2001
    sta animation_index+1
    lda $2001
    sta animation_value
    lda $2001
    sta animation_value+1
    rep #$20
    .a16
    lda #7
    jsr animation_advance
    stz msu_data_busy
    inc animation_header
@time:
    lda animation_time
    cmp #$FFFF
    jeq @done
    cmp chart_time
    beq @apply
    jcs @done
@apply:
    stz animation_header
    lda animation_index
    asl a
    tax
    lda animation_kind
    and #255
    beq @cell
    cmp #1
    beq @opacity
    cmp #2
    beq @x
    cmp #3
    beq @y
    cmp #5
    bne @single_pattern
    jsr animation_cell_run
    jmp @record
@single_pattern:
    jmp @pattern
@cell:
    lda animation_value
    sta f:CELL_STATE,x
    jsr update_visible_cell
    jmp @record
@opacity:
    ldx animation_index
    sep #$20
    .a8
    lda animation_value
    sta f:FLOOR_ALPHA,x
    rep #$20
    .a16
    jmp @record
@x:
    lda animation_value
    sta f:NOTE_X,x
    jmp @record
@y:
    lda animation_value
    sta f:NOTE_Y,x
    jmp @record
@pattern:
    lda animation_value
    sta f:PATTERN_CURRENT,x
    lda animation_mode
    cmp #2
    jeq @discard
    cmp #1
    beq @restore
    lda animation_index
    asl a
    asl a
    tax
    lda f:PATTERN_QUEUE_LOOKUP,x
    cmp pattern_queue_epoch
    beq @queued
    lda pattern_queue_count
    cmp #40
    bcc @queue_available
    inc animation_header
    inc animation_deferred
    jmp @done
@queue_available:
    lda pattern_queue_epoch
    sta f:PATTERN_QUEUE_LOOKUP,x
    lda pattern_queue_count
    sta f:PATTERN_QUEUE_LOOKUP+2,x
    inc pattern_queue_count
    bra @queue_index
@queued:
    lda f:PATTERN_QUEUE_LOOKUP+2,x
@queue_index:
    pha
    jsr animation_read_begin
    pla
    asl a
    asl a
    asl a
    asl a
    asl a
    tax
    clc
    adc #.loword(PATTERN_QUEUE)+8
    sta f:PATTERN_QUEUE,x
    lda #$7E
    sta f:PATTERN_QUEUE+2,x
    lda animation_index
    asl a
    asl a
    asl a
    asl a
    sta f:PATTERN_QUEUE+4,x
    ldy #0
    sep #$20
    .a8
@pattern_bytes:
    lda $2001
    sta f:PATTERN_QUEUE+8,x
    inx
    iny
    cpy #16
    bcc @pattern_bytes
    rep #$20
    .a16
    bra @pattern_end
@restore:
    jsr animation_read_begin
    lda animation_index
    asl a
    asl a
    asl a
    asl a
    asl a
    tax
    ldy #0
    sep #$20
    .a8
@restore_bytes:
    lda $2001
    sta f:CHR_RAM,x
    inx
    iny
    cpy #16
    bcc @restore_bytes
    bra @pattern_end8
@discard:
    jsr animation_read_begin
    ldy #16
    sep #$20
    .a8
@skip:
    lda $2001
    dey
    bne @skip
@pattern_end8:
    rep #$20
    .a16
@pattern_end:
    lda #16
    jsr animation_advance
    stz msu_data_busy
    jmp @record
@done:
    stz msu_data_busy
    lda pattern_queue_count
    cmp pattern_peak_queued
    bcc @peak_done
    sta pattern_peak_queued
@peak_done:
    rts

; Consecutive state words are transferred through the MSU port in one DMA.
; Only the visible hash chains require per-cell CPU work afterwards.
animation_cell_run:
    lda animation_value
    sta animation_bytes
    asl a
    sta transfer_len
    lda animation_index
    asl a
    sta transfer_dest
    lda #1
    sta transfer_wbank
    jsr animation_read_begin
    jsr animation_dma
    lda transfer_len
    jsr animation_advance
    stz msu_data_busy
@cell:
    lda animation_index
    asl a
    tax
    lda f:CELL_STATE,x
    sta animation_value
    jsr update_visible_cell
    inc animation_index
    dec animation_bytes
    bne @cell
    rts

update_visible_cell:
    lda animation_mode
    bne @done
    lda cell_hash_dirty
    bne @done
    lda animation_index
    and #$6000
    asl a
    sta cell_hash_key
    lda animation_index
    and #$1FFF
    ora #$2000
    ora cell_hash_key
    sta cell_hash_key
    and #1023
    asl a
    tax
    lda f:CELL_HASH_HEAD,x
@chain:
    cmp #$FFFF
    beq @done
    tax
    lda f:DYNAMIC_CACHE,x
    cmp cell_hash_key
    beq @found
    lda f:CELL_HASH_NEXT,x
    bra @chain
@found:
    lda animation_value
    cmp TRACK,x
    beq @done
    sta TRACK,x
    lda #1
    sta track_dirty
@done:
    rts

; Maintain only slots replaced by scrolling, rather than all 1024 links.
replace_cell_hash:
    lda cell_hash_dirty
    bne @done
    stx cell_hash_slot
    lda f:DYNAMIC_CACHE,x
    bit #$2000
    beq @insert
    and #1023
    asl a
    tax
    stx cell_hash_bucket
    lda f:CELL_HASH_HEAD,x
    cmp cell_hash_slot
    bne @search
    ldx cell_hash_slot
    lda f:CELL_HASH_NEXT,x
    ldx cell_hash_bucket
    sta f:CELL_HASH_HEAD,x
    bra @insert
@search:
    cmp #$FFFF
    beq @insert
    tax
    lda f:CELL_HASH_NEXT,x
    cmp cell_hash_slot
    bne @search
    stx cell_hash_bucket
    ldx cell_hash_slot
    lda f:CELL_HASH_NEXT,x
    ldx cell_hash_bucket
    sta f:CELL_HASH_NEXT,x
@insert:
    lda map_tile
    bit #$2000
    beq @restore
    and #1023
    asl a
    tax
    stx cell_hash_bucket
    lda f:CELL_HASH_HEAD,x
    ldx cell_hash_slot
    sta f:CELL_HASH_NEXT,x
    txa
    ldx cell_hash_bucket
    sta f:CELL_HASH_HEAD,x
@restore:
    ldx cell_hash_slot
@done:
    rts

build_cell_hash:
    lda cell_hash_dirty
    beq @done
    stz cell_hash_dirty
    lda #$FFFF
    ldx #0
@clear:
    sta f:CELL_HASH_HEAD,x
    inx
    inx
    cpx #2048
    bcc @clear
    stz cell_hash_slot
@slot:
    ldx cell_hash_slot
    lda f:DYNAMIC_CACHE,x
    bit #$2000
    beq @next
    and #1023
    asl a
    sta cell_hash_bucket
    tax
    lda f:CELL_HASH_HEAD,x
    ldx cell_hash_slot
    sta f:CELL_HASH_NEXT,x
    txa
    ldx cell_hash_bucket
    sta f:CELL_HASH_HEAD,x
@next:
    inc cell_hash_slot
    inc cell_hash_slot
    lda cell_hash_slot
    cmp #2048
    bcc @slot
@done:
    rts

; Source stays at the MSU data port; the device advances its file position.
animation_dma:
    lda transfer_len
    beq @done
    sta $4305
    lda transfer_dest
    sta $2181
    lda #$2001
    sta $4302
    sep #$20
    .a8
    lda transfer_wbank
    sta $2183
    stz $4304
    lda #8
    sta $4300
    lda #$80
    sta $4301
    lda #1
    sta $420B
    rep #$20
    .a16
@done:
    rts

restore_pattern_cache:
    lda msu_checkpoint_index
    asl a
    asl a
    clc
    adc animation_table
    sta msu_seek_offset
    lda animation_table+2
    adc #0
    sta msu_seek_offset+2
    jsr msu_seek_data
    sep #$20
    .a8
    ldx #0
@snapshot_address:
    lda $2001
    sta msu_seek_offset,x
    inx
    cpx #4
    bcc @snapshot_address
    rep #$20
    .a16
    jsr msu_seek_data
    sep #$20
    .a8
    ldx #0
@header:
    lda $2001
    sta snapshot_header,x
    inx
    cpx #14
    bcc @header
    rep #$20
    .a16
    lda snapshot_header+4
    clc
    adc animation_base
    sta animation_cursor
    lda snapshot_header+6
    adc animation_base+2
    sta animation_cursor+2
    lda snapshot_header+8
    asl a
    sta transfer_len
    stz transfer_dest
    lda #1
    sta transfer_wbank
    jsr animation_dma
    lda snapshot_header+10
    asl a
    sta transfer_len
    lda #.loword(NOTE_X)
    sta transfer_dest
    stz transfer_wbank
    jsr animation_dma
    lda #.loword(NOTE_Y)
    sta transfer_dest
    jsr animation_dma
    lda snapshot_header+10
    sta transfer_len
    lda #.loword(FLOOR_ALPHA)
    sta transfer_dest
    lda #1
    sta transfer_wbank
    jsr animation_dma
    lda snapshot_header+12
    sta transfer_len
    lda #.loword(CHR_RAM)
    sta transfer_dest
    stz transfer_wbank
    jsr animation_dma
    stz animation_header
    lda #1
    sta animation_mode
    jsr update_pattern_cache
    stz animation_mode
    lda snapshot_header+12
    beq @reset_queue
    sep #$20
    .a8
    lda #$80
    sta $2100
    rep #$20
    .a16
    GFX CHR_RAM,0,32768
    ; The CHR staging buffer shares WRAM with the latter note arrays.
    DESC_PTR 0
    lda last_note
    inc a
    sta chart_count
    asl a
    asl a
    clc
    adc transfer_ptr
    sta transfer_ptr
    lda #4
    sta chart_array
@array:
    ldx chart_array
    lda chart_destinations,x
    sta transfer_dest
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
    stz transfer_wbank
    jsr upload_wram
    lda transfer_ptr
    clc
    adc transfer_len
    sta transfer_ptr
    inc chart_array
    inc chart_array
    lda chart_array
    cmp #18
    bcc @array
    lda #1
    sta pattern_blanked
@reset_queue:
    ; Snapshot CHR staging overlaps the viewport cache and its hash links.
    ; Rebuild those links before applying visible-cell changes after a seek.
    lda #1
    sta cell_hash_dirty
    ldx #0
    lda #0
@clear_view:
    sta f:DYNAMIC_CACHE,x
    inx
    inx
    cpx #2048
    bcc @clear_view
    jsr reset_pattern_epoch
@done:
    rts

reset_pattern_epoch:
    stz pattern_queue_epoch
    lda #0
    ldx #0
@word:
    sta f:PATTERN_QUEUE_LOOKUP,x
    inx
    inx
    cpx #4096
    bcc @word
    rts
