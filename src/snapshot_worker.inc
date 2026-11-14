; Full independent screen poses. All CHR pixels form one contiguous run;
; no hash, lease, dirty-map scan, speculative upload or cache eviction.
worker_snapshot_packet:
    lda M7_CACHE_CODE_VALID
    cmp #5
    beq @ready
    phb
    ldx #__HOTSNAPSHOT_LOAD__
    ldy #__HOTSNAPSHOT_RUN__
    lda #__HOTSNAPSHOT_SIZE__-1
    mvn #$01,#$00
    plb
    lda #0
    sta M7_ROW_CODE_VALID
    lda #5
    sta M7_CACHE_CODE_VALID
@ready:
    jmp worker_snapshot_decode
.segment "HOTSNAPSHOT"
worker_snapshot_decode:
    lda #0
    sta f:M1_PREFETCH_READY
    lda native_index
    sta native_count
    .repeat 5
    asl a
    .endrepeat
    sta f:M1_SNAPSHOT_BYTES
    lda f:M1_FRONT_BANK
    eor #$0200
    sta f:M1_BUILD_BANK
    phb
    ldx transfer_ptr
    ldy #.loword(M1_PALETTE)
    lda #95
    mvn #$42,#$42
    plb
    lda #96
    jsr worker_native_advance
    jsr worker_snapshot_map
    lda #1216
    jsr worker_native_advance
    lda native_kind
    cmp #44
    bne @expand
    lda f:M1_SNAPSHOT_BYTES
    jsr worker_native_advance
    jmp @ready
@expand:
    lda f:M1_BUILD_BANK
    .repeat 5
    asl a
    .endrepeat
    clc
    adc #32
    sta map_dest
    lda native_count
    beq @ready
@glyph:
    lda [transfer_ptr]
    and #255
    sta native_kind
    lda #1
    jsr worker_native_advance
    ldy map_dest
    lda native_kind
    cmp #2
    bne :+
    tya
    clc
    adc #16
    tay
:
    ldx transfer_ptr
    lda native_kind
    beq @full
    lda #15
    bra @copy
@full:
    lda #31
@copy:
    phb
    mvn #$42,#$43
    plb
    lda native_kind
    beq @advance_full
    cmp #2
    bne @zero
    tya
    sec
    sbc #32
    tay
@zero:
    tyx
    lda #0
    .repeat 8, ROW
    sta f:M1_CHR_STAGE+ROW*2,x
    .endrepeat
    lda #16
    bra @advance
@advance_full:
    lda #32
@advance:
    jsr worker_native_advance
    lda map_dest
    clc
    adc #32
    sta map_dest
    dec native_count
    jne @glyph
@ready:
    lda #1
    sta f:M1_READY
    sta f:M1_SNAPSHOT_DIRTY
    lda #0
    sta f:M1_RUN_COUNT
    lda f:M1_SNAPSHOT_BYTES
    sta f:M1_PATTERN_RUNS+2
    beq @prefetch_ready
    lda f:M1_BUILD_BANK
    .repeat 5
    asl a
    .endrepeat
    clc
    adc #32
    sta f:M1_PATTERN_RUNS
    lda #1
    sta f:M1_RUN_COUNT
@prefetch_ready:
    ; All atlas bytes are final. The IRQ may fill the unused VRAM bank
    ; while the main CPU is still positioning the live planets/trails.
    lda #1
    sta f:M1_PREFETCH_READY
    rts

.segment "CODE"
worker_snapshot_prepare:
    lda #0
    sta f:M7_WRAM_STAGE_REQUIRED
    sta f:M7_PATTERN_RUN_COUNT
    sta f:M7_TAG_COUNT
    sta f:SPILL_VISIBLE
    sta f:M7_FORCE_SKIP_HUD
    sta f:M7_STAGE_BASE_X
    sta f:M7_STAGE_BASE_Y
    sta f:M1_RUN_COUNT
    sta m7_row_count
    sta m7_row_span
    sta m7_upload_slots
    lda f:M1_SNAPSHOT_DIRTY
    beq @done
    lda f:M1_MAP_RUNS+2
    sta m7_row_span
    beq @chr
    lda #1
    sta m7_row_count
@chr:
    ; The IRQ may already have prefetched a prefix during planet work.
    ; Preserve its descriptor instead of queuing those pixels a second time.
    lda f:M1_PATTERN_RUNS+2
    .repeat 5
    lsr a
    .endrepeat
    sta m7_upload_slots
    beq @done
    lda #1
    sta f:M1_RUN_COUNT
@done:
    lda f:M1_SNAPSHOT_DIRTY
    sta f:M1_PREFETCH_READY
    rts

; Complete poses remain independent in the stream. Only changed map words
; need to reach VRAM: exclude identical prefix/suffix rows without adding
; dozens of small DMA runs or changing a single pixel/update.
worker_snapshot_map:
    lda f:M1_BUILD_BANK
    beq @bank_ready
    ldy #0
@bank:
    lda [transfer_ptr],y
    beq :+
    ora #$0200
    sta [transfer_ptr],y
:
    iny
    iny
    cpy #1216
    bcc @bank
@bank_ready:
    ldy #0
@first:
    tyx
    lda [transfer_ptr],y
    cmp f:M1_MAP_STAGE+256,x
    bne @found
    iny
    iny
    cpy #1216
    bcc @first
    lda #0
    sta f:M1_MAP_RUNS+2
    rts
@found:
    sty map_dest
    tya
    clc
    adc #256
    sta f:M1_MAP_RUNS
    ldy #1214
@last:
    tyx
    lda [transfer_ptr],y
    cmp f:M1_MAP_STAGE+256,x
    bne @copy
    dey
    dey
    bra @last
@copy:
    tya
    sec
    sbc map_dest
    clc
    adc #2
    sta f:M1_MAP_RUNS+2
    pha
    lda transfer_ptr
    clc
    adc map_dest
    tax
    lda map_dest
    clc
    adc #.loword(M1_MAP_STAGE)+256
    tay
    pla
    dec a
    phb
    mvn #$42,#$42
    plb
    rts

; Upload the exact range of changed hardware colors, rather than rewriting
; all six palettes on every screen-pose change. Native CGRAM fades still
; run on every authored frame, independently of geometry/selector changes.
worker_snapshot_colors:
    lda #192
    sta f:M1_CGRAM_BEGIN
    lda #0
    sta f:M1_CGRAM_BYTES
    ldx #0
@color:
    phx
    txa
    lsr a
    tax
    lda f:M1_PALETTE,x
    and #255
    beq @transparent
    sec
    sbc #32
    asl a
    tax
    lda f:NATIVE_PALETTE,x
    bra @compare
@transparent:
    lda #0
@compare:
    plx
    cmp f:M1_CGRAM,x
    beq @next
    sta f:M1_CGRAM,x
    txa
    cmp f:M1_CGRAM_BEGIN
    bcs :+
    sta f:M1_CGRAM_BEGIN
:
    txa
    inc a
    inc a
    sta f:M1_CGRAM_BYTES
@next:
    inx
    inx
    cpx #192
    bcc @color
    lda f:M1_CGRAM_BYTES
    beq @clean
    sec
    sbc f:M1_CGRAM_BEGIN
    sta f:M1_CGRAM_BYTES
@clean:
    sta f:M1_READY
    rts
